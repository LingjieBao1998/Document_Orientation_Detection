from PIL import Image, ImageDraw, ImageFont
import surya
from surya.detection import DetectionPredictor
import doctr
from doctr.utils.geometry import extract_rcrops
from doctr.models.classification import page_orientation_predictor, crop_orientation_predictor
from doctr.models.classification.predictor.pytorch import OrientationPredictor
import copy
import numpy as np
import time
import PyPDF2
from tqdm import tqdm
import pdf2image
from pdf2image import convert_from_path

# print(f"surya.__version__:{surya.__version__}")
print(f"doctr.__version__:{doctr.__version__}")
print(f"PyPDF2.__version__:{PyPDF2.__version__}")
# print(f"pdf2image.__version__:{pdf2image.__version__}")

font = ImageFont.truetype("arial.ttf", size=60)  # 需要系统中有 arial.ttf 字体文件
def vis_surya_detection(image, detection_result, class_results=None):
    bboxes = detection_result.bboxes

    temp_image = copy.deepcopy(image)

    # 创建绘图对象
    draw = ImageDraw.Draw(temp_image)

    # 定义颜色（RGB 格式）
    color = (0, 255, 0)  # 绿色（RGB）
    thickness = 2        # 线条粗细

    # 遍历所有检测到的文本框并绘制
    for i, bbox in enumerate(bboxes):
        polygon = bbox.polygon  # 获取多边形坐标 [[x1, y1], [x2, y2], ...]
        
        # 将坐标转换为整数（PIL 也要求坐标是整数）
        pts = [(int(x), int(y)) for x, y in polygon]
        
        # 绘制多边形框
        if class_results is not None:
            if class_results[i] == -90:
                draw.text(pts[0], f'{class_results[i]}', fill=(255, 0, 0), font=font)
                draw.polygon(pts, outline=(255, 0, 0), width=thickness)
            elif class_results[i] == 0:
                draw.text(pts[0], f'{class_results[i]}', fill=(0, 0, 255), font=font)
                draw.polygon(pts, outline=(0, 0, 255), width=thickness)
            elif class_results[i] == 90:
                draw.text(pts[0], f'{class_results[i]}', fill=(0, 255, 0), font=font)
                draw.polygon(pts, outline=(0, 255, 0), width=thickness)
            elif class_results[i] == 180:
                draw.text(pts[0], f'{class_results[i]}', fill=(0, 0, 0), font=font)
                draw.polygon(pts, outline=(0, 0, 0), width=thickness)
        else:
            draw.polygon(pts, outline=color, width=thickness)
            
    
    return temp_image

def get_normalized_polymer(detection_result, image=None, width=None, hegiht=None):
    bboxes = detection_result.bboxes
    if (width is None) and (hegiht is None):
        width, hegiht = image.width, image.height

    normalized_pts_list = []
    # 遍历所有检测到的文本框并绘制
    for bbox in tqdm(bboxes, desc="Processing polygon"):
        polygon = bbox.polygon  # 获取多边形坐标 [[x1, y1], [x2, y2], ...]
        
        # 将坐标转换为整数（PIL 也要求坐标是整数）
        pts = [(int(x), int(y)) for x, y in polygon]
        pts = np.array(pts).astype(np.float32)
        pts[:,0] = pts[:,0]/width
        pts[:,1] = pts[:,1]/hegiht
        normalized_pts_list.append(copy.deepcopy(pts))
    normalized_pts_array = np.stack(normalized_pts_list)
    return normalized_pts_array


def numpy_mode(arr):
    # 计算唯一值及其出现次数
    values, counts = np.unique(arr, return_counts=True)
    # 找到出现次数最多的值（可能有多个众数）
    max_count = np.max(counts)
    modes = values[counts == max_count]
    return modes[0]  # 返回所有众数（可能是一个数组）

def correct_fn(image:Image.Image = None, 
                det_predictor:surya.detection.DetectionPredictor = None, 
                page_orientation_model:OrientationPredictor = None, 
                orientation_predictor_model:OrientationPredictor=None,
                page_idx:int=0,
                return_anno_image:bool=False,
                rotate_image:bool=False):

    # predictions is a list of dicts, one per image
    predictions = det_predictor([image])
    # vis_surya_detection(image, predictions[0])

    normalized_pts_array = get_normalized_polymer(predictions[0], image) # (70, 4, 2)
    image_array = np.array(image)

    ## bottom-up
    crops = [extract_rcrops(image_array, normalized_pts_array[:, :4], assume_horizontal=False)]
    orientations, classes, probs = zip(*[orientation_predictor_model(page_crops) for page_crops in crops])
    angle = numpy_mode(classes)
    if angle in [0, 180]:
        pass
    else:
        ## top-down
        if page_orientation_model is not None:
            _, pege_classes, pege_probs = zip(page_orientation_model([image_array]))
            print(page_idx, "bottom-up:", angle, "top-down:",pege_classes[0][0])
        else:
            print(page_idx, "bottom-up:", angle)
    import ipdb
    ipdb.set_trace()
    if return_anno_image:
        temp_image = vis_surya_detection(image, predictions[0], class_results=classes[0])
        if rotate_image:
            temp_image = temp_image.rotate(angle, fillcolor=(255, 255, 255), expand=True)
            return angle, temp_image
    else:
        if rotate_image:
            image = image.rotate(angle, fillcolor=(255, 255, 255), expand=True)
        return angle, image



if __name__ == "__main__":
    start = time.time()
    image = Image.open("./assets/test_image3.png").convert("RGB")
    det_predictor = DetectionPredictor()
    page_orientation_model = page_orientation_predictor(pretrained=True, disabled=False)
    page_orientation_model = page_orientation_model.to("cuda:0")
    page_orientation_model.eval()
    orientation_predictor_model = crop_orientation_predictor(pretrained=True, disabled=False)
    orientation_predictor_model = orientation_predictor_model.to("cuda:0")
    orientation_predictor_model.eval()

    correct_fn(image, det_predictor, page_orientation_model, orientation_predictor_model)

    file_path = "./data/test_pdf/US20240059704A1.pdf"
    with open(file_path, 'rb') as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        num_pages = len(pdf_reader.pages)
        for page_idx in tqdm(range(1, 1+num_pages), desc="Processing pdf"):
            page = convert_from_path(file_path,
                                200,
                                first_page = page_idx,
                                last_page = page_idx + 1,
                                )[0]
            correct_fn(page, det_predictor, page_orientation_model, orientation_predictor_model, page_idx)
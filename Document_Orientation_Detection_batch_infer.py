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
import math

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

def batch_correct_fn(images:Image.Image = None, 
                    det_predictor:surya.detection.DetectionPredictor = None, 
                    page_orientation_model:OrientationPredictor = None, 
                    orientation_predictor_model:OrientationPredictor=None,
                    return_anno_image:bool=False,
                    rotate_image:bool=False,
                    page_idx_list:list=[]
                    ):

    # predictions is a list of dicts, one per image
    if isinstance(images, list):
        predictions = det_predictor(images)
        # vis_surya_detection(image, predictions[0])
    else:
        images = [images]
        predictions = det_predictor(images)

    angle_list = []
    for i in range(len(images)):
        image = images[i]
        image_array = np.array(image)
        normalized_pts_array = get_normalized_polymer(predictions[i], image) # (70, 4, 2)

        ## bottom-up
        crops = [extract_rcrops(image_array, normalized_pts_array[:, :4], assume_horizontal=False)]
        orientations, classes, probs = zip(*[orientation_predictor_model(page_crops) for page_crops in crops])
        angle = numpy_mode(classes)
        if angle in [0, 180]:
            angle_list.append(0)
            pass
        else:
            ## top-down
            if page_orientation_model is not None:
                _, pege_classes, pege_probs = zip(page_orientation_model([image_array]))
                print(page_idx_list[i], "bottom-up:", angle, "top-down:",pege_classes[0][0])
            else:
                print(page_idx_list[i], "bottom-up:", angle)
    
            angle_list.append(angle)
    
    return angle_list



if __name__ == "__main__":
    start = time.time()
    det_predictor = DetectionPredictor()
    page_orientation_model = page_orientation_predictor(pretrained=True, disabled=False)
    page_orientation_model = page_orientation_model.to("cuda:0")
    page_orientation_model.eval()
    orientation_predictor_model = crop_orientation_predictor(pretrained=True, disabled=False)
    orientation_predictor_model = orientation_predictor_model.to("cuda:0")
    orientation_predictor_model.eval()

    batch_size = 16

    file_path = "./data/test_pdf/US20240059704A1.pdf"
    with open(file_path, 'rb') as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        num_pages = len(pdf_reader.pages)
        for batch_idx in tqdm(range(int(math.ceil(num_pages/batch_size))), desc="Processing pdf"):

            pages = convert_from_path(file_path,
                                200,
                                first_page = (batch_idx)*16 + 1,
                                last_page = min((batch_idx+1)*16, num_pages+1),
                                )
            batch_correct_fn(pages, det_predictor, page_orientation_model, orientation_predictor_model, page_idx_list=list(range((batch_idx)*16 + 1, min((batch_idx+1)*16, num_pages)+1 )))
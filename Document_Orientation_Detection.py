from PIL import Image, ImageDraw
import surya
from surya.detection import DetectionPredictor
import doctr
from doctr.utils.geometry import extract_rcrops
from doctr.models.classification import page_orientation_predictor, crop_orientation_predictor
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

def vis_surya_detection(image, detection_result):
    bboxes = detection_result.bboxes

    temp_image = copy.deepcopy(image)

    # 创建绘图对象
    draw = ImageDraw.Draw(temp_image)

    # 定义颜色（RGB 格式）
    color = (0, 255, 0)  # 绿色（RGB）
    thickness = 2        # 线条粗细

    # 遍历所有检测到的文本框并绘制
    for bbox in bboxes:
        polygon = bbox.polygon  # 获取多边形坐标 [[x1, y1], [x2, y2], ...]
        
        # 将坐标转换为整数（PIL 也要求坐标是整数）
        pts = [(int(x), int(y)) for x, y in polygon]
        
        # 绘制多边形框
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

def correct_fn(image, det_predictor, page_orientation_model, orientation_predictor_model, page_idx=0):
    # predictions is a list of dicts, one per image
    predictions = det_predictor([image])
    # vis_surya_detection(image, predictions[0])

    normalized_pts_array = get_normalized_polymer(predictions[0], image) # (70, 4, 2)
    image_array = np.array(image)

    # _, classes, probs = zip(page_orientation_model([image_array]))
    # pege_classes = classes[0][0]
    # pege_probs = probs[0][0]
    # if pege_classes == 0:
    #     if pege_probs >= 0.8:
    #         angle = pege_classes
    #     else:
    #         crops = [extract_rcrops(image_array, normalized_pts_array[:, :4], assume_horizontal=False)]
    #         orientations, classes, probs = zip(*[orientation_predictor_model(page_crops) for page_crops in crops])
    #         angle = numpy_mode(classes)
    # else:
    #     angle = pege_classes
    crops = [extract_rcrops(image_array, normalized_pts_array[:, :4], assume_horizontal=False)]
    orientations, classes, probs = zip(*[orientation_predictor_model(page_crops) for page_crops in crops])
    angle = numpy_mode(classes)
    if angle in [0, 180]:
        pass
    else:
        _, classes, probs = zip(page_orientation_model([image_array]))
        print(page_idx, "bottom-up:", angle, "top-down:",classes[0][0])
        # if classes[0][0] not in [0, 180] and classes[0][0]!= angle and probs[0][0]>=0.8:
        #     angle = classes[0][0]
    
    # image.rotate(angle, fillcolor=(255, 255, 255), expand=True).save("2.png")
    # print(time.time()-start)
    return angle


if __name__ == "__main__":
    start = time.time()
    image = Image.open("./data/test_image/doc_neg_90.jpg").convert("RGB")
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
import cv2
import numpy as np
from PIL import Image

## ref:## ref:https://www.kaggle.com/code/ritvik1909/document-orientation-correction
def detect_angle(image):
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    ret, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(thresh > 0))
    angle = cv2.minAreaRect(coords)[-1]
    angle = -angle
    print(f"angle:{angle}")

if __name__ == "__main__":
    image = Image.open("./assets/test_image3_rotation.png").convert("RGB")
    image_array = np.array(image)
    detect_angle(image_array)
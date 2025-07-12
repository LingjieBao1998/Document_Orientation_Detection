import cv2
import numpy as np
from PIL import Image
import pytesseract
from pytesseract import Output

## ref:https://pyimagesearch.com/2022/01/31/correcting-text-orientation-with-tesseract-and-python/
if __name__ == "__main__":
    image = cv2.imread("./assets/test_image3_rotation.png")
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = pytesseract.image_to_osd(rgb, output_type=Output.DICT)

    # display the orientation information
    print("[INFO] detected orientation: {}".format(-results["orientation"])) #align in PIL
    print("[INFO] rotate by {} degrees to correct".format(results["rotate"]))
    print("[INFO] detected script: {}".format(results["script"]))
import json
import os
import cv2
import pytesseract
from PIL import Image

from capture_window import capture_window
from text_parser import build_disc_json

CONFIG_PATH = "config/roi_config.json"
OUTPUT_PATH = "output/scanned_discs.json"

# Update this if your Tesseract path is different.
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def preprocess_for_ocr(pil_image: Image.Image) -> Image.Image:
    img = cv2.cvtColor(cv2.imread("temp_crop.png"), cv2.COLOR_BGR2GRAY)

    img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    _, img = cv2.threshold(img, 150, 255, cv2.THRESH_BINARY)

    return Image.fromarray(img)


def ocr_crop(image: Image.Image, roi: dict) -> str:
    x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]
    crop = image.crop((x, y, x + w, y + h))

    crop.save("temp_crop.png")

    processed = preprocess_for_ocr(crop)

    text = pytesseract.image_to_string(
        processed,
        config="--psm 6"
    )

    return text.strip()


def load_rois() -> dict:
    if not os.path.exists(CONFIG_PATH):
        raise RuntimeError("Missing roi_config.json. Run calibrate_rois.py first.")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def append_disc_to_output(disc: dict):
    os.makedirs("output", exist_ok=True)

    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = []

    data.append(disc)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    rois = load_rois()
    screenshot = capture_window("Zenless")

    ocr_results = {}

    for field_name, roi in rois.items():
        text = ocr_crop(screenshot, roi)
        ocr_results[field_name] = text

    disc_json = build_disc_json(ocr_results)

    append_disc_to_output(disc_json)

    print(json.dumps(disc_json, indent=2, ensure_ascii=False))
    print(f"\nSaved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

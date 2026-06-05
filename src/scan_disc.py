import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from time import perf_counter
import cv2
import numpy as np
import pytesseract

from PIL import Image
from app_logging import configure_logging
from capture_window import capture_existing_window, capture_window
from text_parser import build_disc_json

CONFIG_PATH = "config/roi_config.json"
OUTPUT_PATH = "output/scanned_discs.json"
LOGGER_NAME = "zzz_scanner.scan_disc"
logger = logging.getLogger(LOGGER_NAME)

DEFAULT_OCR_CONFIG = "--psm 6"
FIELD_OCR_CONFIG = {
    "disc_name": "--psm 7",
    "main_stat": "--psm 7",
    "level": "--psm 7 -c tessedit_char_whitelist=Lv.0123456789/",
    "substats": "--psm 6",
}
DEFAULT_OCR_WORKERS = 4

# Update this if your Tesseract path is different.
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def preprocess_for_ocr(pil_image: Image.Image) -> Image.Image:
    img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2GRAY)

    img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    _, img = cv2.threshold(img, 150, 255, cv2.THRESH_BINARY)

    return Image.fromarray(img)


def ocr_crop(
    image: Image.Image,
    roi: dict,
    field_name: str | None = None,
) -> tuple[str, dict]:
    started_at = perf_counter()
    x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]
    crop = image.crop((x, y, x + w, y + h))

    preprocess_started_at = perf_counter()
    processed = preprocess_for_ocr(crop)
    preprocess_elapsed = perf_counter() - preprocess_started_at

    ocr_started_at = perf_counter()
    text = pytesseract.image_to_string(
        processed,
        config=FIELD_OCR_CONFIG.get(field_name, DEFAULT_OCR_CONFIG),
    )
    ocr_elapsed = perf_counter() - ocr_started_at

    return text.strip(), {
        "preprocess": preprocess_elapsed,
        "ocr": ocr_elapsed,
        "total": perf_counter() - started_at,
    }


@lru_cache(maxsize=1)
def load_rois() -> dict:
    if not os.path.exists(CONFIG_PATH):
        raise RuntimeError("Missing roi_config.json. Run calibrate_rois.py first.")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_ocr_worker_count(field_count: int) -> int:
    configured_workers = os.environ.get("ZZZ_OCR_WORKERS")

    if configured_workers:
        try:
            worker_count = int(configured_workers)
        except ValueError:
            logger.warning(
                "Ignoring invalid ZZZ_OCR_WORKERS=%r; using %s workers.",
                configured_workers,
                DEFAULT_OCR_WORKERS,
            )
            worker_count = DEFAULT_OCR_WORKERS
    else:
        worker_count = DEFAULT_OCR_WORKERS

    return max(1, min(worker_count, field_count))


def run_ocr_fields(image: Image.Image, rois: dict) -> tuple[dict, dict]:
    ocr_results = {}
    field_timings = {}
    worker_count = get_ocr_worker_count(len(rois))

    if worker_count == 1:
        for field_name, roi in rois.items():
            text, field_timing = ocr_crop(
                image=image,
                roi=roi,
                field_name=field_name,
            )
            ocr_results[field_name] = text
            field_timings[field_name] = field_timing

        return ocr_results, {
            "fields": field_timings,
            "workers": worker_count,
            "mode": "sequential",
        }

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_field = {
            executor.submit(
                ocr_crop,
                image=image,
                roi=roi,
                field_name=field_name,
            ): field_name
            for field_name, roi in rois.items()
        }

        for future in as_completed(future_to_field):
            field_name = future_to_field[future]
            text, field_timing = future.result()
            ocr_results[field_name] = text
            field_timings[field_name] = field_timing

    return ocr_results, {
        "fields": field_timings,
        "workers": worker_count,
        "mode": "parallel",
    }


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


def scan_current_disc(window=None, return_timing: bool = False):
    total_started_at = perf_counter()

    rois_started_at = perf_counter()
    rois = load_rois()
    timings = {
        "load_rois": perf_counter() - rois_started_at,
        "fields": {},
    }

    capture_started_at = perf_counter()
    if window is None:
        screenshot = capture_window("Zenless")
    else:
        screenshot = capture_existing_window(window)
    timings["capture"] = perf_counter() - capture_started_at

    all_ocr_started_at = perf_counter()
    ocr_results, ocr_metadata = run_ocr_fields(screenshot, rois)
    timings.update(ocr_metadata)
    timings["ocr_total"] = perf_counter() - all_ocr_started_at

    parse_started_at = perf_counter()
    disc_json = build_disc_json(ocr_results)
    timings["parse"] = perf_counter() - parse_started_at
    timings["total"] = perf_counter() - total_started_at

    if return_timing:
        return disc_json, timings

    return disc_json


def main():
    configure_logging()

    disc_json, timings = scan_current_disc(return_timing=True)

    append_disc_to_output(disc_json)

    logger.info("Scanned disc:\n%s", json.dumps(disc_json, indent=2, ensure_ascii=False))
    logger.info(
        "Scan timings: mode=%s workers=%s total=%.3fs capture=%.3fs ocr=%.3fs parse=%.3fs",
        timings.get("mode"),
        timings.get("workers"),
        timings["total"],
        timings["capture"],
        timings["ocr_total"],
        timings["parse"],
    )
    logger.info("Saved to %s", OUTPUT_PATH)


if __name__ == "__main__":
    main()

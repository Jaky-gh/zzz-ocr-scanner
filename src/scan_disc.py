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

from src.app_logging import configure_logging
from src.coordinate_scaling import get_config_base_size, scale_rois
from src.capture_window import capture_existing_window, capture_window
from src.paths import OUTPUT_DIR, ROI_CONFIG_PATH, SCANNED_DISCS_PATH
from src.text_parser import build_disc_json, load_drive_disc_names, normalize_disc_name

CONFIG_PATH = ROI_CONFIG_PATH
OUTPUT_PATH = SCANNED_DISCS_PATH
LOGGER_NAME = "zzz_scanner.scan_disc"
logger = logging.getLogger(LOGGER_NAME)

DEFAULT_OCR_CONFIG = "--psm 6"
FIELD_OCR_CONFIG = {
    "disc_name": "--psm 6",
    "main_stat": "--psm 7",
    "level": "--psm 7 -c tessedit_char_whitelist=Lv.0123456789/",
    "substats": "--psm 6",
    "disc_count": "--psm 7 -c tessedit_char_whitelist=0123456789/",
}
DEFAULT_OCR_WORKERS = 4
ROI_FIELD_NAMES = frozenset({"disc_name", "main_stat", "level", "substats"})

# Update this if your Tesseract path is different.
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def grayscale_upscale(pil_image: Image.Image, scale: int = 2):
    img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2GRAY)
    return cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def preprocess_for_ocr(pil_image: Image.Image, field_name: str | None = None) -> Image.Image:
    img = grayscale_upscale(pil_image)

    if field_name == "disc_count":
        img = cv2.adaptiveThreshold(
            img,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            5,
        )
    else:
        _, img = cv2.threshold(img, 150, 255, cv2.THRESH_BINARY)

    return Image.fromarray(img)


def preprocess_disc_name_variants(pil_image: Image.Image) -> list[tuple[str, Image.Image]]:
    gray = grayscale_upscale(pil_image, scale=3)
    variants = [("gray", Image.fromarray(gray))]

    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    variants.append(("binary", Image.fromarray(binary)))

    adaptive = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        3,
    )
    variants.append(("adaptive", Image.fromarray(adaptive)))

    return variants


def ocr_image(processed: Image.Image, field_name: str | None = None) -> str:
    return pytesseract.image_to_string(
        processed,
        config=FIELD_OCR_CONFIG.get(field_name, DEFAULT_OCR_CONFIG),
    ).strip()


@lru_cache(maxsize=1)
def known_disc_name_set() -> frozenset[str]:
    return frozenset(load_drive_disc_names())


def score_disc_name_text(text: str) -> tuple[int, int]:
    normalized_name = normalize_disc_name(text)
    known_match = 1 if normalized_name in known_disc_name_set() else 0
    return known_match, len(text.strip())


def ocr_disc_name_crop(crop: Image.Image, debug_name: str | None = None) -> tuple[str, dict]:
    started_at = perf_counter()
    best_text = ""
    best_variant = ""
    variant_timings = {}

    for variant_name, processed in preprocess_disc_name_variants(crop):
        variant_started_at = perf_counter()
        text = ocr_image(processed, field_name="disc_name")
        variant_elapsed = perf_counter() - variant_started_at
        variant_timings[variant_name] = {
            "ocr": variant_elapsed,
            "text": text,
        }

        if debug_name:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            processed.save(OUTPUT_DIR / f"{debug_name}_{variant_name}.png")

        if score_disc_name_text(text) > score_disc_name_text(best_text):
            best_text = text
            best_variant = variant_name

    return best_text, {
        "preprocess": 0,
        "ocr": sum(timing["ocr"] for timing in variant_timings.values()),
        "total": perf_counter() - started_at,
        "variant": best_variant,
        "variants": variant_timings,
    }


def ocr_crop(
    image: Image.Image,
    roi: dict,
    field_name: str | None = None,
    debug_name: str | None = None,
) -> tuple[str, dict]:
    started_at = perf_counter()
    x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]
    crop = image.crop((x, y, x + w, y + h))

    if field_name == "disc_name":
        if debug_name:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            crop.save(OUTPUT_DIR / f"{debug_name}_raw.png")

        text, timing = ocr_disc_name_crop(crop, debug_name=debug_name)
        timing["total"] = perf_counter() - started_at
        return text, timing

    preprocess_started_at = perf_counter()
    processed = preprocess_for_ocr(crop, field_name=field_name)
    preprocess_elapsed = perf_counter() - preprocess_started_at

    if debug_name:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        crop.save(OUTPUT_DIR / f"{debug_name}_raw.png")
        processed.save(OUTPUT_DIR / f"{debug_name}_processed.png")

    ocr_started_at = perf_counter()
    text = ocr_image(processed, field_name=field_name)
    ocr_elapsed = perf_counter() - ocr_started_at

    return text, {
        "preprocess": preprocess_elapsed,
        "ocr": ocr_elapsed,
        "total": perf_counter() - started_at,
    }


@lru_cache(maxsize=1)
def load_roi_config() -> dict:
    if not CONFIG_PATH.exists():
        raise RuntimeError("Missing roi_config.json. Run calibrate_rois.py first.")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_rois() -> dict:
    return {
        field_name: roi
        for field_name, roi in load_roi_config().items()
        if field_name in ROI_FIELD_NAMES
    }


def load_roi_base_size() -> tuple[int, int] | None:
    return get_config_base_size(load_roi_config().get("_meta", {}))


def maybe_scale_rois_for_image(rois: dict, image: Image.Image) -> dict:
    base_size = load_roi_base_size()

    if base_size is None:
        logger.debug("No ROI base_window_size configured; using absolute ROI coordinates.")
        return rois

    image_size = image.size

    if image_size == base_size:
        logger.debug("Image size matches ROI base_window_size=%sx%s.", *base_size)
        return rois

    logger.debug(
        "Scaling OCR ROIs from base_window_size=%sx%s to current image=%sx%s.",
        base_size[0],
        base_size[1],
        image_size[0],
        image_size[1],
    )
    return scale_rois(rois, base_size, image_size)


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
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if OUTPUT_PATH.exists():
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
    rois = maybe_scale_rois_for_image(rois, screenshot)

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

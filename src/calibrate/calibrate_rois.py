import json
import logging
import cv2
import os

from src.app_logging import configure_logging
from src.capture_window import capture_window


CONFIG_PATH = "config/roi_config.json"
logger = logging.getLogger("zzz_scanner.calibrate_rois")

ROI_NAMES = [
    "disc_name",
    "main_stat",
    "level",
    "substats",
]


def main():
    configure_logging()
    os.makedirs("config", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    image = capture_window("ZenlessZoneZero")
    image_path = "output/calibration_screenshot.png"
    image.save(image_path)

    img = cv2.imread(image_path)

    rois = {}

    logger.info("Draw each ROI, then press ENTER/SPACE. Press C to cancel current selection.")

    for name in ROI_NAMES:
        logger.info("Select ROI for: %s", name)
        x, y, w, h = cv2.selectROI(f"Select {name}", img, showCrosshair=True)
        cv2.destroyWindow(f"Select {name}")

        if w == 0 or h == 0:
            logger.info("Skipped %s", name)
            continue

        rois[name] = {
            "x": int(x),
            "y": int(y),
            "w": int(w),
            "h": int(h),
        }

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(rois, f, indent=2)

    logger.info("Saved ROI config to %s", CONFIG_PATH)


if __name__ == "__main__":
    main()

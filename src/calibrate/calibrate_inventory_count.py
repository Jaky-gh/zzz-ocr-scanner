import logging

import cv2

from src.app_logging import configure_logging
from src.calibrate.calibrate_rois import save_inventory_count_roi
from src.capture_window import capture_window
from src.paths import OUTPUT_DIR

logger = logging.getLogger("zzz_scanner.calibrate_inventory_count")


def main():
    configure_logging()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    image = capture_window("ZenlessZoneZero")
    image_path = OUTPUT_DIR / "inventory_count_calibration.png"
    image.save(image_path)

    img = cv2.imread(image_path)

    logger.info("Select the inventory count ROI, for example the text that looks like 1234/3000.")
    x, y, w, h = cv2.selectROI("Select inventory count", img, showCrosshair=True)
    cv2.destroyWindow("Select inventory count")

    if w == 0 or h == 0:
        logger.info("No ROI selected. Leaving grid config unchanged.")
        return

    save_inventory_count_roi({
        "x": int(x),
        "y": int(y),
        "w": int(w),
        "h": int(h),
    })


if __name__ == "__main__":
    main()

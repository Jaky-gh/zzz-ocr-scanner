import json
import logging
import cv2

from src.app_logging import configure_logging
from src.capture_window import capture_window
from src.paths import GRID_CONFIG_PATH, OUTPUT_DIR, ROI_CONFIG_PATH


CONFIG_PATH = ROI_CONFIG_PATH
logger = logging.getLogger("zzz_scanner.calibrate_rois")

ROI_NAMES = [
    "disc_name",
    "main_stat",
    "level",
    "substats",
]


def select_roi(img, name: str) -> dict | None:
    logger.info("Select ROI for: %s", name)
    x, y, w, h = cv2.selectROI(f"Select {name}", img, showCrosshair=True)
    cv2.destroyWindow(f"Select {name}")

    if w == 0 or h == 0:
        logger.info("Skipped %s", name)
        return None

    return {
        "x": int(x),
        "y": int(y),
        "w": int(w),
        "h": int(h),
    }


def load_grid_config() -> dict:
    if not GRID_CONFIG_PATH.exists():
        logger.info("Missing %s; inventory count ROI will not be saved.", GRID_CONFIG_PATH)
        return {}

    with open(GRID_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_inventory_count_roi(roi: dict):
    config = load_grid_config()
    config["inventory_count_roi"] = roi

    with open(GRID_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    logger.info("Saved inventory_count_roi to %s", GRID_CONFIG_PATH)


def main():
    configure_logging()
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    image = capture_window("ZenlessZoneZero")
    image_path = OUTPUT_DIR / "calibration_screenshot.png"
    image.save(image_path)

    img = cv2.imread(image_path)

    rois = {}

    logger.info("Draw each ROI, then press ENTER/SPACE. Press C to cancel current selection.")

    for name in ROI_NAMES:
        roi = select_roi(img, name)

        if roi:
            rois[name] = roi

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(rois, f, indent=2)

    logger.info("Saved ROI config to %s", CONFIG_PATH)

    answer = input(
        "Calibrate inventory count ROI for count-based stop? "
        "Select the text like 1234/3000. [y/N]: "
    ).strip().lower()

    if answer not in {"y", "yes"}:
        logger.info("Skipped inventory count ROI calibration.")
        return

    count_roi = select_roi(img, "inventory_count")

    if count_roi:
        save_inventory_count_roi(count_roi)


if __name__ == "__main__":
    main()

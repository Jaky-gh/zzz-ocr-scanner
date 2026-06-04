import json
import cv2
import os
from capture_window import capture_window

CONFIG_PATH = "config/roi_config.json"

ROI_NAMES = [
    "disc_name",
    "main_stat",
    "level",
    "substats",
]


def main():
    os.makedirs("config", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    image = capture_window("ZenlessZoneZero")
    image_path = "output/calibration_screenshot.png"
    image.save(image_path)

    img = cv2.imread(image_path)

    rois = {}

    print("Draw each ROI, then press ENTER/SPACE. Press C to cancel current selection.")

    for name in ROI_NAMES:
        print(f"Select ROI for: {name}")
        x, y, w, h = cv2.selectROI(f"Select {name}", img, showCrosshair=True)
        cv2.destroyWindow(f"Select {name}")

        if w == 0 or h == 0:
            print(f"Skipped {name}")
            continue

        rois[name] = {
            "x": int(x),
            "y": int(y),
            "w": int(w),
            "h": int(h),
        }

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(rois, f, indent=2)

    print(f"Saved ROI config to {CONFIG_PATH}")


if __name__ == "__main__":
    main()

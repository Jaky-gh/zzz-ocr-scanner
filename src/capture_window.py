import logging
import time

import mss
import pygetwindow as gw
from PIL import Image

try:
    from src.app_logging import configure_logging
    from src.paths import OUTPUT_DIR
except ModuleNotFoundError:
    from app_logging import configure_logging
    from paths import OUTPUT_DIR


ZZZ_TITLE_KEYWORDS = [
    "Zenless",
    "Zenless Zone Zero",
    "ZenlessZoneZero",
]
logger = logging.getLogger("zzz_scanner.capture_window")


def find_zzz_window():
    windows = gw.getAllWindows()

    for window in windows:
        title = window.title or ""

        if not title.strip():
            continue

        title_lower = title.lower()

        if "pycharm" in title_lower:
            continue

        for keyword in ZZZ_TITLE_KEYWORDS:
            if keyword.lower() in title_lower:
                if window.width > 0 and window.height > 0:
                    return window

    logger.error("Available windows:")
    for w in windows:
        if w.title.strip():
            logger.error("%r", w.title)

    raise RuntimeError("Could not find the ZZZ window.")


def activate_window(window):
    if window.isMinimized:
        window.restore()
        time.sleep(0.5)

    try:
        window.activate()
        time.sleep(1)
    except Exception as e:
        logger.warning("Could not activate window normally: %s", e)
        logger.warning(
            "Try running PyCharm/terminal as Administrator, or use borderless/windowed mode."
        )


def capture_existing_window(window) -> Image.Image:
    left = window.left
    top = window.top
    width = window.width
    height = window.height

    monitor = {
        "left": left,
        "top": top,
        "width": width,
        "height": height,
    }

    with mss.MSS() as sct:
        screenshot = sct.grab(monitor)
        image = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

    return image


def capture_zzz_window() -> Image.Image:
    window = find_zzz_window()

    logger.info("Found ZZZ window: %r", window.title)

    activate_window(window)

    return capture_existing_window(window)


# Keep this name so your other files do not break
def capture_window(title_keyword: str = "Zenless") -> Image.Image:
    return capture_zzz_window()


if __name__ == "__main__":
    configure_logging()
    img = capture_zzz_window()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image_path = OUTPUT_DIR / "window_capture.png"
    img.save(image_path)
    logger.info("Saved screenshot to %s", image_path)

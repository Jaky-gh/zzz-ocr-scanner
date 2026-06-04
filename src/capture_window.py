import time
import mss
import pygetwindow as gw
from PIL import Image


ZZZ_TITLE_KEYWORDS = [
    "Zenless",
    "Zenless Zone Zero",
    "ZenlessZoneZero",
]


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

    print("Available windows:")
    for w in windows:
        if w.title.strip():
            print(repr(w.title))

    raise RuntimeError("Could not find the ZZZ window.")


def activate_window(window):
    if window.isMinimized:
        window.restore()
        time.sleep(0.5)

    try:
        window.activate()
        time.sleep(1)
    except Exception as e:
        print(f"Could not activate window normally: {e}")
        print("Try running PyCharm/terminal as Administrator, or use borderless/windowed mode.")


def capture_zzz_window() -> Image.Image:
    window = find_zzz_window()

    print(f"Found ZZZ window: {window.title!r}")

    activate_window(window)

    # Refresh window position after activation
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


# Keep this name so your other files do not break
def capture_window(title_keyword: str = "Zenless") -> Image.Image:
    return capture_zzz_window()


if __name__ == "__main__":
    img = capture_zzz_window()
    img.save("output/window_capture.png")
    print("Saved screenshot to output/window_capture.png")

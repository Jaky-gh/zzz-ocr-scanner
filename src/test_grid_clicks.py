import json
import time
import pyautogui

from capture_window import find_zzz_window, activate_window

GRID_CONFIG_PATH = "config/grid_config.json"


def main():
    with open(GRID_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    window = find_zzz_window()
    activate_window(window)

    base_left = window.left
    base_top = window.top

    first_x = config["first_x"]
    first_y = config["first_y"]
    x_step = config["x_step"]

    print("Testing first 5 disc clicks.")
    print("Watch ZZZ and confirm whether the yellow selection box moves.")

    for col in range(5):
        x = base_left + first_x + col * x_step
        y = base_top + first_y

        print(f"Clicking col={col + 1} at screen position ({x}, {y})")
        pyautogui.moveTo(x, y, duration=0.2)
        pyautogui.click()
        time.sleep(1.2)

    print("Done.")


if __name__ == "__main__":
    main()

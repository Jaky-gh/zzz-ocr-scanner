import json
import time
import pydirectinput

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

    print("Testing first 5 disc clicks with PyDirectInput.")
    print("Watch ZZZ and confirm whether the yellow selection box moves.")

    time.sleep(1)

    for col in range(5):
        x = base_left + first_x + col * x_step
        y = base_top + first_y

        print(f"Clicking col={col + 1} at screen position ({x}, {y})")
        pydirectinput.moveTo(x, y)
        time.sleep(0.2)
        pydirectinput.click()
        time.sleep(1.2)

    print("Done.")


if __name__ == "__main__":
    main()

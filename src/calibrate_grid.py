import json
import time
import pyautogui

from capture_window import find_zzz_window, activate_window

OUTPUT_PATH = "config/grid_config.json"


def ask_point(label: str):
    input(f"\nMove your mouse to the CENTER of {label}, then press ENTER here...")
    x, y = pyautogui.position()
    print(f"{label}: screen position = ({x}, {y})")
    return x, y


def main():
    window = find_zzz_window()
    activate_window(window)

    print("We will record 3 positions:")
    print("1. First disc, row 1 col 1")
    print("2. Second disc, row 1 col 2")
    print("3. First disc, row 2 col 1")
    print("\nUse the CENTER of the disc card, not the level text.")

    time.sleep(1)

    x1, y1 = ask_point("row 1 col 1")
    x2, y2 = ask_point("row 1 col 2")
    x3, y3 = ask_point("row 2 col 1")

    base_left = window.left
    base_top = window.top

    first_x = x1 - base_left
    first_y = y1 - base_top
    x_step = x2 - x1
    y_step = y3 - y1

    config = {
        "columns": 9,
        "rows": 5,
        "first_x": first_x,
        "first_y": first_y,
        "x_step": x_step,
        "y_step": y_step,
        "click_delay": 1.0,
        "scroll_amount": -5,
        "page_delay": 0.7
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print("\nSaved grid config:")
    print(json.dumps(config, indent=2))


if __name__ == "__main__":
    main()

import json
import logging
import time

import pydirectinput

from src.app_logging import configure_logging
from src.capture_window import find_zzz_window, activate_window
from src.paths import GRID_CONFIG_PATH


OUTPUT_PATH = GRID_CONFIG_PATH
logger = logging.getLogger("zzz_scanner.calibrate_grid")


def load_existing_config() -> dict:
    if not OUTPUT_PATH.exists():
        return {}

    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def ask_point(label: str):
    input(f"\nMove your mouse to the CENTER of {label}, then press ENTER here...")
    x, y = pydirectinput.position()
    logger.info("%s: screen position = (%s, %s)", label, x, y)
    return x, y


def main():
    configure_logging()
    window = find_zzz_window()
    activate_window(window)

    logger.info("We will record 3 positions:")
    logger.info("1. First disc, row 1 col 1")
    logger.info("2. Second disc, row 1 col 2")
    logger.info("3. First disc, row 2 col 1")
    logger.info("Use the CENTER of the disc card, not the level text.")

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

    config = load_existing_config()
    config.update(
        {
            "base_window_size": {
                "width": int(window.width),
                "height": int(window.height),
            },
            "columns": config.get("columns", 9),
            "rows": config.get("rows", 4),
            "first_x": first_x,
            "first_y": first_y,
            "x_step": x_step,
            "y_step": y_step,
        }
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    logger.info("Saved grid config:\n%s", json.dumps(config, indent=2))


if __name__ == "__main__":
    main()

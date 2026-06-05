import json
import logging
import time

import pydirectinput

from src.app_logging import configure_logging
from src.capture_window import find_zzz_window, activate_window


GRID_CONFIG_PATH = "config/grid_config.json"
logger = logging.getLogger("zzz_scanner.test_grid_clicks")


def main():
    configure_logging()
    with open(GRID_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    window = find_zzz_window()
    activate_window(window)

    base_left = window.left
    base_top = window.top

    first_x = config["first_x"]
    first_y = config["first_y"]
    x_step = config["x_step"]

    logger.info("Testing first 5 disc clicks with PyDirectInput.")
    logger.info("Watch ZZZ and confirm whether the yellow selection box moves.")

    time.sleep(1)

    for col in range(5):
        x = base_left + first_x + col * x_step
        y = base_top + first_y

        logger.info("Clicking col=%s at screen position (%s, %s)", col + 1, x, y)
        pydirectinput.moveTo(x, y)
        time.sleep(0.2)
        pydirectinput.click()
        time.sleep(1.2)

    logger.info("Done.")


if __name__ == "__main__":
    main()

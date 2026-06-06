import argparse
import logging
from datetime import datetime
from pathlib import Path

from src.app_logging import configure_logging
from src.capture_window import activate_window, capture_existing_window, find_zzz_window
from src.paths import SCREENSHOT_FIXTURES_DIR

logger = logging.getLogger("zzz_scanner.capture_zzz_screenshot")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Bring Zenless Zone Zero to the foreground and save a screenshot fixture."
    )
    parser.add_argument(
        "--name",
        help="Optional output filename. Example: disc_inventory_1920x1080.png",
    )
    parser.add_argument(
        "--output-dir",
        default=str(SCREENSHOT_FIXTURES_DIR),
        help="Directory where the screenshot is saved.",
    )
    return parser.parse_args()


def make_default_filename(width: int, height: int) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"disc_inventory_{width}x{height}_{timestamp}.png"


def main():
    configure_logging()
    args = parse_args()

    window = find_zzz_window()
    logger.info(
        "Found ZZZ window: %r at left=%s top=%s size=%sx%s",
        window.title,
        window.left,
        window.top,
        window.width,
        window.height,
    )

    activate_window(window)
    image = capture_existing_window(window)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = args.name or make_default_filename(image.width, image.height)
    if not filename.lower().endswith(".png"):
        filename = f"{filename}.png"

    output_path = output_dir / filename
    image.save(output_path)

    logger.info("Saved screenshot fixture to %s", output_path)
    logger.info("Screenshot size: %sx%s", image.width, image.height)


if __name__ == "__main__":
    main()

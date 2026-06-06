import json

from PIL import Image

from src.paths import PROJECT_ROOT, SCREENSHOT_FIXTURES_DIR
from src.scan_disc import load_rois, maybe_scale_rois_for_image, run_ocr_fields
from src.text_parser import build_disc_json

EXPECTATIONS_PATH = PROJECT_ROOT / "tests" / "fixtures" / "screenshot_expectations.json"


def assert_equal(actual, expected, context: str):
    if actual != expected:
        raise AssertionError(f"{context}: expected {expected!r}, got {actual!r}")


def assert_disc_matches(filename: str, expected: dict):
    image_path = SCREENSHOT_FIXTURES_DIR / filename

    if not image_path.exists():
        raise AssertionError(f"Missing screenshot fixture: {image_path}")

    image = Image.open(image_path).convert("RGB")
    rois = maybe_scale_rois_for_image(load_rois(), image)
    ocr_results, _metadata = run_ocr_fields(image, rois)
    disc = build_disc_json(ocr_results)

    assert_equal(disc.get("disc_name"), expected["disc_name"], f"{filename} disc_name")
    assert_equal(disc.get("slot"), expected["slot"], f"{filename} slot")
    assert_equal(disc.get("level"), expected["level"], f"{filename} level")

    main_stat = disc.get("main_stat") or {}
    expected_main_stat = expected["main_stat"]
    assert_equal(main_stat.get("stat"), expected_main_stat["stat"], f"{filename} main_stat.stat")
    assert_equal(main_stat.get("value"), expected_main_stat["value"], f"{filename} main_stat.value")


def main():
    with open(EXPECTATIONS_PATH, "r", encoding="utf-8") as f:
        expectations = json.load(f)

    for filename, expected in expectations.items():
        assert_disc_matches(filename, expected)

    print("screenshot fixture checks passed")


if __name__ == "__main__":
    main()

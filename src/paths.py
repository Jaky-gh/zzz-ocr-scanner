from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
OUTPUT_DIR = PROJECT_ROOT / "output"
TEST_FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
SCREENSHOT_FIXTURES_DIR = TEST_FIXTURES_DIR / "screenshots"

GRID_CONFIG_PATH = CONFIG_DIR / "grid_config.json"
ROI_CONFIG_PATH = CONFIG_DIR / "roi_config.json"
DRIVE_DISC_NAMES_PATH = CONFIG_DIR / "drive_disc_names.json"

SCANNED_DISCS_PATH = OUTPUT_DIR / "scanned_discs.json"
SCANNER_LOG_PATH = OUTPUT_DIR / "scanner.log"

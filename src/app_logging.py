import logging
import os
from pathlib import Path

try:
    from src.paths import SCANNER_LOG_PATH
except ModuleNotFoundError:
    from paths import SCANNER_LOG_PATH


DEFAULT_LOG_PATH = SCANNER_LOG_PATH


def configure_logging(
    level: str | int | None = None,
    log_path: str | Path | None = DEFAULT_LOG_PATH,
) -> None:
    """
    Configure application logging once.

    The console stays readable during long scans, while the file log keeps a
    timestamped trace for debugging slow or failed runs.
    """
    if logging.getLogger().handlers:
        return

    resolved_level = level or os.environ.get("ZZZ_SCANNER_LOG_LEVEL", "INFO")
    if isinstance(resolved_level, str):
        resolved_level = resolved_level.upper()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    handlers: list[logging.Handler] = []

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)

    if log_path:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    logging.basicConfig(level=resolved_level, handlers=handlers)

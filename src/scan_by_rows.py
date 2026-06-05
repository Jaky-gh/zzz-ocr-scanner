import json
import logging
import os
import time
from time import perf_counter

import pydirectinput

from app_logging import configure_logging
from capture_window import find_zzz_window, activate_window
from scan_disc import scan_current_disc

GRID_CONFIG_PATH = "config/grid_config.json"
OUTPUT_PATH = "output/scanned_discs.json"
logger = logging.getLogger("zzz_scanner.scan_by_rows")
pydirectinput.PAUSE = 0


def load_grid_config() -> dict:
    with open(GRID_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_existing_data() -> list:
    if not os.path.exists(OUTPUT_PATH):
        return []

    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: list):
    os.makedirs("output", exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def make_disc_key(disc: dict) -> str:
    return json.dumps(
        {
            "disc_name": disc.get("disc_name"),
            "slot": disc.get("slot"),
            "main_stat": disc.get("main_stat"),
            "level": disc.get("level"),
            "substats": disc.get("substats"),
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def make_row_key(row_discs: list[dict]) -> str:
    """
    Creates a stable row signature.
    Used to detect when auto-scroll did not move anymore.
    """
    return json.dumps(
        [make_disc_key(disc) for disc in row_discs],
        sort_keys=True,
        ensure_ascii=False,
    )


def click_grid_position(window, config, row_number: int, col_number: int):
    """
    row_number and col_number are 1-based.
    """
    base_left = window.left
    base_top = window.top

    first_x = config["first_x"]
    first_y = config["first_y"]
    x_step = config["x_step"]
    y_step = config["y_step"]

    row_index = row_number - 1
    col_index = col_number - 1

    x = base_left + first_x + col_index * x_step
    y = base_top + first_y + row_index * y_step

    pydirectinput.moveTo(x, y)
    time.sleep(config.get("input_settle_delay", 0.05))
    pydirectinput.click()

    return x, y


def format_scan_timing(timings: dict) -> str:
    fields = timings.get("fields", {})
    field_parts = [
        f"{field_name}={field_timing.get('total', 0):.3f}s"
        for field_name, field_timing in fields.items()
    ]
    field_summary = ", ".join(field_parts)

    return (
        f"capture={timings.get('capture', 0):.3f}s "
        f"ocr={timings.get('ocr_total', 0):.3f}s "
        f"parse={timings.get('parse', 0):.3f}s "
        f"total={timings.get('total', 0):.3f}s"
        + (f" fields=[{field_summary}]" if field_summary else "")
    )


def summarize_scan_timings(timings: list[dict]) -> dict:
    if not timings:
        return {}

    count = len(timings)
    return {
        "count": count,
        "capture": sum(timing.get("capture", 0) for timing in timings) / count,
        "ocr_total": sum(timing.get("ocr_total", 0) for timing in timings) / count,
        "parse": sum(timing.get("parse", 0) for timing in timings) / count,
        "total": sum(timing.get("total", 0) for timing in timings) / count,
    }


def scan_row_to_memory(window, config, row_number: int, label: str) -> list[dict]:
    """
    Scans one visual row and returns it in memory.
    Does NOT save to JSON.
    """
    columns = config["columns"]
    click_delay = config.get("click_delay", 1.0)

    row_started_at = perf_counter()
    row_discs = []
    row_timings = []

    logger.info("Scanning row to memory: %s, visual row %s", label, row_number)

    for col_number in range(1, columns + 1):
        logger.info("Clicking row=%s, col=%s", row_number, col_number)

        click_started_at = perf_counter()
        click_grid_position(
            window=window,
            config=config,
            row_number=row_number,
            col_number=col_number,
        )
        click_elapsed = perf_counter() - click_started_at

        wait_started_at = perf_counter()
        time.sleep(click_delay)
        wait_elapsed = perf_counter() - wait_started_at

        disc, scan_timings = scan_current_disc(
            window=window,
            return_timing=True,
        )
        row_timings.append(scan_timings)

        disc["scan_mode"] = "row_compare_auto_stop"
        disc["visual_row"] = row_number
        disc["visual_col"] = col_number
        disc["scan_label"] = label

        row_discs.append(disc)

        logger.info(
            "Read: %s | slot=%s | level=%s | click=%.3fs wait=%.3fs %s",
            disc.get("disc_name"),
            disc.get("slot"),
            disc.get("level"),
            click_elapsed,
            wait_elapsed,
            format_scan_timing(scan_timings),
        )

    row_summary = summarize_scan_timings(row_timings)
    logger.info(
        "Finished row %s (%s): discs=%s elapsed=%.3fs avg_capture=%.3fs avg_ocr=%.3fs avg_parse=%.3fs avg_scan_total=%.3fs",
        row_number,
        label,
        len(row_discs),
        perf_counter() - row_started_at,
        row_summary.get("capture", 0),
        row_summary.get("ocr_total", 0),
        row_summary.get("parse", 0),
        row_summary.get("total", 0),
    )

    return row_discs


def commit_row(row_discs: list[dict], data: list, existing_keys: set, label: str) -> int:
    """
    Saves one row to JSON, skipping individual duplicate discs.
    """
    started_at = perf_counter()
    added_count = 0

    logger.info("Committing row: %s", label)

    for disc in row_discs:
        key = make_disc_key(disc)

        if key in existing_keys:
            logger.info("Duplicate disc detected during commit, skipping.")
            continue

        existing_keys.add(key)

        disc["scan_index"] = len(data)
        data.append(disc)
        added_count += 1

        logger.info(
            "Saved #%s: %s | slot=%s | level=%s",
            disc["scan_index"],
            disc.get("disc_name"),
            disc.get("slot"),
            disc.get("level"),
        )

    save_data(data)

    logger.info("Committed %s new discs in %.3fs.", added_count, perf_counter() - started_at)
    return added_count


def trigger_game_scroll(window, config):
    """
    Clicks the bottom displayed row to let ZZZ auto-scroll down by itself.
    We only use this as a scroll trigger.
    """
    trigger_row = config.get("scroll_trigger_row", 4)
    trigger_col = config.get("scroll_trigger_col", 1)
    scroll_delay = config.get("auto_scroll_delay", 1.0)

    logger.info(
        "Triggering auto-scroll by clicking row=%s, col=%s",
        trigger_row,
        trigger_col,
    )

    started_at = perf_counter()
    click_grid_position(
        window=window,
        config=config,
        row_number=trigger_row,
        col_number=trigger_col,
    )

    time.sleep(scroll_delay)
    logger.info("Auto-scroll trigger completed in %.3fs.", perf_counter() - started_at)


def main():
    configure_logging()
    config = load_grid_config()
    data = load_existing_data()
    existing_keys = {make_disc_key(disc) for disc in data}

    window = find_zzz_window()
    activate_window(window)

    initial_scan_rows = config.get("initial_scan_rows", [1, 2, 3])
    scan_after_scroll_row = config.get("scan_after_scroll_row", 3)
    max_auto_scroll_cycles = config.get("max_auto_scroll_cycles", 300)

    logger.info("Starting row-compare auto-stop scan.")
    logger.info("Initial scan rows: %s", initial_scan_rows)
    logger.info("After each auto-scroll, scan visual row: %s", scan_after_scroll_row)
    logger.info("Max auto-scroll cycles: %s", max_auto_scroll_cycles)

    # First, commit the initial visible safe rows.
    for row_number in initial_scan_rows:
        row = scan_row_to_memory(
            window=window,
            config=config,
            row_number=row_number,
            label=f"initial_row_{row_number}",
        )

        commit_row(
            row_discs=row,
            data=data,
            existing_keys=existing_keys,
            label=f"initial_row_{row_number}",
        )

    # Now use row comparison:
    # previous_row is not committed immediately.
    # We only commit it after confirming the next row is different.
    trigger_game_scroll(window, config)

    previous_row = scan_row_to_memory(
        window=window,
        config=config,
        row_number=scan_after_scroll_row,
        label="row_buffer_1",
    )

    for cycle in range(2, max_auto_scroll_cycles + 1):
        logger.info("Row-compare cycle %s/%s", cycle, max_auto_scroll_cycles)

        trigger_game_scroll(window, config)

        current_row = scan_row_to_memory(
            window=window,
            config=config,
            row_number=scan_after_scroll_row,
            label=f"row_buffer_{cycle}",
        )

        previous_key = make_row_key(previous_row)
        current_key = make_row_key(current_row)

        if current_key == previous_key:
            logger.info("Current row is the same as previous row.")
            logger.info("Reached the end. Committing previous row once, then stopping.")

            commit_row(
                row_discs=previous_row,
                data=data,
                existing_keys=existing_keys,
                label="final_previous_row",
            )

            break

        logger.info("Current row is different from previous row.")
        logger.info("Committing previous row and continuing.")

        commit_row(
            row_discs=previous_row,
            data=data,
            existing_keys=existing_keys,
            label=f"confirmed_row_{cycle - 1}",
        )

        previous_row = current_row

    else:
        logger.info("Reached max_auto_scroll_cycles.")
        logger.info("Committing last buffered row before stopping.")

        commit_row(
            row_discs=previous_row,
            data=data,
            existing_keys=existing_keys,
            label="last_buffered_row",
        )

    logger.info("Done. Saved %s unique discs to %s", len(data), OUTPUT_PATH)


if __name__ == "__main__":
    main()

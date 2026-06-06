import json
import logging
import os
import re
import time
from functools import lru_cache
from time import perf_counter

import pydirectinput

from src.app_logging import configure_logging
from src.capture_window import capture_existing_window
from src.capture_window import find_zzz_window, activate_window
from src.coordinate_scaling import maybe_scale_config_for_window
from src.paths import GRID_CONFIG_PATH, OUTPUT_DIR, SCANNED_DISCS_PATH
from src.scan_disc import load_rois, maybe_scale_rois_for_image, ocr_crop, scan_current_disc
from src.text_parser import load_drive_disc_names

OUTPUT_PATH = SCANNED_DISCS_PATH
logger = logging.getLogger("zzz_scanner.scan_by_rows")
pydirectinput.PAUSE = 0


def load_grid_config() -> dict:
    with open(GRID_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_existing_data() -> list:
    if not OUTPUT_PATH.exists():
        return []

    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: list):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def parse_disc_count(text: str) -> int | None:
    """
    Parses an inventory count OCR result.

    For capacity-style text such as "1234/3000", the first number is the
    owned disc count and the second is inventory capacity.
    """
    numbers = re.findall(r"\d+", text or "")

    if not numbers:
        return None

    return int(numbers[0])


def read_total_disc_count(window, config) -> int | None:
    manual_total = config.get("expected_total_discs")

    if isinstance(manual_total, int) and manual_total > 0:
        logger.info("Using configured expected_total_discs=%s.", manual_total)
        return manual_total

    count_roi = config.get("inventory_count_roi")

    if not count_roi:
        logger.info(
            "No expected_total_discs or inventory_count_roi configured; using row-compare stop only."
        )
        return None

    screenshot = capture_existing_window(window)
    text, timing = ocr_crop(
        image=screenshot,
        roi=count_roi,
        field_name="disc_count",
        debug_name="inventory_count_roi",
    )
    total = parse_disc_count(text)

    if total is None:
        logger.warning(
            "Could not parse total disc count from OCR text %r; using row-compare stop only.",
            text,
        )
        return None

    logger.info(
        "Detected total disc count: %s from OCR text %r in %.3fs.",
        total,
        text,
        timing.get("total", 0),
    )
    return total


def reached_total_disc_count(data: list, total_disc_count: int | None) -> bool:
    return total_disc_count is not None and len(data) >= total_disc_count


@lru_cache(maxsize=1)
def valid_drive_disc_names() -> frozenset[str]:
    return frozenset(load_drive_disc_names())


def is_known_disc_name(disc: dict) -> bool:
    return disc.get("disc_name") in valid_drive_disc_names()


def save_unknown_disc_debug_crops(window, row_number: int, col_number: int, label: str):
    screenshot = capture_existing_window(window)
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", label)
    debug_prefix = f"unknown_disc_{safe_label}_r{row_number}_c{col_number}"

    for field_name, roi in maybe_scale_rois_for_image(load_rois(), screenshot).items():
        debug_name = f"{debug_prefix}_{field_name}"
        text, timing = ocr_crop(
            image=screenshot,
            roi=roi,
            field_name=field_name,
            debug_name=debug_name,
        )
        logger.error(
            "Unknown-disc debug OCR field=%s text=%r elapsed=%.3fs files=%s_raw.png/%s_processed.png",
            field_name,
            text,
            timing.get("total", 0),
            debug_name,
            debug_name,
        )


def validate_known_disc_name(disc: dict, row_number: int, col_number: int, label: str):
    if is_known_disc_name(disc):
        return

    disc_name = disc.get("disc_name")
    raw_ocr = disc.get("raw_ocr", {})
    raw_name = raw_ocr.get("disc_name", "")

    logger.error(
        "Stopping scan: could not resolve a known Drive Disc set name at row=%s col=%s label=%s. "
        "parsed_name=%r raw_disc_name_ocr=%r raw_ocr=%s",
        row_number,
        col_number,
        label,
        disc_name,
        raw_name,
        json.dumps(raw_ocr, ensure_ascii=False),
    )

    raise RuntimeError(
        "Could not resolve a known Drive Disc set name. "
        f"row={row_number} col={col_number} label={label} raw_disc_name_ocr={raw_name!r}"
    )


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


def get_row_crop_bounds(config: dict, row_number: int) -> tuple[int, int, int, int]:
    columns = config["columns"]
    first_x = config["first_x"]
    first_y = config["first_y"]
    x_step = config["x_step"]
    y_step = config["y_step"]

    row_index = row_number - 1
    left = max(0, first_x - x_step // 2)
    top = max(0, first_y + row_index * y_step - y_step // 2)
    right = first_x + (columns - 1) * x_step + x_step // 2
    bottom = first_y + row_index * y_step + y_step // 2

    return left, top, right, bottom


def make_row_visual_key(window, config: dict, row_number: int) -> tuple[int, ...]:
    screenshot = capture_existing_window(window)
    bounds = get_row_crop_bounds(config, row_number)
    crop = screenshot.crop(bounds).convert("L").resize((96, 16))
    pixels = list(crop.getdata())
    average = sum(pixels) / len(pixels)
    return tuple(1 if pixel >= average else 0 for pixel in pixels)


def row_visual_distance(left_key: tuple[int, ...], right_key: tuple[int, ...]) -> int:
    return sum(left_bit != right_bit for left_bit, right_bit in zip(left_key, right_key))


def is_same_visual_row(left_key: tuple[int, ...], right_key: tuple[int, ...], config: dict) -> bool:
    threshold = config.get("row_visual_compare_threshold", 24)
    return row_visual_distance(left_key, right_key) <= threshold


def format_scan_timing(timings: dict) -> str:
    fields = timings.get("fields", {})
    field_parts = [
        (
            f"{field_name}={field_timing.get('total', 0):.3f}s"
            + (
                f":{field_timing.get('variant')}"
                if field_timing.get("variant")
                else ""
            )
        )
        for field_name, field_timing in fields.items()
    ]
    field_summary = ", ".join(field_parts)

    return (
        f"ocr_mode={timings.get('mode', 'unknown')} "
        f"workers={timings.get('workers', 0)} "
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

        if config.get("stop_on_unknown_disc_name", True):
            if not is_known_disc_name(disc):
                save_unknown_disc_debug_crops(
                    window=window,
                    row_number=row_number,
                    col_number=col_number,
                    label=label,
                )

            validate_known_disc_name(
                disc=disc,
                row_number=row_number,
                col_number=col_number,
                label=label,
            )

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
    config = maybe_scale_config_for_window(config, window)
    total_disc_count = read_total_disc_count(window, config)

    initial_scan_rows = config.get("initial_scan_rows", [1, 2, 3])
    scan_after_scroll_row = config.get("scan_after_scroll_row", 3)
    max_auto_scroll_cycles = config.get("max_auto_scroll_cycles", 300)

    logger.info("Starting row-compare auto-stop scan.")
    logger.info("Initial scan rows: %s", initial_scan_rows)
    logger.info("After each auto-scroll, scan visual row: %s", scan_after_scroll_row)
    logger.info("Max auto-scroll cycles: %s", max_auto_scroll_cycles)
    if total_disc_count is not None:
        logger.info(
            "Count-based stop enabled: current=%s target=%s",
            len(data),
            total_disc_count,
        )

        if reached_total_disc_count(data, total_disc_count):
            logger.info("Existing output already reached the total disc count. Nothing to scan.")
            return

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

        if reached_total_disc_count(data, total_disc_count):
            logger.info(
                "Reached total disc count after initial row %s: %s/%s. Stopping.",
                row_number,
                len(data),
                total_disc_count,
            )
            return

    # Now use row comparison:
    # previous_row is not committed immediately.
    # We only commit it after confirming the next row is different.
    trigger_game_scroll(window, config)
    previous_visual_key = make_row_visual_key(window, config, scan_after_scroll_row)

    previous_row = scan_row_to_memory(
        window=window,
        config=config,
        row_number=scan_after_scroll_row,
        label="row_buffer_1",
    )

    for cycle in range(2, max_auto_scroll_cycles + 1):
        logger.info("Row-compare cycle %s/%s", cycle, max_auto_scroll_cycles)

        trigger_game_scroll(window, config)
        current_visual_key = make_row_visual_key(window, config, scan_after_scroll_row)
        visual_distance = row_visual_distance(previous_visual_key, current_visual_key)
        logger.info(
            "Visual row %s compare distance after scroll: %s",
            scan_after_scroll_row,
            visual_distance,
        )

        if is_same_visual_row(previous_visual_key, current_visual_key, config):
            logger.info(
                "Visual row %s did not change after scroll; reached the end.",
                scan_after_scroll_row,
            )
            logger.info("Committing previous row, scanning the final visible row, then stopping.")

            commit_row(
                row_discs=previous_row,
                data=data,
                existing_keys=existing_keys,
                label="final_previous_row",
            )

            if reached_total_disc_count(data, total_disc_count):
                logger.info(
                    "Reached total disc count before final visible row scan: %s/%s. Stopping.",
                    len(data),
                    total_disc_count,
                )
                break

            final_row_number = config.get("final_scan_row", config.get("scroll_trigger_row", 4))
            final_row = scan_row_to_memory(
                window=window,
                config=config,
                row_number=final_row_number,
                label="final_visible_row",
            )
            commit_row(
                row_discs=final_row,
                data=data,
                existing_keys=existing_keys,
                label="final_visible_row",
            )

            break

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
            logger.info(
                "Reached the end. Committing previous row, scanning the final visible row, then stopping."
            )

            commit_row(
                row_discs=previous_row,
                data=data,
                existing_keys=existing_keys,
                label="final_previous_row",
            )

            if reached_total_disc_count(data, total_disc_count):
                logger.info(
                    "Reached total disc count before final visible row scan: %s/%s. Stopping.",
                    len(data),
                    total_disc_count,
                )
                break

            final_row_number = config.get("final_scan_row", config.get("scroll_trigger_row", 4))
            final_row = scan_row_to_memory(
                window=window,
                config=config,
                row_number=final_row_number,
                label="final_visible_row",
            )
            commit_row(
                row_discs=final_row,
                data=data,
                existing_keys=existing_keys,
                label="final_visible_row",
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

        if reached_total_disc_count(data, total_disc_count):
            logger.info(
                "Reached total disc count after cycle %s: %s/%s. Stopping.",
                cycle,
                len(data),
                total_disc_count,
            )
            break

        previous_row = current_row
        previous_visual_key = current_visual_key

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

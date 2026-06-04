import json
import os
import time
import pydirectinput

from capture_window import find_zzz_window, activate_window
from scan_disc import scan_current_disc

GRID_CONFIG_PATH = "config/grid_config.json"
OUTPUT_PATH = "output/scanned_discs.json"


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
    time.sleep(0.15)
    pydirectinput.click()

    return x, y


def scan_row_to_memory(window, config, row_number: int, label: str) -> list[dict]:
    """
    Scans one visual row and returns it in memory.
    Does NOT save to JSON.
    """
    columns = config["columns"]
    click_delay = config.get("click_delay", 1.0)

    row_discs = []

    print(f"\n--- Scanning row to memory: {label}, visual row {row_number} ---")

    for col_number in range(1, columns + 1):
        print(f"Clicking row={row_number}, col={col_number}")

        click_grid_position(
            window=window,
            config=config,
            row_number=row_number,
            col_number=col_number,
        )

        time.sleep(click_delay)

        disc = scan_current_disc()

        disc["scan_mode"] = "row_compare_auto_stop"
        disc["visual_row"] = row_number
        disc["visual_col"] = col_number
        disc["scan_label"] = label

        row_discs.append(disc)

        print(
            f"Read: {disc.get('disc_name')} | "
            f"slot={disc.get('slot')} | "
            f"level={disc.get('level')}"
        )

    return row_discs


def commit_row(row_discs: list[dict], data: list, existing_keys: set, label: str) -> int:
    """
    Saves one row to JSON, skipping individual duplicate discs.
    """
    added_count = 0

    print(f"\nCommitting row: {label}")

    for disc in row_discs:
        key = make_disc_key(disc)

        if key in existing_keys:
            print("Duplicate disc detected during commit, skipping.")
            continue

        existing_keys.add(key)

        disc["scan_index"] = len(data)
        data.append(disc)
        added_count += 1

        print(
            f"Saved #{disc['scan_index']}: "
            f"{disc.get('disc_name')} | "
            f"slot={disc.get('slot')} | "
            f"level={disc.get('level')}"
        )

    save_data(data)

    print(f"Committed {added_count} new discs.")
    return added_count


def trigger_game_scroll(window, config):
    """
    Clicks the bottom displayed row to let ZZZ auto-scroll down by itself.
    We only use this as a scroll trigger.
    """
    trigger_row = config.get("scroll_trigger_row", 4)
    trigger_col = config.get("scroll_trigger_col", 1)
    scroll_delay = config.get("auto_scroll_delay", 1.0)

    print(f"\nTriggering auto-scroll by clicking row={trigger_row}, col={trigger_col}")

    click_grid_position(
        window=window,
        config=config,
        row_number=trigger_row,
        col_number=trigger_col,
    )

    time.sleep(scroll_delay)


def main():
    config = load_grid_config()
    data = load_existing_data()
    existing_keys = {make_disc_key(disc) for disc in data}

    window = find_zzz_window()
    activate_window(window)

    initial_scan_rows = config.get("initial_scan_rows", [1, 2, 3])
    scan_after_scroll_row = config.get("scan_after_scroll_row", 3)
    max_auto_scroll_cycles = config.get("max_auto_scroll_cycles", 300)

    print("Starting row-compare auto-stop scan.")
    print(f"Initial scan rows: {initial_scan_rows}")
    print(f"After each auto-scroll, scan visual row: {scan_after_scroll_row}")
    print(f"Max auto-scroll cycles: {max_auto_scroll_cycles}")

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
        print(f"\n=== Row-compare cycle {cycle}/{max_auto_scroll_cycles} ===")

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
            print("\nCurrent row is the same as previous row.")
            print("Reached the end. Committing previous row once, then stopping.")

            commit_row(
                row_discs=previous_row,
                data=data,
                existing_keys=existing_keys,
                label="final_previous_row",
            )

            break

        print("\nCurrent row is different from previous row.")
        print("Committing previous row and continuing.")

        commit_row(
            row_discs=previous_row,
            data=data,
            existing_keys=existing_keys,
            label=f"confirmed_row_{cycle - 1}",
        )

        previous_row = current_row

    else:
        print("\nReached max_auto_scroll_cycles.")
        print("Committing last buffered row before stopping.")

        commit_row(
            row_discs=previous_row,
            data=data,
            existing_keys=existing_keys,
            label="last_buffered_row",
        )

    print(f"\nDone. Saved {len(data)} unique discs to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

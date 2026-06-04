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


def scan_row(window, config, row_number: int, data: list, existing_keys: set, label: str):
    columns = config["columns"]
    click_delay = config.get("click_delay", 1.0)

    added_count = 0

    print(f"\n--- Scanning {label}, visual row {row_number} ---")

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
        key = make_disc_key(disc)

        if key in existing_keys:
            print("Duplicate detected, skipping.")
            continue

        existing_keys.add(key)

        disc["scan_index"] = len(data)
        disc["scan_mode"] = "bottom_trigger_scroll"
        disc["visual_row"] = row_number
        disc["visual_col"] = col_number
        disc["scan_label"] = label

        data.append(disc)
        save_data(data)
        added_count += 1

        print(
            f"Saved #{disc['scan_index']}: "
            f"{disc.get('disc_name')} | slot={disc.get('slot')} | level={disc.get('level')}"
        )

    return added_count


def trigger_game_scroll(window, config):
    """
    Clicks the bottom displayed row to let ZZZ auto-scroll down by itself.

    We only click col 1 on the bottom row because we are not trying to scan it here.
    We just use it to move the inventory down.
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
    auto_scroll_cycles = config.get("auto_scroll_cycles", 5)

    print("Starting bottom-trigger scroll scan.")
    print(f"Initial scan rows: {initial_scan_rows}")
    print(f"After each auto-scroll, scan visual row: {scan_after_scroll_row}")
    print(f"Auto-scroll cycles: {auto_scroll_cycles}")

    # Initial top scan.
    # At the top, rows 1, 2, 3 are safe and cover the first visible discs.
    for row_number in initial_scan_rows:
        scan_row(
            window=window,
            config=config,
            row_number=row_number,
            data=data,
            existing_keys=existing_keys,
            label=f"initial_row_{row_number}",
        )

    # Main loop:
    # click bottom row to make the game auto-scroll,
    # then scan row 3, which should now contain the newly revealed row.
    for cycle in range(auto_scroll_cycles):
        print(f"\n=== Auto-scroll cycle {cycle + 1}/{auto_scroll_cycles} ===")

        trigger_game_scroll(window, config)

        added = scan_row(
            window=window,
            config=config,
            row_number=scan_after_scroll_row,
            data=data,
            existing_keys=existing_keys,
            label=f"after_scroll_cycle_{cycle + 1}_row_{scan_after_scroll_row}",
        )

        print(f"Cycle {cycle + 1} added {added} new discs.")

    print(f"\nDone. Saved {len(data)} unique discs to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

from src.text_parser import (
    build_disc_json,
    extract_slot_from_disc_text,
    parse_substat_line,
)


def assert_equal(actual, expected):
    if actual != expected:
        raise AssertionError(f"Expected {expected!r}, got {actual!r}")


def main():
    malformed_def = parse_substat_line("DEF 1\u00a7")
    assert_equal(malformed_def["stat"], "DEF")
    assert_equal(malformed_def["upgrade_count"], 0)
    assert_equal(malformed_def["value"], "15")

    mojibake_def = parse_substat_line("DEF 1\u00c2\u00a7")
    assert_equal(mojibake_def["stat"], "DEF")
    assert_equal(mojibake_def["upgrade_count"], 0)
    assert_equal(mojibake_def["value"], "15")

    normal_atk = parse_substat_line("ATK +1 6%")
    assert_equal(normal_atk["stat"], "ATK")
    assert_equal(normal_atk["upgrade_count"], 1)
    assert_equal(normal_atk["value"], "6%")

    failed_value = parse_substat_line("DEF ???")
    assert_equal(failed_value["stat"], "DEF")
    assert_equal(failed_value["upgrade_count"], 0)
    assert_equal(failed_value["value"], None)

    assert_equal(extract_slot_from_disc_text("White Water Ballad [S]"), 5)
    assert_equal(extract_slot_from_disc_text("White Water Ballad [\u00a7]"), 5)
    assert_equal(extract_slot_from_disc_text("White Water Ballad [\u00c2\u00a7]"), 5)
    assert_equal(extract_slot_from_disc_text("White Water Ballad [I]"), 1)

    inferred_slot = build_disc_json(
        {
            "disc_name": "White Water",
            "main_stat": "CRIT DMG 48%",
            "level": "Lv.15/15",
            "substats": "",
        }
    )
    assert_equal(inferred_slot["disc_name"], "White Water Ballad")
    assert_equal(inferred_slot["slot"], 4)

    print("text parser checks passed")


if __name__ == "__main__":
    main()

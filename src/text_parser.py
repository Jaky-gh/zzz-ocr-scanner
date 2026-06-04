import json
import os
import re
from difflib import get_close_matches


DRIVE_DISC_NAMES_PATH = "config/drive_disc_names.json"


def load_drive_disc_names() -> list[str]:
    if not os.path.exists(DRIVE_DISC_NAMES_PATH):
        raise RuntimeError(
            f"Missing {DRIVE_DISC_NAMES_PATH}. "
            "Create it with the list of valid Drive Disc names."
        )

    with open(DRIVE_DISC_NAMES_PATH, "r", encoding="utf-8") as f:
        names = json.load(f)

    if not isinstance(names, list):
        raise RuntimeError(f"{DRIVE_DISC_NAMES_PATH} must contain a JSON list.")

    return names


def clean_text(text: str | None) -> str:
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\r", "\n")
    text = text.replace("％", "%")
    text = text.replace("|", "I")
    text = re.sub(r"\n+", "\n", text)
    text = text.strip()

    return text


def normalize_spaces(text: str) -> str:
    text = clean_text(text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_slot_from_disc_text(text: str) -> int | None:
    """
    Extracts the slot from the Drive Disc name OCR.

    We assume the only meaningful number in the name OCR is the slot.
    Examples:
    - "White Water Ballad [1]" -> 1
    - "Yunkui Tales [3" -> 3
    - "Swing Jazz 5" -> 5
    """
    text = normalize_spaces(text)

    digits = re.findall(r"\d", text)

    if not digits:
        return None

    slot = int(digits[-1])

    if 1 <= slot <= 6:
        return slot

    return None


def raw_name_candidate_from_disc_text(text: str) -> str:
    """
    Removes the slot suffix from the OCR disc name.

    Examples:
    - "White Water Ballad [1]" -> "White Water Ballad"
    - "Yunkui Tales [3" -> "Yunkui Tales"
    - "Swing Jazz 5" -> "Swing Jazz"
    """
    text = normalize_spaces(text)

    if not text:
        return ""

    # Main case: remove everything from the last "[" onward.
    # "Yunkui Tales [3" -> "Yunkui Tales"
    if "[" in text:
        text = text[: text.rfind("[")].strip()
        return text

    # Fallback: OCR missed "[", remove trailing slot number.
    # "Yunkui Tales 3" -> "Yunkui Tales"
    text = re.sub(r"\s+\d\s*$", "", text).strip()

    return text


def normalize_disc_name(text: str) -> str:
    """
    Normalizes the OCR disc name against config/drive_disc_names.json.

    This makes the output homogeneous even if OCR has small mistakes.
    """
    candidate = raw_name_candidate_from_disc_text(text)

    if not candidate:
        return ""

    drive_disc_names = load_drive_disc_names()

    # Exact case-insensitive match first.
    for name in drive_disc_names:
        if candidate.lower() == name.lower():
            return name

    # Containment match.
    # Useful if OCR captured extra characters around the real name.
    for name in drive_disc_names:
        if name.lower() in candidate.lower():
            return name

    # Fuzzy match fallback.
    matches = get_close_matches(
        candidate,
        drive_disc_names,
        n=1,
        cutoff=0.65,
    )

    if matches:
        return matches[0]

    # Final fallback: return cleaned OCR text.
    return candidate


def parse_disc_name_and_slot(text: str) -> tuple[str, int | None]:
    disc_name = normalize_disc_name(text)
    slot = extract_slot_from_disc_text(text)

    return disc_name, slot


def parse_level(text: str) -> int | None:
    text = clean_text(text)

    # Example: Lv. 15/15
    match = re.search(r"Lv\.?\s*(\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # Fallback: +15 or 15
    match = re.search(r"\+?\s*(\d+)", text)
    if match:
        return int(match.group(1))

    return None


def normalize_stat_name(stat_name: str) -> str:
    stat_name = normalize_spaces(stat_name)
    stat_name = stat_name.strip(" :+-,")

    known_stats = [
        "CRIT Rate",
        "CRIT DMG",
        "Anomaly Proficiency",
        "Anomaly Mastery",
        "Energy Regen",
        "PEN Ratio",
        "Physical DMG Bonus",
        "Fire DMG Bonus",
        "Ice DMG Bonus",
        "Electric DMG Bonus",
        "Ether DMG Bonus",
        "HP",
        "ATK",
        "DEF",
        "PEN",
    ]

    for known in known_stats:
        if known.lower() in stat_name.lower():
            return known

    matches = get_close_matches(
        stat_name,
        known_stats,
        n=1,
        cutoff=0.7,
    )

    if matches:
        return matches[0]

    return stat_name


def parse_main_stat(text: str) -> dict | None:
    text = normalize_spaces(text)

    if not text:
        return None

    # Examples:
    # HP 2,200
    # CRIT Rate 24%
    # Fire DMG Bonus 30%
    match = re.search(r"(.+?)\s+([\d,]+(?:\.\d+)?%?)$", text)

    if not match:
        return {
            "stat": normalize_stat_name(text),
            "value": None,
            "raw": text,
        }

    stat_name = normalize_stat_name(match.group(1))
    value = match.group(2).replace(",", "")

    return {
        "stat": stat_name,
        "value": value,
        "raw": text,
    }


def parse_substat_line(line: str) -> dict | None:
    line = normalize_spaces(line)

    if not line:
        return None

    # Examples:
    # CRIT Rate +1 4.8%
    # CRIT DMG +1 9.6%
    # ATK +2 9%
    # HP 3%
    match = re.search(
        r"(.+?)(?:\s+\+(\d+))?\s+([\d,]+(?:\.\d+)?%?)$",
        line,
    )

    if not match:
        return {
            "stat": normalize_stat_name(line),
            "upgrade_count": None,
            "value": None,
            "raw": line,
        }

    stat_name = normalize_stat_name(match.group(1))
    upgrade_count = int(match.group(2)) if match.group(2) else 0
    value = match.group(3).replace(",", "")

    return {
        "stat": stat_name,
        "upgrade_count": upgrade_count,
        "value": value,
        "raw": line,
    }


def parse_substats(text: str) -> list[dict]:
    text = clean_text(text)

    lines = [
        normalize_spaces(line)
        for line in text.splitlines()
        if normalize_spaces(line)
    ]

    substats = []

    for line in lines:
        parsed = parse_substat_line(line)

        if parsed:
            substats.append(parsed)

    return substats


def build_disc_json(ocr_results: dict) -> dict:
    disc_name, slot = parse_disc_name_and_slot(
        ocr_results.get("disc_name", "")
    )

    return {
        "disc_name": disc_name,
        "slot": slot,
        "main_stat": parse_main_stat(ocr_results.get("main_stat", "")),
        "level": parse_level(ocr_results.get("level", "")),
        "substats": parse_substats(ocr_results.get("substats", "")),
        "raw_ocr": ocr_results,
    }

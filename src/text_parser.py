import re


def clean_text(text: str) -> str:
    if text is None:
        return ""

    text = text.replace("\r", "\n")
    text = text.replace("％", "%")
    text = text.replace("|", "I")
    text = re.sub(r"\n+", "\n", text)
    text = text.strip()

    return text


def parse_level(text: str) -> int | None:
    text = clean_text(text)

    match = re.search(r"Lv\.?\s*(\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    match = re.search(r"\+?\s*(\d+)", text)
    if match:
        return int(match.group(1))

    return None


def parse_slot(text: str) -> int | str | None:
    text = clean_text(text)

    match = re.search(r"\d+", text)
    if match:
        return int(match.group(0))

    return text or None


def normalize_stat_name(stat_name: str) -> str:
    stat_name = clean_text(stat_name)
    stat_name = re.sub(r"\s+", " ", stat_name)
    stat_name = stat_name.strip(" :+-,")

    replacements = {
        "CRIT Rate": "CRIT Rate",
        "CRIT DMG": "CRIT DMG",
        "ATK": "ATK",
        "DEF": "DEF",
        "HP": "HP",
        "PEN": "PEN",
    }

    for key, value in replacements.items():
        if key.lower() in stat_name.lower():
            return value

    return stat_name


def parse_main_stat(text: str) -> dict | None:
    text = clean_text(text)

    if not text:
        return None

    # Example: HP 2,200
    # Example: CRIT Rate 24%
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
    line = clean_text(line)

    if not line:
        return None

    # Example: CRIT Rate +1 4.8%
    # Example: ATK +2 9%
    # Example: HP 3%
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
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    return [
        parsed
        for line in lines
        if (parsed := parse_substat_line(line)) is not None
    ]


def build_disc_json(ocr_results: dict) -> dict:
    return {
        "disc_name": clean_text(ocr_results.get("disc_name", "")).replace("\n", " "),
        "slot": parse_slot(ocr_results.get("slot", "")),
        "main_stat": parse_main_stat(ocr_results.get("main_stat", "")),
        "level": parse_level(ocr_results.get("level", "")),
        "substats": parse_substats(ocr_results.get("substats", "")),
        "raw_ocr": ocr_results,
    }

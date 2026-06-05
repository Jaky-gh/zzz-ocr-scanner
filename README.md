# ZZZ OCR Scanner

Small OCR scanner for exporting Zenless Zone Zero Drive Disc inventory data.

The tool uses screenshots, calibrated UI regions, and Tesseract OCR to read disc
details from the game inventory. It is intended as a read-only inventory exporter:
it does not modify game files, access game memory, bypass anti-cheat, or automate
gameplay/rewards.

## Setup

Install Python dependencies:

```powershell
.\venv\Scripts\pip.exe install -r requirements.txt
```

Install Tesseract OCR and update this path in `src/scan_disc.py` if needed:

```python
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

## Calibration

Run grid calibration first:

```powershell
.\venv\Scripts\python.exe -m src.calibrate.calibrate_grid
```

Then run ROI calibration:

```powershell
.\venv\Scripts\python.exe -m src.calibrate.calibrate_rois
```

The ROI calibration can also save an optional inventory count ROI used for
count-based stopping. Select the count text such as `1234/3000` when prompted.

## Scanning

Start the row scanner:

```powershell
.\venv\Scripts\python.exe src\scan_by_rows.py
```

Output is written to:

```text
output/scanned_discs.json
```

Logs are written to:

```text
output/scanner.log
```

## Speed Tuning

Timing values live in `config/grid_config.json`:

```json
"click_delay": 0.35,
"input_settle_delay": 0.05,
"auto_scroll_delay": 0.6
```

If scans sometimes read the previous selected disc, increase `click_delay`.

OCR fields run in parallel by default. To compare worker counts:

```powershell
$env:ZZZ_OCR_WORKERS=1
.\venv\Scripts\python.exe src\scan_by_rows.py
```

## Stop Conditions

The scanner stops when the row-compare logic detects the end of the inventory.

Optionally, set `expected_total_discs` in `config/grid_config.json`, or calibrate
`inventory_count_roi`, to stop once the output reaches the known disc count.

If count OCR fails, debug images are saved:

```text
output/inventory_count_roi_raw.png
output/inventory_count_roi_processed.png
```

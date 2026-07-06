"""
Converts the real multi-year hourly Electricity Maps CSV exports in
data/raw_yearly/ into one merged data/history/ci_history_{zone}.json per
zone, in the same {"datetime", "carbonIntensity", "isEstimated"} shape the
API's /history endpoint produces, so the existing forecaster/LSTM pipeline
can consume either source unchanged.

Multiple per-zone files (e.g. one per year: ...-2021-hourly.csv,
...-2022-hourly.csv, ...) are concatenated and de-duplicated by datetime,
sorted chronologically into a single continuous series.

Run from carbon_scheduler/: python scripts/import_yearly_csv.py
"""
import csv
import glob
import json
import os
import sys
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

RAW_DIR = os.path.join(config.DATA_DIR, "raw_yearly")
OUT_DIR = os.path.join(config.DATA_DIR, "history")


def read_file(path: str) -> tuple:
    records = []
    zone = None
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            zone = zone or row["Zone id"]
            ci = row["Carbon intensity gCO₂eq/kWh (Life cycle)"]
            if not ci:
                continue
            records.append({
                "zone": zone,
                "datetime": row["Datetime (UTC)"],
                "carbonIntensity": round(float(ci), 2),
                "isEstimated": row["Data estimated"].strip().lower() == "true"
            })
    return zone, records


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    csv_files = sorted(glob.glob(os.path.join(RAW_DIR, "*.csv")))
    if not csv_files:
        print(f"No CSVs found in {RAW_DIR}")
        return

    by_zone = defaultdict(dict)  # zone -> {datetime: record}, dict dedupes by key
    for path in csv_files:
        zone, records = read_file(path)
        for r in records:
            by_zone[zone][r["datetime"]] = r

    for zone, records_by_dt in sorted(by_zone.items()):
        records = sorted(records_by_dt.values(), key=lambda r: r["datetime"])
        out_path = os.path.join(OUT_DIR, f"ci_history_{zone}.json")
        with open(out_path, "w") as f:
            json.dump(records, f)
        estimated = sum(1 for r in records if r["isEstimated"])
        span = f"{records[0]['datetime'][:10]} to {records[-1]['datetime'][:10]}" if records else "n/a"
        print(f"{zone}: {len(records)} hourly records ({estimated} estimated), {span} -> {out_path}")


if __name__ == "__main__":
    main()

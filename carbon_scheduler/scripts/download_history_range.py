"""
Downloads 2026-01-01 -> 2026-09-28 hourly carbon intensity per zone from
Electricity Maps /past-range in 10-day chunks, into
$CADSS_RETRAIN_DIR/history_2026/ (default data/retrain/, gitignored).

Does NOT touch data/history: download_ci_history.py replaces each of those
files with only the trailing 10 days, which would wipe a multi-year import.

Licensed data: keep local, never push.
Run from carbon_scheduler/: python scripts/download_history_range.py
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(REPO)
import config
from services.electricity_service import ElectricityService

URL = "https://api.electricitymaps.com/v3/carbon-intensity/past-range"
WORK = os.environ.get("CADSS_RETRAIN_DIR", os.path.join(config.DATA_DIR, "retrain"))
OUT = os.path.join(WORK, "history_2026")
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 9, 28, 0, tzinfo=timezone.utc)
CHUNK = timedelta(days=10)  # plan limit for hourly past-range data


def fetch(zone, token, a, b):
    params = {"zone": zone, "start": a.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
              "end": b.strftime("%Y-%m-%dT%H:%M:%S.000Z")}
    for attempt in range(4):
        r = requests.get(URL, headers={"auth-token": token}, params=params, timeout=30)
        if r.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json().get("data", [])
    raise RuntimeError("rate limited")


def main():
    os.makedirs(OUT, exist_ok=True)
    token = config.ELECTRICITY_MAPS_TOKEN
    zones = sorted({m["zone"] for m in ElectricityService.REGION_MAP.values()})
    for zone in zones:
        path = os.path.join(OUT, f"ci_2026_{zone}.json")
        if os.path.exists(path):
            print(f"{zone}: exists, skipping")
            continue
        rows = {}
        a = START
        while a < END:
            b = min(a + CHUNK, END)
            for e in fetch(zone, token, a, b):
                if e.get("carbonIntensity") is not None:
                    rows[e["datetime"]] = {"zone": zone, "datetime": e["datetime"],
                                           "carbonIntensity": e["carbonIntensity"],
                                           "isEstimated": bool(e.get("isEstimated"))}
            a = b
            time.sleep(0.5)  # well under the 150 req/min limit
        data = [rows[k] for k in sorted(rows)]
        with open(path, "w") as f:
            json.dump(data, f)
        estimated = sum(1 for d in data if d["isEstimated"])
        print(f"{zone}: saved {len(data)} records ({estimated} estimated) -> {path}")


if __name__ == "__main__":
    main()

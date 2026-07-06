"""
Downloads historical carbon-intensity series from Electricity Maps for each
mapped zone and saves to data/history/ci_history_{zone}.json. Used to
train/fit the LSTM and ARIMA forecasters on real data instead of the
synthetic diurnal generator.

Uses /past-range (real measured data, up to a 10-day window per request)
rather than /history (only ever returns the trailing 24h regardless of
date params on this token's plan).

Run from carbon_scheduler/: python scripts/download_ci_history.py
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from services.electricity_service import ElectricityService

PAST_RANGE_URL = "https://api.electricitymaps.com/v3/carbon-intensity/past-range"
OUT_DIR = os.path.join(config.DATA_DIR, "history")
RANGE_DAYS = 10  # plan limit for hourly past-range data


def download_zone_history(zone: str, token: str) -> list:
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=RANGE_DAYS)
    params = {
        "zone": zone,
        "start": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "end": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }
    resp = requests.get(PAST_RANGE_URL, headers={"auth-token": token}, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("data", [])


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    zones = sorted({meta["zone"] for meta in ElectricityService.REGION_MAP.values()})
    token = config.ELECTRICITY_MAPS_TOKEN

    for zone in zones:
        try:
            history = download_zone_history(zone, token)
            out_path = os.path.join(OUT_DIR, f"ci_history_{zone}.json")
            with open(out_path, "w") as f:
                json.dump(history, f)
            estimated = sum(1 for h in history if h.get("isEstimated"))
            print(f"{zone}: saved {len(history)} records ({estimated} estimated) -> {out_path}")
        except Exception as e:
            print(f"{zone}: FAILED ({e})")


if __name__ == "__main__":
    main()

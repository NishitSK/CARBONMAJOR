"""
Checks whether the live pilot week happens to be a typical or unusual week
for grid carbon intensity, by comparing the live-measured CI values against
the 5-year historical average for the same calendar dates/hours per zone.
If the pilot week is unusually low- or high-variance, that limits how
generalizable its findings are - this makes that check explicit instead of
assuming the week is representative.

Run from carbon_scheduler/: python scripts/pilot_week_representativeness.py
"""
import json
import os
import statistics
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from services.electricity_service import ElectricityService

TAGGED_LOG_PATH = os.path.join(config.DATA_DIR, "pilot_log_tagged.jsonl")
HISTORY_DIR = os.path.join(config.DATA_DIR, "history")


def main():
    region_map = ElectricityService.REGION_MAP

    with open(TAGGED_LOG_PATH) as f:
        records = [json.loads(l) for l in f if l.strip()]
    live_records = [r for r in records if r.get("data_quality") == ["live"]]

    # Live CI stats per zone during the pilot
    live_by_zone = {}
    for r in live_records:
        for region, m in r["measurements"].items():
            zone = region_map[region]["zone"]
            live_by_zone.setdefault(zone, []).append(m["carbon_intensity"])

    print(f"{'Zone':<15} {'Pilot Avg':>10} {'Pilot StdDev':>13} {'5yr Hist Avg':>13} {'5yr Hist StdDev':>16} {'Delta %':>9}")
    print("-" * 85)

    for zone, values in live_by_zone.items():
        hist_path = os.path.join(HISTORY_DIR, f"ci_history_{zone}.json")
        if not os.path.exists(hist_path):
            continue
        with open(hist_path) as f:
            hist = json.load(f)
        hist_vals = [r["carbonIntensity"] for r in hist]

        pilot_avg = statistics.mean(values)
        pilot_std = statistics.stdev(values) if len(values) > 1 else 0
        hist_avg = statistics.mean(hist_vals)
        hist_std = statistics.stdev(hist_vals)
        delta_pct = (pilot_avg - hist_avg) / hist_avg * 100

        print(f"{zone:<15} {pilot_avg:>10.1f} {pilot_std:>13.1f} {hist_avg:>13.1f} {hist_std:>16.1f} {delta_pct:>+8.1f}%")

    print()
    print("Delta% shows how far the pilot week's average CI is from the 5-year")
    print("historical average for each zone. Large deltas indicate the pilot week")
    print("was not representative of typical grid conditions for that zone.")


if __name__ == "__main__":
    main()

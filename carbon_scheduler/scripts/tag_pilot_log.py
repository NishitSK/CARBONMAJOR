"""
Tags every pilot_log.jsonl record with a data-quality flag so contamination
is explicit and filterable at analysis time, instead of being discovered by
a reviewer opening the raw file.

Flags:
  "stale_date_bug"  - collected before the ElectricityService fix (was
                       querying /past with a hardcoded fallback date instead
                       of /latest). Identifiable because every region's CI
                       is byte-identical to the previous cycle.
  "manual_duplicate" - manual test run, not from the hourly scheduled task
                        (identified by being <15 min after the prior cycle).
  "live"             - genuine automated hourly cycle with live /latest data.

Run from carbon_scheduler/: python scripts/tag_pilot_log.py
"""
import json
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

LOG_PATH = os.path.join(config.DATA_DIR, "pilot_log.jsonl")
OUT_PATH = os.path.join(config.DATA_DIR, "pilot_log_tagged.jsonl")


def main():
    with open(LOG_PATH) as f:
        records = [json.loads(l) for l in f if l.strip()]

    tagged = []
    prev_measurements = None
    prev_time = None

    for r in records:
        ts = datetime.fromisoformat(r["timestamp"])
        flags = []

        # Stale-date bug: identical CI values to the previous cycle across all regions
        # (the old /past endpoint queried a hardcoded fallback date every time).
        if prev_measurements is not None:
            cis_now = {k: v["carbon_intensity"] for k, v in r["measurements"].items()}
            cis_prev = {k: v["carbon_intensity"] for k, v in prev_measurements.items()}
            if cis_now == cis_prev:
                flags.append("stale_date_bug")

        # Manual duplicate: less than 15 minutes after the previous cycle
        # (the hourly scheduled task never fires that close together).
        if prev_time is not None:
            gap_minutes = (ts - prev_time).total_seconds() / 60
            if gap_minutes < 15:
                flags.append("manual_duplicate")

        if not flags:
            flags.append("live")

        r["data_quality"] = flags
        tagged.append(r)

        prev_measurements = r["measurements"]
        prev_time = ts

    with open(OUT_PATH, "w") as f:
        for r in tagged:
            f.write(json.dumps(r) + "\n")

    counts = {}
    for r in tagged:
        for flag in r["data_quality"]:
            counts[flag] = counts.get(flag, 0) + 1

    print(f"Tagged {len(tagged)} records -> {OUT_PATH}")
    print("Flag counts:", counts)
    clean = [r for r in tagged if r["data_quality"] == ["live"]]
    print(f"Clean (live-only) records: {len(clean)} / {len(tagged)}")


if __name__ == "__main__":
    main()

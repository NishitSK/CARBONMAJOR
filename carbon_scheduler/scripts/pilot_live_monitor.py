"""
Live 3-Account Pilot Telemetry Monitor
Displays a formatted real-time status table of all 3 streams:
- Total cycles completed
- Elapsed runtime
- Current winning / active region
- Mean carbon intensity achieved
- Total estimated carbon reduction vs. fixed baseline (~405 gCO2/kWh)
- Real migration counts

Usage:
  python scripts/pilot_live_monitor.py
  python scripts/pilot_live_monitor.py --watch
"""
import argparse
import datetime
import json
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

LOG_FILES = {
    "Adaptive Spatial (Acc 1)": os.path.join(config.DATA_DIR, "pilot_adaptive.jsonl"),
    "LSTM Temporal 24h (Acc 2)": os.path.join(config.DATA_DIR, "pilot_lstm.jsonl"),
    "ARIMA Temporal 6h (Acc 3)": os.path.join(config.DATA_DIR, "pilot_arima.jsonl"),
}

BASELINE_CI = 405.04  # standard Virginia / carbon-blind fixed baseline


def read_jsonl(path: str):
    if not os.path.exists(path):
        return []
    records = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
    return records


def render_dashboard():
    os.system("cls" if os.name == "nt" else "clear")
    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print("=" * 90)
    print(f" CARBON-AWARE SCHEDULER: 3-ACCOUNT LIVE PILOT MONITOR  |  {now_utc}")
    print("=" * 90)

    header = f"{'Policy / Stream':<28} | {'Cycles':<7} | {'Active Region':<22} | {'Latest CI':<10} | {'Mean CI':<9} | {'CO2 Cut':<7}"
    print(header)
    print("-" * 90)

    for stream_name, log_path in LOG_FILES.items():
        records = read_jsonl(log_path)
        count = len(records)
        if count == 0:
            print(f"{stream_name:<28} | {'0':<7} | {'[Pending / Not Started]':<22} | {'--':<10} | {'--':<9} | {'--':<7}")
            continue

        latest = records[-1]
        if "winning_region" in latest:
            active_reg = latest["winning_region"]
            latest_ci = latest.get("winning_ci", 0.0)
            all_cis = [r.get("winning_ci", 0.0) for r in records if "winning_ci" in r]
        else:
            active_reg = latest.get("selected_region", "Unknown")
            latest_ci = latest.get("predicted_optimal_ci", 0.0)
            all_cis = [r.get("predicted_optimal_ci", 0.0) for r in records if "predicted_optimal_ci" in r]

        mean_ci = sum(all_cis) / len(all_cis) if all_cis else 0.0
        reduction_pct = max(0.0, (BASELINE_CI - mean_ci) / BASELINE_CI * 100.0)

        reg_short = (active_reg[:19] + "...") if len(active_reg) > 22 else active_reg
        print(f"{stream_name:<28} | {count:<7} | {reg_short:<22} | {latest_ci:<10.2f} | {mean_ci:<9.2f} | {reduction_pct:<6.1f}%")

    print("-" * 90)
    print("Note: Target duration is 30 Days (720 cycles). Interim Checkpoint at Day 14 (336 cycles).")
    print("Run scripts/generate_interim_report.py to freeze a checkpoint and produce full tables.")
    print("=" * 90)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true", help="Refresh every 30 seconds")
    args = parser.parse_args()

    if args.watch:
        try:
            while True:
                render_dashboard()
                time.sleep(30)
        except KeyboardInterrupt:
            print("\nExiting monitor.")
    else:
        render_dashboard()


if __name__ == "__main__":
    main()

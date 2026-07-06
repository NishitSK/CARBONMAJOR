"""
Reads data/pilot_log.jsonl (built up over the pilot week by run_one_cycle.py)
and produces the paper-ready report: real measured latency table (mean +
range, replacing the old placeholder values), how often each region was
selected, and a real-data carbon comparison against an always-use-one-
fixed-region baseline.

Run from carbon_scheduler/: python aws/analyze_pilot.py
"""
import json
import os
import statistics
import sys
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

LOG_PATH = os.path.join(config.DATA_DIR, "pilot_log.jsonl")
# Compare against always scheduling to this region, to quantify real savings.
BASELINE_REGION = "us-east-1 (N. Virginia)"


def main():
    if not os.path.exists(LOG_PATH):
        print(f"No pilot log at {LOG_PATH} yet.")
        return

    records = []
    with open(LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    if not records:
        print("Pilot log is empty.")
        return

    print(f"Pilot cycles logged: {len(records)}")
    print(f"From {records[0]['timestamp']} to {records[-1]['timestamp']}\n")

    # --- Real measured latency table ---
    latency_samples = defaultdict(list)
    carbon_samples = defaultdict(list)
    for r in records:
        for region, m in r["measurements"].items():
            latency_samples[region].append(m["latency_ms"])
            carbon_samples[region].append(m["carbon_intensity"])

    print("--- Real measured latency (replaces placeholder values) ---")
    print(f"{'Region':<30} {'Mean (ms)':>10} {'Min':>7} {'Max':>7} {'Samples':>8}")
    for region in sorted(latency_samples):
        vals = latency_samples[region]
        print(f"{region:<30} {statistics.mean(vals):>10.1f} {min(vals):>7.1f} {max(vals):>7.1f} {len(vals):>8}")

    # --- Selection frequency ---
    selections = [r["decision"]["selected_region"] for r in records if r.get("decision")]
    counts = defaultdict(int)
    for s in selections:
        counts[s] += 1

    print(f"\n--- Region selection frequency ({len(selections)} decisions) ---")
    for region, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        pct = count / len(selections) * 100
        print(f"{region:<30} {count:>4} cycles ({pct:.1f}%)")

    # --- Real carbon savings vs fixed-region baseline ---
    actual_carbon = []
    baseline_carbon = []
    for r in records:
        if not r.get("decision"):
            continue
        selected = r["decision"]["selected_region"]
        if selected not in r["measurements"]:
            continue
        actual_carbon.append(r["measurements"][selected]["carbon_intensity"])
        if BASELINE_REGION in r["measurements"]:
            baseline_carbon.append(r["measurements"][BASELINE_REGION]["carbon_intensity"])

    if actual_carbon and baseline_carbon and len(actual_carbon) == len(baseline_carbon):
        avg_actual = statistics.mean(actual_carbon)
        avg_baseline = statistics.mean(baseline_carbon)
        savings_pct = (avg_baseline - avg_actual) / avg_baseline * 100
        print(f"\n--- Real carbon comparison vs always-{BASELINE_REGION} ---")
        print(f"Scheduler avg CI:  {avg_actual:.1f} gCO2/kWh")
        print(f"Baseline avg CI:   {avg_baseline:.1f} gCO2/kWh")
        print(f"Measured savings:  {savings_pct:.1f}%  (n={len(actual_carbon)} cycles, real Electricity Maps data)")

    out_path = os.path.join(config.DATA_DIR, "pilot_report.json")
    with open(out_path, "w") as f:
        json.dump({
            "n_cycles": len(records),
            "latency_by_region": {r: {"mean": statistics.mean(v), "min": min(v), "max": max(v), "n": len(v)}
                                   for r, v in latency_samples.items()},
            "selection_counts": dict(counts),
        }, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()

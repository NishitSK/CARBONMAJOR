"""
Compares the production scheduler's picks against two naive baselines, using
only "live" tagged cycles from pilot_log_tagged.jsonl (excludes stale-date-bug
and manual-duplicate contamination).

Baselines:
  - always_cheapest_now: pick whichever region has the lowest carbon intensity
    that cycle, ignoring latency/resources entirely (pure carbon greedy).
  - round_robin: cycle through regions in a fixed order regardless of any
    signal (the "do nothing clever" baseline).
  - fixed_region: always use BASELINE_REGION (us-east-1), the common default
    a naive deployment would pick and never move from.

For each, reports the average actual carbon intensity that would have
resulted, versus the scheduler's actual average - this is the missing
counterfactual: does the scheduler's decision process actually beat doing
nothing smart?

Run from carbon_scheduler/: python scripts/baseline_comparison.py
"""
import json
import os
import statistics
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

TAGGED_LOG_PATH = os.path.join(config.DATA_DIR, "pilot_log_tagged.jsonl")
BASELINE_REGION = "us-east-1 (N. Virginia)"


def main():
    if not os.path.exists(TAGGED_LOG_PATH):
        print(f"No tagged log at {TAGGED_LOG_PATH}. Run scripts/tag_pilot_log.py first.")
        return

    with open(TAGGED_LOG_PATH) as f:
        records = [json.loads(l) for l in f if l.strip()]

    live_records = [r for r in records if r.get("data_quality") == ["live"]]
    print(f"Using {len(live_records)} / {len(records)} cycles (live-only, contamination excluded)\n")

    if not live_records:
        print("No clean cycles yet.")
        return

    all_regions = sorted(live_records[0]["measurements"].keys())
    scheduler_carbon = []
    cheapest_carbon = []
    round_robin_carbon = []
    fixed_carbon = []

    for i, r in enumerate(live_records):
        m = r["measurements"]

        # Scheduler's actual pick
        decision = r.get("decision")
        if decision and decision["selected_region"] in m:
            scheduler_carbon.append(m[decision["selected_region"]]["carbon_intensity"])
        else:
            continue

        # Baseline 1: always pick lowest-CI region this cycle (oracle-ish, carbon-only greedy)
        cheapest_region = min(m, key=lambda reg: m[reg]["carbon_intensity"])
        cheapest_carbon.append(m[cheapest_region]["carbon_intensity"])

        # Baseline 2: round robin through fixed region order
        rr_region = all_regions[i % len(all_regions)]
        if rr_region in m:
            round_robin_carbon.append(m[rr_region]["carbon_intensity"])

        # Baseline 3: always the same fixed region (naive default deployment)
        if BASELINE_REGION in m:
            fixed_carbon.append(m[BASELINE_REGION]["carbon_intensity"])

    def summarize(name, values):
        if not values:
            print(f"{name:<28} no data")
            return None
        avg = statistics.mean(values)
        print(f"{name:<28} avg CI = {avg:>7.1f} g  (n={len(values)})")
        return avg

    print("--- Average carbon intensity resulting from each policy ---")
    sched_avg = summarize("Scheduler (actual picks)", scheduler_carbon)
    cheap_avg = summarize("Always-cheapest-now (greedy)", cheapest_carbon)
    rr_avg = summarize("Round-robin", round_robin_carbon)
    fixed_avg = summarize(f"Fixed ({BASELINE_REGION})", fixed_carbon)

    print()
    if sched_avg and rr_avg:
        savings_vs_rr = (rr_avg - sched_avg) / rr_avg * 100
        print(f"Scheduler vs round-robin:    {savings_vs_rr:+.1f}% carbon")
    if sched_avg and fixed_avg:
        savings_vs_fixed = (fixed_avg - sched_avg) / fixed_avg * 100
        print(f"Scheduler vs fixed-region:   {savings_vs_fixed:+.1f}% carbon")
    if sched_avg and cheap_avg:
        gap_vs_oracle = (sched_avg - cheap_avg) / cheap_avg * 100
        print(f"Scheduler vs pure-greedy-carbon (oracle): {gap_vs_oracle:+.1f}% "
              f"(scheduler trades some carbon for latency/resources)")

    out_path = os.path.join(config.DATA_DIR, "baseline_comparison.json")
    with open(out_path, "w") as f:
        json.dump({
            "n_cycles": len(scheduler_carbon),
            "scheduler_avg_ci": sched_avg,
            "always_cheapest_avg_ci": cheap_avg,
            "round_robin_avg_ci": rr_avg,
            "fixed_region_avg_ci": fixed_avg,
        }, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()

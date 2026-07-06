"""
Re-analysis companion to baseline_comparison.py: instead of reading the
STORED decision from each pilot cycle (which reflects whatever scoring
logic was live at the time - linear_v1 for all cycles collected so far),
this RECOMPUTES what the scheduler would have decided using the CURRENT
scoring logic (threshold_v1) applied to the same raw measurements.

This is explicitly a separate, clearly-labeled comparison, not a rewrite of
history: the original stored decisions and pilot_log files are untouched.
This answers "what would threshold_v1 have chosen on the same real data,"
which is a legitimate new analysis, not retroactive rescoring of the
pilot's actual recorded behavior.

Run from carbon_scheduler/: python scripts/baseline_comparison_recomputed.py
"""
import json
import os
import statistics
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from models.region import Region
from services.scheduler import Scheduler

TAGGED_LOG_PATH = os.path.join(config.DATA_DIR, "pilot_log_tagged.jsonl")
BASELINE_REGION = "us-east-1 (N. Virginia)"


def main():
    with open(TAGGED_LOG_PATH) as f:
        records = [json.loads(l) for l in f if l.strip()]

    live_records = [r for r in records if r.get("data_quality") == ["live"]]
    print(f"Using {len(live_records)} / {len(records)} cycles (live-only, contamination excluded)")
    print(f"Recomputing decisions under scoring_method='{config.SCORING_METHOD_VERSION}' "
          f"(original cycles were logged under 'linear_v1')\n")

    scheduler = Scheduler()
    all_regions = sorted(live_records[0]["measurements"].keys())
    scheduler_carbon = []
    round_robin_carbon = []
    fixed_carbon = []
    changed_decisions = 0

    for i, r in enumerate(live_records):
        m = r["measurements"]
        regions = [Region(name=name, carbon=v["carbon_intensity"], latency=v["latency_ms"], resources=80.0)
                   for name, v in m.items()]
        eligible = scheduler.filter_regions(regions, config.DEFAULT_MAX_LATENCY)
        if not eligible:
            continue
        scored = scheduler.calculate_scores(eligible, config.DEFAULT_WEIGHTS)
        new_winner = scored[0][0].name
        scheduler_carbon.append(m[new_winner]["carbon_intensity"])

        old_winner = (r.get("decision") or {}).get("selected_region")
        if old_winner and old_winner != new_winner:
            changed_decisions += 1

        rr_region = all_regions[i % len(all_regions)]
        if rr_region in m:
            round_robin_carbon.append(m[rr_region]["carbon_intensity"])
        if BASELINE_REGION in m:
            fixed_carbon.append(m[BASELINE_REGION]["carbon_intensity"])

    sched_avg = statistics.mean(scheduler_carbon)
    rr_avg = statistics.mean(round_robin_carbon)
    fixed_avg = statistics.mean(fixed_carbon)

    print(f"Decisions that would change under threshold_v1: {changed_decisions} / {len(scheduler_carbon)}\n")
    print(f"Scheduler (threshold_v1, recomputed) avg CI: {sched_avg:.1f}g")
    print(f"Round-robin avg CI: {rr_avg:.1f}g")
    print(f"Fixed-region avg CI: {fixed_avg:.1f}g\n")
    print(f"Scheduler vs round-robin:  {(rr_avg - sched_avg) / rr_avg * 100:+.1f}%")
    print(f"Scheduler vs fixed-region: {(fixed_avg - sched_avg) / fixed_avg * 100:+.1f}%")

    out_path = os.path.join(config.DATA_DIR, "baseline_comparison_threshold_v1.json")
    with open(out_path, "w") as f:
        json.dump({
            "scoring_method": config.SCORING_METHOD_VERSION,
            "n_cycles": len(scheduler_carbon),
            "decisions_changed_vs_linear_v1": changed_decisions,
            "scheduler_avg_ci": sched_avg,
            "round_robin_avg_ci": rr_avg,
            "fixed_region_avg_ci": fixed_avg,
        }, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()

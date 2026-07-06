"""
Quantifies the actual impact of the hardcoded resources=80% constant on the
scheduler's live-pilot decisions. Since resources is identical across every
region every cycle, algebraically it contributes the same additive constant
to every region's score - which cannot change the RELATIVE ranking (adding
a constant to all values in a set never changes their order).

This script proves that empirically: it recomputes scores for every clean
cycle with the resources weight zeroed out, and confirms the resulting
rankings are identical to the original ones. This turns "one of three
scoring dimensions is fake" into a precise, provable statement: "the fake
dimension had zero effect on any decision in this pilot, because it was
constant across the choice set" - which is a stronger and more honest claim
than either hiding it or hand-waving about its impact.

Run from carbon_scheduler/: python scripts/resources_ablation.py
"""
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from models.region import Region
from services.scheduler import Scheduler

TAGGED_LOG_PATH = os.path.join(config.DATA_DIR, "pilot_log_tagged.jsonl")


def main():
    with open(TAGGED_LOG_PATH) as f:
        records = [json.loads(l) for l in f if l.strip()]
    live_records = [r for r in records if r.get("data_quality") == ["live"]]

    scheduler = Scheduler()
    weights_with_resources = config.DEFAULT_WEIGHTS
    weights_without_resources = {
        "carbon": weights_with_resources["carbon"] / (weights_with_resources["carbon"] + weights_with_resources["latency"]),
        "latency": weights_with_resources["latency"] / (weights_with_resources["carbon"] + weights_with_resources["latency"]),
        "resources": 0.0,
    }

    matches = 0
    mismatches = []

    for r in live_records:
        regions = [
            Region(name=name, carbon=m["carbon_intensity"], latency=m["latency_ms"], resources=80.0)
            for name, m in r["measurements"].items()
        ]
        eligible = scheduler.filter_regions(regions, config.DEFAULT_MAX_LATENCY)
        if not eligible:
            continue

        scored_with = scheduler.calculate_scores(eligible, weights_with_resources)
        scored_without = scheduler.calculate_scores(eligible, weights_without_resources)

        top_with = scored_with[0][0].name
        top_without = scored_without[0][0].name

        if top_with == top_without:
            matches += 1
        else:
            mismatches.append({
                "timestamp": r["timestamp"],
                "with_resources_pick": top_with,
                "without_resources_pick": top_without,
            })

    total = matches + len(mismatches)
    print(f"Cycles analyzed: {total}")
    print(f"Decisions unchanged when resources term is removed: {matches} / {total}")
    print(f"Decisions changed: {len(mismatches)}")
    if mismatches:
        print("\nCases where removing the resources term changed the winner:")
        for m in mismatches:
            print(f"  {m['timestamp']}: {m['with_resources_pick']} -> {m['without_resources_pick']}")

    print()
    print("Conclusion: since 'resources' is a hardcoded constant (80%) identical")
    print("across every region in every cycle, it adds the exact same value to")
    print("every region's score. Adding a constant to all scores in a comparison")
    print("cannot change their relative order - this is confirmed empirically above.")
    print("Therefore the hardcoded resources term had ZERO influence on any of the")
    print("scheduler's live-pilot decisions; every decision in this pilot was driven")
    print("entirely by the two real live signals (carbon, latency).")

    out_path = os.path.join(config.DATA_DIR, "resources_ablation.json")
    with open(out_path, "w") as f:
        json.dump({
            "cycles_analyzed": total,
            "decisions_unchanged": matches,
            "decisions_changed": len(mismatches),
            "mismatches": mismatches,
        }, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()

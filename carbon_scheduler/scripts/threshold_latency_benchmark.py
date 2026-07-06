"""
Tests whether the scheduler's linear latency normalization is over-sensitive
to small, practically-meaningless latency differences (e.g. 150ms vs 200ms
being scored as meaningfully different, when most workloads can't perceive
that gap) versus a threshold/step-based model where anything below an
"acceptable" cutoff scores similarly, and only genuinely slow options are
penalized.

Reruns the 5-year historical replay with a step-function latency score:
  - latency <= ACCEPTABLE_THRESHOLD_MS  -> l_norm = 0 (no penalty at all)
  - latency > ACCEPTABLE_THRESHOLD_MS   -> l_norm scales from 0 to 1 between
                                            threshold and max_latency

This directly tests the user's intuition: does carbon reassert influence
once "good enough" latency differences stop being treated as decisive?

Run from carbon_scheduler/: python scripts/threshold_latency_benchmark.py
"""
import json
import os
import statistics
import sys
from collections import Counter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from models.region import Region
from services.electricity_service import ElectricityService

HISTORY_DIR = os.path.join(config.DATA_DIR, "history")
CLOUD_LATENCY_PATH = os.path.join(config.DATA_DIR, "cloud_latency.json")
ACCEPTABLE_THRESHOLD_MS = 200.0  # "good enough" cutoff for a non-interactive workload


def load_history():
    region_map = ElectricityService.REGION_MAP
    zone_to_region = {meta["zone"]: name for name, meta in region_map.items()}
    series_by_zone = {}
    for fname in os.listdir(HISTORY_DIR):
        if not fname.startswith("ci_history_"):
            continue
        zone = fname[len("ci_history_"):-len(".json")]
        if zone not in zone_to_region:
            continue
        with open(os.path.join(HISTORY_DIR, fname)) as f:
            records = json.load(f)
        series_by_zone[zone] = {r["datetime"]: r["carbonIntensity"] for r in records}
    return series_by_zone, zone_to_region


def threshold_score(regions, weights):
    carbons = [r.carbon for r in regions]
    min_c, max_c = min(carbons), max(carbons)
    max_l = max(r.latency for r in regions)

    scored = []
    for r in regions:
        c_norm = 0.0 if max_c == min_c else (r.carbon - min_c) / (max_c - min_c)
        if r.latency <= ACCEPTABLE_THRESHOLD_MS:
            l_norm = 0.0  # "good enough" - no latency penalty at all
        else:
            denom = max_l - ACCEPTABLE_THRESHOLD_MS
            l_norm = 0.0 if denom <= 0 else (r.latency - ACCEPTABLE_THRESHOLD_MS) / denom
        r_penalty = 1.0 - (r.resources / 100.0)
        score = weights["carbon"] * c_norm + weights["latency"] * l_norm + weights["resources"] * r_penalty
        scored.append((r, score))
    scored.sort(key=lambda x: x[1])
    return scored


def main():
    series_by_zone, zone_to_region = load_history()
    with open(CLOUD_LATENCY_PATH) as f:
        static_latency = json.load(f)["latency_ms"]

    common_ts = sorted(set.intersection(*[set(s.keys()) for s in series_by_zone.values()]))
    sample = common_ts[::6]

    winners = Counter()
    scheduler_carbon = []
    fixed_carbon = []

    for ts in sample:
        regions = []
        for zone, region_name in zone_to_region.items():
            ci = series_by_zone[zone].get(ts)
            lat = static_latency.get(region_name)
            if ci is None or lat is None:
                continue
            regions.append(Region(name=region_name, carbon=ci, latency=lat, resources=80.0))

        if not regions:
            continue
        scored = threshold_score(regions, config.DEFAULT_WEIGHTS)
        winner = scored[0][0]
        winners[winner.name] += 1
        scheduler_carbon.append(winner.carbon)

        fixed_ci = series_by_zone.get("US-MIDA-PJM", {}).get(ts)
        if fixed_ci is not None:
            fixed_carbon.append(fixed_ci)

    sched_avg = statistics.mean(scheduler_carbon)
    fixed_avg = statistics.mean(fixed_carbon)
    total = sum(winners.values())

    print(f"Threshold-based latency model (acceptable <= {ACCEPTABLE_THRESHOLD_MS}ms treated as equal)")
    print(f"Decisions replayed: n={len(scheduler_carbon)}\n")
    print(f"Scheduler avg CI: {sched_avg:.1f}g")
    print(f"Fixed-region avg CI: {fixed_avg:.1f}g")
    print(f"Savings vs fixed-region: {(fixed_avg - sched_avg) / fixed_avg * 100:+.1f}%\n")

    print("Winner distribution:")
    for region, count in winners.most_common():
        print(f"  {region:<30} {count:>5} ({count/total*100:.1f}%)")


if __name__ == "__main__":
    main()

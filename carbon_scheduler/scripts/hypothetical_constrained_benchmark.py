"""
Reruns the 5-year historical decision replay under production-realistic
constraints, similar in spirit to what Google (Radovanovic et al. 2022)
actually operates under, to produce a fairer, apples-to-apples efficiency
estimate instead of the unconstrained 92% upper-bound figure.

Constraints applied (each disclosed, not hidden):
  1. Regional candidate pool restricted to a realistic serving region for a
     North-American user base (Virginia, Ohio, Oregon, Canada) instead of
     freely picking from all 12 global regions - real services don't route
     North American traffic to Mumbai regardless of carbon intensity.
  2. A capacity cap: no single region may be selected more than 40% of the
     time in any rolling window, simulating finite real data-center capacity
     (a real facility cannot absorb 100% of a fleet's traffic).
  3. Baseline is the AVERAGE of the realistic candidate pool (representing an
     already-reasonable multi-region deployment), not a single worst-case
     fixed region - this mirrors comparing against an already-decent existing
     system, the way Google's 29% figure does.

Run from carbon_scheduler/: python scripts/hypothetical_constrained_benchmark.py
"""
import json
import os
import statistics
import sys
from collections import Counter, deque

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from models.region import Region
from services.scheduler import Scheduler
from services.electricity_service import ElectricityService

HISTORY_DIR = os.path.join(config.DATA_DIR, "history")
CLOUD_LATENCY_PATH = os.path.join(config.DATA_DIR, "cloud_latency.json")

CANDIDATE_POOL = [
    "us-east-1 (N. Virginia)",
    "us-east-2 (Ohio)",
    "us-west-2 (Oregon)",
    "ca-central-1 (Canada)",
]
CAPACITY_CAP_PCT = 0.40
CAPACITY_WINDOW = 20  # rolling window size (decisions) over which the cap applies


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


def main():
    series_by_zone, zone_to_region = load_history()
    region_to_zone = {v: k for k, v in zone_to_region.items()}

    with open(CLOUD_LATENCY_PATH) as f:
        static_latency = json.load(f)["latency_ms"]

    pool_zones = [region_to_zone[r] for r in CANDIDATE_POOL]
    common_ts = sorted(set.intersection(*[set(series_by_zone[z].keys()) for z in pool_zones]))
    sample = common_ts[::6]

    scheduler = Scheduler()
    scheduler_carbon = []
    baseline_avg_carbon = []
    winners = Counter()
    recent_window = deque(maxlen=CAPACITY_WINDOW)

    for ts in sample:
        regions = []
        for region_name in CANDIDATE_POOL:
            zone = region_to_zone[region_name]
            ci = series_by_zone[zone].get(ts)
            lat = static_latency.get(region_name)
            if ci is None or lat is None:
                continue
            regions.append(Region(name=region_name, carbon=ci, latency=lat, resources=80.0))

        eligible = scheduler.filter_regions(regions, config.DEFAULT_MAX_LATENCY)
        if not eligible:
            continue
        # Use the paper's own delay-tolerant/flexible-workload weights
        # (carbon-heavy, 0.6/0.25/0.15) since Google's 29% figure specifically
        # applies to their flexible/batch workload class, not their whole
        # fleet - this is the correct like-for-like comparison, not the
        # general-purpose 0.4/0.3/0.3 weights used for mixed workload types.
        flexible_weights = {"carbon": config.JOINT_SHIFT_WEIGHTS["w1"],
                             "latency": config.JOINT_SHIFT_WEIGHTS["w2"],
                             "resources": config.JOINT_SHIFT_WEIGHTS["w3"]}
        scored = scheduler.calculate_scores(eligible, flexible_weights)

        # Apply capacity cap: skip a region if it's already >= cap% of the
        # recent window, falling through to the next-best eligible region.
        chosen = None
        for region, score, _ in scored:
            recent_count = sum(1 for r in recent_window if r == region.name)
            projected_pct = (recent_count + 1) / (len(recent_window) + 1) if recent_window else 0
            if projected_pct <= CAPACITY_CAP_PCT or len(recent_window) < CAPACITY_WINDOW // 2:
                chosen = region
                break
        if chosen is None:
            chosen = scored[0][0]  # fallback if all options exceed cap

        recent_window.append(chosen.name)
        scheduler_carbon.append(chosen.carbon)
        winners[chosen.name] += 1

        # Baseline: average carbon across the realistic candidate pool this hour
        # (an "already reasonably distributed" multi-region deployment)
        pool_cis = [r.carbon for r in regions]
        if pool_cis:
            baseline_avg_carbon.append(statistics.mean(pool_cis))

    sched_avg = statistics.mean(scheduler_carbon)
    baseline_avg = statistics.mean(baseline_avg_carbon)
    total = sum(winners.values())

    print(f"Candidate pool: {CANDIDATE_POOL}")
    print(f"Capacity cap: no region > {CAPACITY_CAP_PCT*100:.0f}% of decisions (rolling window={CAPACITY_WINDOW})")
    print(f"Decisions replayed: n={len(scheduler_carbon)}\n")

    print(f"Constrained scheduler avg CI: {sched_avg:.1f} g")
    print(f"Realistic baseline avg CI (multi-region average): {baseline_avg:.1f} g")
    savings = (baseline_avg - sched_avg) / baseline_avg * 100
    print(f"\nHypothetical constrained efficiency: {savings:+.1f}% carbon reduction")
    print(f"(vs unconstrained global 12-region result: +92.0%)")
    print(f"(vs Google/Radovanovic 2022 production result: +29%)")

    print("\nWinner distribution under capacity cap:")
    for region, count in winners.most_common():
        print(f"  {region:<30} {count:>5} ({count/total*100:.1f}%)")

    out_path = os.path.join(config.DATA_DIR, "hypothetical_constrained_benchmark.json")
    with open(out_path, "w") as f:
        json.dump({
            "candidate_pool": CANDIDATE_POOL,
            "capacity_cap_pct": CAPACITY_CAP_PCT,
            "n_decisions": len(scheduler_carbon),
            "constrained_scheduler_avg_ci": sched_avg,
            "realistic_baseline_avg_ci": baseline_avg,
            "hypothetical_efficiency_pct": savings,
            "winner_distribution": dict(winners),
        }, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()

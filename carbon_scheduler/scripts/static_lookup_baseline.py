"""
Answers the question a council review raised: how much of the scheduler's
headline carbon-savings number comes from real-time adaptive scheduling,
versus simply knowing in advance which grids are consistently clean?

Compares the full adaptive scheduler against a naive "static lookup" policy
that computes the 5-year average carbon intensity per zone ONCE and always
picks whichever region has the lowest average, forever, with zero real-time
adaptation. If the scheduler barely beats this naive rule, most of its
carbon-reduction value comes from region selection, not from adaptivity.

Uses the same 5-year dataset, sampling cadence, and real cloud-vantage
latency as historical_decision_benchmark_cloud_vantage.py, so results are
directly comparable to that script's output.

Run from carbon_scheduler/: python scripts/static_lookup_baseline.py
"""
import json
import os
import statistics
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from models.region import Region
from services.scheduler import Scheduler
from services.electricity_service import ElectricityService

HISTORY_DIR = os.path.join(config.DATA_DIR, "history")
CLOUD_LATENCY_PATH = os.path.join(config.DATA_DIR, "cloud_latency.json")
BASELINE_REGION_ZONE = "US-MIDA-PJM"  # us-east-1


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

    with open(CLOUD_LATENCY_PATH) as f:
        static_latency = json.load(f)["latency_ms"]

    # Compute the 5-year average CI per zone once - the basis for the naive
    # static lookup policy (no real-time information used at decision time).
    avg_ci_by_zone = {zone: statistics.mean(series.values()) for zone, series in series_by_zone.items()}
    print("5-year average CI per region (static lookup basis):")
    for zone, avg in sorted(avg_ci_by_zone.items(), key=lambda kv: kv[1]):
        print(f"  {zone_to_region[zone]:<30} {avg:.1f}g")

    static_best_zone = min(avg_ci_by_zone, key=avg_ci_by_zone.get)
    static_best_region = zone_to_region[static_best_zone]
    print(f"\nNaive static choice (lowest 5-year average): {static_best_region} "
          f"({avg_ci_by_zone[static_best_zone]:.1f}g avg)\n")

    common_ts = sorted(set.intersection(*[set(s.keys()) for s in series_by_zone.values()]))
    sample = common_ts[::6]
    scheduler = Scheduler()

    scheduler_carbon = []
    static_lookup_carbon = []
    fixed_carbon = []

    for ts in sample:
        regions = []
        for zone, region_name in zone_to_region.items():
            ci = series_by_zone[zone].get(ts)
            lat = static_latency.get(region_name)
            if ci is None or lat is None:
                continue
            regions.append(Region(name=region_name, carbon=ci, latency=lat, resources=80.0))

        eligible = scheduler.filter_regions(regions, config.DEFAULT_MAX_LATENCY)
        if not eligible:
            continue
        scored = scheduler.calculate_scores(eligible, config.DEFAULT_WEIGHTS)
        winner = scored[0][0]
        scheduler_carbon.append(winner.carbon)

        static_ci = series_by_zone[static_best_zone].get(ts)
        if static_ci is not None:
            static_lookup_carbon.append(static_ci)

        fixed_ci = series_by_zone.get(BASELINE_REGION_ZONE, {}).get(ts)
        if fixed_ci is not None:
            fixed_carbon.append(fixed_ci)

    sched_avg = statistics.mean(scheduler_carbon)
    static_avg = statistics.mean(static_lookup_carbon)
    fixed_avg = statistics.mean(fixed_carbon)

    print(f"Decisions: n={len(scheduler_carbon)} (scoring_method={config.SCORING_METHOD_VERSION})\n")
    print(f"Full adaptive scheduler:                {sched_avg:.2f}g avg CI")
    print(f"Naive static lookup (always {static_best_region}): {static_avg:.2f}g avg CI")
    print(f"Fixed baseline (always us-east-1):       {fixed_avg:.2f}g avg CI\n")

    gap_vs_static = (static_avg - sched_avg) / static_avg * 100
    gap_vs_fixed = (fixed_avg - sched_avg) / fixed_avg * 100
    print(f"Scheduler vs naive static lookup: {gap_vs_static:+.2f}% "
          f"(isolates the marginal value of real-time adaptivity)")
    print(f"Scheduler vs fixed baseline:      {gap_vs_fixed:+.2f}% "
          f"(value of carbon-awareness generally)")

    out_path = os.path.join(config.DATA_DIR, "static_lookup_baseline.json")
    with open(out_path, "w") as f:
        json.dump({
            "n_decisions": len(scheduler_carbon),
            "scoring_method": config.SCORING_METHOD_VERSION,
            "static_lookup_region": static_best_region,
            "scheduler_avg_ci": sched_avg,
            "static_lookup_avg_ci": static_avg,
            "fixed_baseline_avg_ci": fixed_avg,
            "scheduler_vs_static_lookup_pct": gap_vs_static,
            "scheduler_vs_fixed_baseline_pct": gap_vs_fixed,
        }, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()

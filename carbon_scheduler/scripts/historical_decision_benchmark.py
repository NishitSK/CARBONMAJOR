"""
Addresses the "no decision-quality baseline" gap: the offline evaluation
only ever tested forecast accuracy (MAE), never full region-selection
decisions. This replays the actual production Scheduler.calculate_scores()
across the full 5-year real historical carbon-intensity dataset (2021-2025,
~43,824 hourly timestamps x 12 zones) to get a large-n decision-quality
benchmark, comparable in kind to baseline_comparison.py's live-pilot
version but with ~1000x more decisions.

Latency is held fixed per region using the distance-fitted model from
latency_bias_correction.py (since we have no 5-year latency history) -
this is disclosed explicitly, not hidden. Resources stays at the constant
80% (proven in resources_ablation.py to have zero effect on ranking).

Run from carbon_scheduler/: python scripts/historical_decision_benchmark.py
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

    # Common timestamps across all zones
    common_ts = set.intersection(*[set(s.keys()) for s in series_by_zone.values()])
    common_ts = sorted(common_ts)
    print(f"Zones loaded: {len(series_by_zone)}")
    print(f"Common timestamps across all zones: {len(common_ts)}")

    # Static latency per region from the distance-fit model (disclosed assumption)
    bias_path = os.path.join(config.DATA_DIR, "latency_bias_analysis.json")
    static_latency = {}
    if os.path.exists(bias_path):
        with open(bias_path) as f:
            bias_data = json.load(f)
        for row in bias_data["regions"]:
            static_latency[row["region"]] = row["avg_latency_ms"]
    else:
        print("Run scripts/latency_bias_correction.py first for latency estimates.")
        return

    scheduler = Scheduler()
    region_names = list(zone_to_region.values())
    baseline_region_name = zone_to_region.get(BASELINE_REGION_ZONE)

    scheduler_carbon = []
    fixed_carbon = []
    round_robin_carbon = []

    # Sample every 6th hour to keep runtime reasonable while preserving diurnal coverage
    sample = common_ts[::6]
    print(f"Sampling every 6th hour -> {len(sample)} decisions to replay\n")

    for i, ts in enumerate(sample):
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

        if baseline_region_name:
            fixed_ci = series_by_zone[BASELINE_REGION_ZONE].get(ts)
            if fixed_ci is not None:
                fixed_carbon.append(fixed_ci)

        rr_region_name = region_names[i % len(region_names)]
        rr_zone = next(z for z, n in zone_to_region.items() if n == rr_region_name)
        rr_ci = series_by_zone[rr_zone].get(ts)
        if rr_ci is not None:
            round_robin_carbon.append(rr_ci)

    sched_avg = statistics.mean(scheduler_carbon)
    fixed_avg = statistics.mean(fixed_carbon)
    rr_avg = statistics.mean(round_robin_carbon)

    print("--- 5-year historical decision replay (n={}) ---".format(len(scheduler_carbon)))
    print(f"Scheduler avg CI:      {sched_avg:.1f} g")
    print(f"Fixed-region avg CI:   {fixed_avg:.1f} g")
    print(f"Round-robin avg CI:    {rr_avg:.1f} g")
    print()
    print(f"Scheduler vs fixed-region:  {(fixed_avg - sched_avg) / fixed_avg * 100:+.1f}% carbon")
    print(f"Scheduler vs round-robin:   {(rr_avg - sched_avg) / rr_avg * 100:+.1f}% carbon")

    out_path = os.path.join(config.DATA_DIR, "historical_decision_benchmark.json")
    with open(out_path, "w") as f:
        json.dump({
            "n_decisions": len(scheduler_carbon),
            "date_range": "2021-01-01 to 2025-12-31 (sampled every 6h)",
            "scheduler_avg_ci": sched_avg,
            "fixed_region_avg_ci": fixed_avg,
            "round_robin_avg_ci": rr_avg,
            "latency_assumption": "static, from distance-fit model (latency_bias_analysis.json)",
        }, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()

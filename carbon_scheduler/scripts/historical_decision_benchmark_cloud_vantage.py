"""
Reruns the 5-year historical decision replay (see historical_decision_benchmark.py)
using REAL EC2-to-EC2 latency (data/cloud_latency.json, measured via SSM from a
us-east-1 vantage point) instead of the laptop-distance-fitted latency model.

This is the direct test the council review asked for: does the earlier finding
("Singapore wins 2,269/3,000 historical decisions under static latency") still
hold once the latency term reflects real inter-region cloud traffic instead of
a single home laptop's distance-biased measurements? If the winner distribution
changes substantially, the original finding was an artifact of the biased
latency model, not a property of the scheduler itself.

Run from carbon_scheduler/: python scripts/historical_decision_benchmark_cloud_vantage.py
"""
import json
import os
import statistics
import sys
from collections import Counter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from models.region import Region
from services.scheduler import Scheduler
from services.electricity_service import ElectricityService

HISTORY_DIR = os.path.join(config.DATA_DIR, "history")
CLOUD_LATENCY_PATH = os.path.join(config.DATA_DIR, "cloud_latency.json")
LAPTOP_BENCHMARK_PATH = os.path.join(config.DATA_DIR, "historical_decision_benchmark.json")
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
        cloud_data = json.load(f)
    static_latency = cloud_data["latency_ms"]

    common_ts = sorted(set.intersection(*[set(s.keys()) for s in series_by_zone.values()]))
    print(f"Zones loaded: {len(series_by_zone)}")
    print(f"Common timestamps: {len(common_ts)}")
    print(f"Latency source: REAL EC2-to-EC2 (SSM probe from {cloud_data['prober']})\n")

    scheduler = Scheduler()
    region_names = [n for n in zone_to_region.values() if n in static_latency]
    baseline_region_name = zone_to_region.get(BASELINE_REGION_ZONE)

    scheduler_carbon = []
    fixed_carbon = []
    round_robin_carbon = []
    winners = Counter()

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
        winners[winner.name] += 1

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
    total = sum(winners.values())

    print("--- 5-year historical decision replay: CLOUD-VANTAGE latency (n={}) ---".format(len(scheduler_carbon)))
    print(f"Scheduler avg CI:      {sched_avg:.1f} g")
    print(f"Fixed-region avg CI:   {fixed_avg:.1f} g")
    print(f"Round-robin avg CI:    {rr_avg:.1f} g")
    print()
    print(f"Scheduler vs fixed-region:  {(fixed_avg - sched_avg) / fixed_avg * 100:+.1f}% carbon")
    print(f"Scheduler vs round-robin:   {(rr_avg - sched_avg) / rr_avg * 100:+.1f}% carbon")
    print()
    print("--- Winner distribution (cloud-vantage latency) ---")
    for region, count in winners.most_common():
        print(f"  {region:<30} {count:>5} ({count/total*100:.1f}%)")

    # Compare against the laptop-vantage benchmark if it exists
    if os.path.exists(LAPTOP_BENCHMARK_PATH):
        with open(LAPTOP_BENCHMARK_PATH) as f:
            laptop_result = json.load(f)
        print()
        print("--- Comparison: laptop-vantage vs cloud-vantage historical benchmark ---")
        print(f"{'Metric':<30} {'Laptop-vantage':>16} {'Cloud-vantage':>16}")
        print(f"{'Scheduler avg CI':<30} {laptop_result['scheduler_avg_ci']:>16.1f} {sched_avg:>16.1f}")
        print(f"{'vs fixed-region':<30} {(laptop_result['fixed_region_avg_ci']-laptop_result['scheduler_avg_ci'])/laptop_result['fixed_region_avg_ci']*100:>15.1f}% {(fixed_avg-sched_avg)/fixed_avg*100:>15.1f}%")
        print(f"{'vs round-robin':<30} {(laptop_result['round_robin_avg_ci']-laptop_result['scheduler_avg_ci'])/laptop_result['round_robin_avg_ci']*100:>15.1f}% {(rr_avg-sched_avg)/rr_avg*100:>15.1f}%")

    out_path = os.path.join(config.DATA_DIR, "historical_decision_benchmark_cloud_vantage.json")
    with open(out_path, "w") as f:
        json.dump({
            "n_decisions": len(scheduler_carbon),
            "latency_source": f"real EC2-to-EC2 via SSM, prober={cloud_data['prober']}",
            "scheduler_avg_ci": sched_avg,
            "fixed_region_avg_ci": fixed_avg,
            "round_robin_avg_ci": rr_avg,
            "winner_distribution": dict(winners),
        }, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()

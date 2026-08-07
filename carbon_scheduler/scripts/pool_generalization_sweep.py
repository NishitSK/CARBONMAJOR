"""
Council Week-1 item: tests whether "static region selection captures ~97% of
achievable savings" is a property of this specific 12-region pool, or holds
more generally. Re-runs the same replay-and-decompose logic as
static_lookup_baseline.py across alternative pools built from the 13 zones of
5-year Electricity Maps history already on disk (research/education access):
leave-one-region-out for all 12 latency-mapped regions, leave-Sweden-and-
Canada-out (removing both regions that dominate the original result), three
continental sub-pools (EU / Asia-Pacific / Americas), and a sweep over the
carbon:latency weight ratio on the full pool. No new data collection, no AWS
access, no redistribution of raw history data - purely local computation.

Each pool run reports the same triplet as static_lookup_baseline.py -
scheduler vs. static-lookup vs. fixed-baseline - plus the winning region's
share of decisions, so results are directly comparable across pools. This
finds WHERE the mechanism changes (which pool/weighting shifts the picture),
not a battery of significance tests on every variant; the held-out,
autocorrelation-adjusted significance test stays on the primary 12-region
result in held_out_generalization_test.py.

Run from carbon_scheduler/: python scripts/pool_generalization_sweep.py
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
BASELINE_REGION_ZONE = "US-MIDA-PJM"  # us-east-1: fixed external reference in every pool

EU = ["eu-west-1 (Ireland)", "eu-central-1 (Frankfurt)", "eu-north-1 (Sweden)"]
ASIA_PACIFIC = ["ap-south-1 (Mumbai)", "ap-southeast-2 (Sydney)",
                "ap-southeast-1 (Singapore)", "ap-northeast-1 (Tokyo)"]
AMERICAS = ["us-east-1 (N. Virginia)", "sa-east-1 (Sao Paulo)",
            "ca-central-1 (Canada)", "us-west-2 (Oregon)", "us-east-2 (Ohio)"]
FULL_12 = EU + ASIA_PACIFIC + AMERICAS


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


def run_pool(pool_regions, series_by_zone, zone_to_region, static_latency, common_ts, weights, sample_stride=6):
    region_to_zone = {name: zone for zone, name in zone_to_region.items()}
    pool_zones = [region_to_zone[r] for r in pool_regions if r in region_to_zone]

    # The static lookup must obey the same SLA latency filter the scheduler
    # does - otherwise, in a pool where the raw cleanest zone happens to be
    # SLA-ineligible (found via leave-Sweden-and-Canada-out: Sao Paulo has the
    # lowest average CI post-removal but 230ms latency, over the 200ms
    # ceiling), the "static lookup" silently picks a region no real
    # deployment could ever use, making it an invalid comparison.
    sla_eligible_zones = [
        z for z in pool_zones
        if static_latency.get(zone_to_region[z]) is not None
        and static_latency[zone_to_region[z]] <= config.DEFAULT_MAX_LATENCY
    ]
    avg_ci = {z: statistics.mean(series_by_zone[z].values()) for z in sla_eligible_zones}
    static_best_zone = min(avg_ci, key=avg_ci.get)
    static_best_region = zone_to_region[static_best_zone]

    scheduler = Scheduler()
    sample = common_ts[::sample_stride]

    scheduler_carbon, static_carbon, fixed_carbon = [], [], []
    winner_counts = {}

    for ts in sample:
        regions = []
        for zone in pool_zones:
            ci = series_by_zone[zone].get(ts)
            region_name = zone_to_region[zone]
            lat = static_latency.get(region_name)
            if ci is None or lat is None:
                continue
            regions.append(Region(name=region_name, carbon=ci, latency=lat, resources=80.0))

        eligible = scheduler.filter_regions(regions, config.DEFAULT_MAX_LATENCY)
        if not eligible:
            continue
        scored = scheduler.calculate_scores(eligible, weights)
        winner = scored[0][0]

        static_ci = series_by_zone[static_best_zone].get(ts)
        fixed_ci = series_by_zone.get(BASELINE_REGION_ZONE, {}).get(ts)
        if static_ci is None or fixed_ci is None:
            continue

        scheduler_carbon.append(winner.carbon)
        static_carbon.append(static_ci)
        fixed_carbon.append(fixed_ci)
        winner_counts[winner.name] = winner_counts.get(winner.name, 0) + 1

    if not scheduler_carbon:
        return None

    sched_avg = statistics.mean(scheduler_carbon)
    static_avg = statistics.mean(static_carbon)
    fixed_avg = statistics.mean(fixed_carbon)
    gap_vs_static = (static_avg - sched_avg) / static_avg * 100 if static_avg else float("nan")
    gap_vs_fixed = (fixed_avg - sched_avg) / fixed_avg * 100 if fixed_avg else float("nan")

    n = len(scheduler_carbon)
    top_region, top_count = max(winner_counts.items(), key=lambda kv: kv[1])

    return {
        "pool_regions": [zone_to_region[z] for z in pool_zones],
        "pool_size": len(pool_zones),
        "static_lookup_region": static_best_region,
        "n_decisions": n,
        "scheduler_avg_ci": sched_avg,
        "static_lookup_avg_ci": static_avg,
        "fixed_baseline_avg_ci": fixed_avg,
        "scheduler_vs_static_lookup_pct": gap_vs_static,
        "scheduler_vs_fixed_baseline_pct": gap_vs_fixed,
        "winner_distribution": winner_counts,
        "top_region": top_region,
        "top_region_share_pct": 100 * top_count / n,
    }


def main():
    series_by_zone, zone_to_region = load_history()
    with open(CLOUD_LATENCY_PATH) as f:
        static_latency = json.load(f)["latency_ms"]

    common_ts = sorted(set.intersection(*[set(series_by_zone[z].keys()) for z in series_by_zone]))
    print(f"Common timestamps across all {len(series_by_zone)} zones: {len(common_ts)}")
    print(f"Full pool ({len(FULL_12)} regions): {FULL_12}\n")

    pool_defs = {"full_12": FULL_12}
    for region in FULL_12:
        pool_defs[f"leave_out__{region}"] = [r for r in FULL_12 if r != region]
    pool_defs["leave_out__sweden_and_canada"] = [
        r for r in FULL_12 if r not in ("eu-north-1 (Sweden)", "ca-central-1 (Canada)")
    ]
    pool_defs["eu_only"] = EU
    pool_defs["asia_pacific_only"] = ASIA_PACIFIC
    pool_defs["americas_only"] = AMERICAS

    print("--- Pool sweeps (default weights) ---")
    results = {}
    for name, pool in pool_defs.items():
        r = run_pool(pool, series_by_zone, zone_to_region, static_latency, common_ts, config.DEFAULT_WEIGHTS)
        if r is None:
            print(f"{name}: no eligible decisions (pool too small or all filtered), skipped")
            continue
        results[name] = r
        print(f"{name:42s} n={r['n_decisions']:>6}  adaptivity={r['scheduler_vs_static_lookup_pct']:+6.2f}%  "
              f"vs_fixed={r['scheduler_vs_fixed_baseline_pct']:+6.1f}%  "
              f"top={r['top_region']} ({r['top_region_share_pct']:.1f}%)")

    print("\n--- Weight sweep (full 12-region pool, carbon:latency ratio varied) ---")
    weight_results = {}
    for w_carbon in [0.50, 0.571, 0.65, 0.75, 0.85]:
        weights = {"carbon": w_carbon, "latency": 1 - w_carbon, "resources": 0.0}
        r = run_pool(FULL_12, series_by_zone, zone_to_region, static_latency, common_ts, weights)
        key = f"w_carbon_{w_carbon:.3f}"
        weight_results[key] = r
        print(f"{key:20s} n={r['n_decisions']:>6}  adaptivity={r['scheduler_vs_static_lookup_pct']:+6.2f}%  "
              f"top={r['top_region']} ({r['top_region_share_pct']:.1f}%)")

    out_path = os.path.join(config.DATA_DIR, "pool_generalization_sweep.json")
    with open(out_path, "w") as f:
        json.dump({"pool_sweeps": results, "weight_sweeps": weight_results}, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()

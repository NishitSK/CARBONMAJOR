"""
Council-mandated fix: the static-lookup baseline (scripts/static_lookup_baseline.py)
reports that the scheduler beats a naive static lookup by only +6.5% on the 5-year
replay. That figure was reported as a point estimate with no significance test -
if it isn't statistically distinguishable from noise, the paper's framing needs to
shift from "adaptivity contributes +6.5%" to "we found no measurable benefit from
real-time adaptivity in this region pool," which is a different, still-honest,
claim.

This script re-runs the exact same replay (same dataset, same sampling cadence,
same latency data, same scoring method) as static_lookup_baseline.py, but keeps
the PAIRED per-decision carbon-intensity values (scheduler vs. static lookup, same
timestamp) rather than only the aggregate means, so a proper paired test can be
run: each decision is one paired observation, not an independent sample.

Tests run:
  1. Paired t-test (parametric; assumes the differences are roughly normal)
  2. Wilcoxon signed-rank test (nonparametric; robust to the fact that carbon-
     intensity differences are unlikely to be normally distributed)
  3. Bootstrap 95% CI on the mean percentage difference (10,000 resamples,
     resampling decision-pairs with replacement - the standard way to get a CI
     on a ratio-of-means statistic without assuming a parametric form)

Run from carbon_scheduler/: python scripts/significance_test_adaptivity.py
"""
import json
import os
import statistics
import sys
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from models.region import Region
from services.scheduler import Scheduler
from services.electricity_service import ElectricityService

from scipy import stats as scipy_stats

HISTORY_DIR = os.path.join(config.DATA_DIR, "history")
CLOUD_LATENCY_PATH = os.path.join(config.DATA_DIR, "cloud_latency.json")
BASELINE_REGION_ZONE = "US-MIDA-PJM"  # us-east-1
N_BOOTSTRAP = 10000
RNG_SEED = 42


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


def bootstrap_pct_diff_ci(scheduler_vals, static_vals, n_boot=N_BOOTSTRAP, seed=RNG_SEED):
    """
    Bootstrap CI on: (mean(static) - mean(scheduler)) / mean(static) * 100
    Resamples decision-PAIRS with replacement, preserving the pairing between
    scheduler and static-lookup values for the same timestamp.
    """
    rng = random.Random(seed)
    n = len(scheduler_vals)
    diffs_pct = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        sched_sample = [scheduler_vals[i] for i in idx]
        static_sample = [static_vals[i] for i in idx]
        sched_mean = statistics.mean(sched_sample)
        static_mean = statistics.mean(static_sample)
        if static_mean == 0:
            continue
        diffs_pct.append((static_mean - sched_mean) / static_mean * 100)
    diffs_pct.sort()
    lo = diffs_pct[int(0.025 * len(diffs_pct))]
    hi = diffs_pct[int(0.975 * len(diffs_pct))]
    return lo, hi, statistics.mean(diffs_pct)


def main():
    series_by_zone, zone_to_region = load_history()

    with open(CLOUD_LATENCY_PATH) as f:
        static_latency = json.load(f)["latency_ms"]

    avg_ci_by_zone = {zone: statistics.mean(series.values()) for zone, series in series_by_zone.items()}
    static_best_zone = min(avg_ci_by_zone, key=avg_ci_by_zone.get)
    static_best_region = zone_to_region[static_best_zone]

    common_ts = sorted(set.intersection(*[set(s.keys()) for s in series_by_zone.values()]))
    sample = common_ts[::6]
    scheduler = Scheduler()

    scheduler_carbon = []
    static_lookup_carbon = []

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

        static_ci = series_by_zone[static_best_zone].get(ts)
        if static_ci is None:
            continue

        scheduler_carbon.append(winner.carbon)
        static_lookup_carbon.append(static_ci)

    n = len(scheduler_carbon)
    sched_avg = statistics.mean(scheduler_carbon)
    static_avg = statistics.mean(static_lookup_carbon)
    pct_diff = (static_avg - sched_avg) / static_avg * 100

    # 1. Paired t-test
    t_stat, t_pvalue = scipy_stats.ttest_rel(static_lookup_carbon, scheduler_carbon)

    # 2. Wilcoxon signed-rank test (nonparametric)
    diffs = [s - sc for s, sc in zip(static_lookup_carbon, scheduler_carbon)]
    n_nonzero = sum(1 for d in diffs if d != 0)
    if n_nonzero > 0:
        w_stat, w_pvalue = scipy_stats.wilcoxon(static_lookup_carbon, scheduler_carbon)
    else:
        w_stat, w_pvalue = float("nan"), float("nan")

    # 3. Bootstrap CI
    ci_lo, ci_hi, boot_mean = bootstrap_pct_diff_ci(scheduler_carbon, static_lookup_carbon)

    print(f"Decisions (paired): n={n}")
    print(f"Static lookup region: {static_best_region}\n")
    print(f"Scheduler mean CI:      {sched_avg:.3f}g")
    print(f"Static lookup mean CI:  {static_avg:.3f}g")
    print(f"Point estimate:         {pct_diff:+.2f}% (scheduler vs static lookup)\n")

    print(f"Paired t-test:          t={t_stat:.3f}, p={t_pvalue:.6f}")
    print(f"Wilcoxon signed-rank:   W={w_stat:.3f}, p={w_pvalue:.6f}")
    print(f"Bootstrap 95% CI on pct diff ({N_BOOTSTRAP} resamples): "
          f"[{ci_lo:+.2f}%, {ci_hi:+.2f}%] (bootstrap mean {boot_mean:+.2f}%)\n")

    alpha = 0.05
    significant = t_pvalue < alpha and w_pvalue < alpha
    ci_excludes_zero = (ci_lo > 0 and ci_hi > 0) or (ci_lo < 0 and ci_hi < 0)
    print(f"Verdict (alpha=0.05): "
          f"{'STATISTICALLY SIGNIFICANT' if significant else 'NOT statistically significant'} "
          f"by both tests; bootstrap CI {'excludes' if ci_excludes_zero else 'includes'} zero.")

    out_path = os.path.join(config.DATA_DIR, "significance_test_adaptivity.json")
    with open(out_path, "w") as f:
        json.dump({
            "n_decisions": int(n),
            "static_lookup_region": static_best_region,
            "scheduler_mean_ci": float(sched_avg),
            "static_lookup_mean_ci": float(static_avg),
            "point_estimate_pct": float(pct_diff),
            "paired_t_test": {"t_stat": float(t_stat), "p_value": float(t_pvalue)},
            "wilcoxon_signed_rank": {"w_stat": float(w_stat), "p_value": float(w_pvalue)},
            "bootstrap_95ci_pct": {"lo": float(ci_lo), "hi": float(ci_hi), "mean": float(boot_mean), "n_resamples": N_BOOTSTRAP},
            "significant_at_0.05": bool(significant),
            "bootstrap_ci_excludes_zero": bool(ci_excludes_zero),
        }, f, indent=2)
    print(f"Saved -> {out_path}")


if __name__ == "__main__":
    main()

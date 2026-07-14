"""
Round-2 council review: the static-lookup baseline (and its significance test)
were both computed using the SAME 2021-2025 window for (a) picking the static
lookup's region and (b) evaluating it. That gives the static lookup implicit
hindsight over its own test period - not a fair "knew in advance" comparison,
and it means the 82.9%/17.1% mechanism split has never been checked on data
the static lookup's region choice didn't have access to.

This script fixes that with a real train/test split:
  - TRAIN period: 2021-01-01 to 2023-12-31 (3 years). The static lookup's
    region choice (lowest average CI) is computed using ONLY this window,
    exactly like a real deployment would have to.
  - TEST period: 2024-01-01 to 2025-12-31 (2 years, fully held out). Both the
    full adaptive scheduler and the train-period-chosen static lookup are
    evaluated ONLY on this window, which the static lookup's region choice
    has never seen.

Reports: does the ~6.5% adaptivity finding and the 82.9%/17.1% agree/switch
mechanism hold up out-of-sample, or was it specific to the original in-sample
setup? Either answer is reported as-is - this script does not have a target
number to hit.

Run from carbon_scheduler/: python scripts/held_out_generalization_test.py
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

from scipy import stats as scipy_stats

HISTORY_DIR = os.path.join(config.DATA_DIR, "history")
CLOUD_LATENCY_PATH = os.path.join(config.DATA_DIR, "cloud_latency.json")
BASELINE_REGION_ZONE = "US-MIDA-PJM"  # us-east-1

TRAIN_END = "2024-01-01T00:00:00.000000"  # exclusive: train = [.., TRAIN_END)
TEST_START = TRAIN_END                     # test = [TEST_START, ..]


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

    common_ts = sorted(set.intersection(*[set(s.keys()) for s in series_by_zone.values()]))
    train_ts = [t for t in common_ts if t < TRAIN_END]
    test_ts = [t for t in common_ts if t >= TEST_START]

    # --- Static lookup's region choice, using ONLY the train period ---
    train_avg_ci_by_zone = {
        zone: statistics.mean(series[t] for t in train_ts if t in series)
        for zone, series in series_by_zone.items()
    }
    static_best_zone = min(train_avg_ci_by_zone, key=train_avg_ci_by_zone.get)
    static_best_region = zone_to_region[static_best_zone]
    print("Static lookup region chosen from TRAIN period only (2021-2023):")
    for zone, avg in sorted(train_avg_ci_by_zone.items(), key=lambda kv: kv[1])[:3]:
        print(f"  {zone_to_region[zone]:<30} {avg:.1f}g (train avg)")
    print(f"-> Static lookup commits to: {static_best_region}\n")

    # --- Evaluate on TEST period only (never seen by the static choice) ---
    test_sample = test_ts[::6]
    scheduler = Scheduler()

    scheduler_carbon, static_carbon, fixed_carbon = [], [], []
    agree, switch_to_better, switch_to_worse = 0, 0, 0
    winner_counts = {}

    for ts in test_sample:
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
        fixed_ci = series_by_zone.get(BASELINE_REGION_ZONE, {}).get(ts)
        if static_ci is None or fixed_ci is None:
            continue

        scheduler_carbon.append(winner.carbon)
        static_carbon.append(static_ci)
        fixed_carbon.append(fixed_ci)
        winner_counts[winner.name] = winner_counts.get(winner.name, 0) + 1

        if winner.name == static_best_region:
            agree += 1
        elif winner.carbon < static_ci:
            switch_to_better += 1
        else:
            switch_to_worse += 1

    n = len(scheduler_carbon)
    sched_avg = statistics.mean(scheduler_carbon)
    static_avg = statistics.mean(static_carbon)
    fixed_avg = statistics.mean(fixed_carbon)
    gap_vs_static = (static_avg - sched_avg) / static_avg * 100
    gap_vs_fixed = (fixed_avg - sched_avg) / fixed_avg * 100

    diffs = [s - sc for s, sc in zip(static_carbon, scheduler_carbon)]
    t_stat, t_pvalue = scipy_stats.ttest_rel(static_carbon, scheduler_carbon)
    w_stat, w_pvalue = scipy_stats.wilcoxon(static_carbon, scheduler_carbon) if any(diffs) else (float("nan"), float("nan"))

    # --- Round-3 point 1: subgroup breakdown, agreement vs. disagreement ---
    # On agreement decisions the scheduler and static lookup pick the SAME
    # region, so their CI reading for that hour is identical by construction
    # (diff = 0). The entire aggregate advantage is therefore mechanically
    # concentrated in the disagreement subset - this reports the actual
    # magnitude of that concentration rather than asserting it.
    agree_diffs = [d for d in diffs if d == 0]
    disagree_diffs = [d for d in diffs if d != 0]
    n_agree, n_disagree = len(agree_diffs), len(disagree_diffs)
    mean_diff_agree = statistics.mean(agree_diffs) if agree_diffs else 0.0
    mean_diff_disagree = statistics.mean(disagree_diffs) if disagree_diffs else 0.0
    pct_of_pooled_advantage_from_disagreement = (
        (sum(disagree_diffs) / sum(diffs)) * 100 if sum(diffs) else float("nan")
    )

    # --- Round-3 point 3: autocorrelation-adjusted effective sample size ---
    # Hourly CI is autocorrelated across adjacent sampled decisions (weather/
    # grid conditions persist for hours), so treating n=2,924 as independent
    # trials in the paired t-test likely overstates the effective sample
    # size. Lag-1 autocorrelation of the per-decision diff series gives a
    # standard AR(1) effective-n correction: n_eff = n*(1-rho)/(1+rho).
    def lag1_autocorr(series):
        m = statistics.mean(series)
        num = sum((series[i] - m) * (series[i + 1] - m) for i in range(len(series) - 1))
        den = sum((x - m) ** 2 for x in series)
        return num / den if den else 0.0

    rho = lag1_autocorr(diffs)
    n_eff = n * (1 - rho) / (1 + rho) if (1 + rho) != 0 else n
    se_naive = statistics.stdev(diffs) / (n ** 0.5) if n > 1 else 0.0
    se_adjusted = statistics.stdev(diffs) / (max(n_eff, 1) ** 0.5) if n > 1 else 0.0
    t_stat_adjusted = statistics.mean(diffs) / se_adjusted if se_adjusted else float("nan")
    # two-sided p-value from a normal approximation (effective-n corrected)
    from scipy.stats import norm
    p_adjusted = 2 * (1 - norm.cdf(abs(t_stat_adjusted))) if se_adjusted else float("nan")

    print(f"TEST period (held out, 2024-2025): n={n} decisions")
    print(f"Winner distribution: {sorted(winner_counts.items(), key=lambda kv: -kv[1])}\n")
    print(f"Scheduler mean CI:      {sched_avg:.2f}g")
    print(f"Static lookup mean CI:  {static_avg:.2f}g")
    print(f"Fixed baseline mean CI: {fixed_avg:.2f}g\n")
    print(f"Scheduler vs static lookup (held-out): {gap_vs_static:+.2f}%")
    print(f"Scheduler vs fixed baseline (held-out): {gap_vs_fixed:+.2f}%\n")
    print(f"Paired t-test (naive n={n}):  t={t_stat:.3f}, p={t_pvalue:.6f}")
    print(f"Wilcoxon signed-rank:         W={w_stat:.3f}, p={w_pvalue:.6f}\n")
    print(f"Agreement (scheduler picks same region as static lookup): {agree}/{n} ({100*agree/n:.1f}%)")
    print(f"Scheduler switches to a BETTER region:                    {switch_to_better}/{n} ({100*switch_to_better/n:.1f}%)")
    print(f"Scheduler switches to a WORSE region (should be ~0):      {switch_to_worse}/{n} ({100*switch_to_worse/n:.1f}%)\n")
    print(f"--- Subgroup breakdown ---")
    print(f"Agreement subset    (n={n_agree}): mean diff = {mean_diff_agree:.3f}g (trivially 0, same region)")
    print(f"Disagreement subset (n={n_disagree}): mean diff = {mean_diff_disagree:.3f}g per decision")
    print(f"Share of total pooled advantage coming from the disagreement subset: {pct_of_pooled_advantage_from_disagreement:.1f}%\n")
    print(f"--- Autocorrelation-adjusted significance ---")
    print(f"Lag-1 autocorrelation of per-decision diffs: rho={rho:.3f}")
    print(f"Naive n={n} -> effective n (AR(1)-adjusted) = {n_eff:.0f}")
    print(f"Naive SE={se_naive:.4f}g -> adjusted SE={se_adjusted:.4f}g")
    print(f"Adjusted t-stat={t_stat_adjusted:.3f}, adjusted p-value={p_adjusted:.6f}")

    out_path = os.path.join(config.DATA_DIR, "held_out_generalization_test.json")
    with open(out_path, "w") as f:
        json.dump({
            "train_period": "2021-01-01 to 2023-12-31 (region choice only)",
            "test_period": "2024-01-01 to 2025-12-31 (held out, never used for region choice)",
            "static_lookup_region_from_train": static_best_region,
            "n_decisions_test": int(n),
            "winner_distribution": winner_counts,
            "scheduler_mean_ci": float(sched_avg),
            "static_lookup_mean_ci": float(static_avg),
            "fixed_baseline_mean_ci": float(fixed_avg),
            "scheduler_vs_static_pct": float(gap_vs_static),
            "scheduler_vs_fixed_pct": float(gap_vs_fixed),
            "paired_t_test": {"t_stat": float(t_stat), "p_value": float(t_pvalue)},
            "wilcoxon": {"w_stat": float(w_stat), "p_value": float(w_pvalue)},
            "agreement_count": agree,
            "switch_to_better_count": switch_to_better,
            "switch_to_worse_count": switch_to_worse,
            "subgroup_breakdown": {
                "n_agree": n_agree,
                "n_disagree": n_disagree,
                "mean_diff_agree_g": float(mean_diff_agree),
                "mean_diff_disagree_g": float(mean_diff_disagree),
                "pct_of_pooled_advantage_from_disagreement": float(pct_of_pooled_advantage_from_disagreement),
            },
            "autocorrelation_adjustment": {
                "lag1_autocorr_rho": float(rho),
                "n_naive": int(n),
                "n_effective": float(n_eff),
                "se_naive_g": float(se_naive),
                "se_adjusted_g": float(se_adjusted),
                "t_stat_adjusted": float(t_stat_adjusted),
                "p_value_adjusted": float(p_adjusted),
            },
        }, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()

"""
Round-4 council review, point 1: the round-3 "100% of advantage concentrates
in the 6.3% disagreement subset" finding is close to circular - "agreement"
is DEFINED as picking the same region, which trivially makes the CI
difference ~0 there. This script instead asks the substantive question: is
there anything that CHARACTERIZES the 183 disagreement decisions - something
that would let a reader anticipate them in advance, not just observe them
after the fact?

Point 3: before proposing any mechanism, this script also checks whether
disagreement correlates with a mundane data-quality artifact - specifically
whether Canada's CI readings on disagreement hours are disproportionately
`isEstimated` (interpolated/estimated rather than measured), since Canada's
historical series has a much higher estimated-fraction (~13%) than Sweden's
(~0.06%).

Point 2: computes lag-1 autocorrelation and an AR(1)-adjusted effective
sample size for the n=183 disagreement subgroup specifically (not just the
full n=2,924 set), and reports whether the subgroup's mean advantage remains
distinguishable from zero under that correction.

Method for the characterization (point 1): the held-out 2024-2025 test
period is itself split in half by time - 2024 as a FIT period, 2025 as a
TEST period - so any candidate rule is fit on one period and checked for
whether it predicts disagreement in a period it never saw, mirroring the
train/test discipline already applied to the headline 6.5%->2.7% result.

Run from carbon_scheduler/: python scripts/significance_test_adaptivity_subgroup_characterization.py
"""
import json
import os
import statistics
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from models.region import Region
from services.scheduler import Scheduler
from services.electricity_service import ElectricityService

from scipy import stats as scipy_stats

HISTORY_DIR = os.path.join(config.DATA_DIR, "history")
CLOUD_LATENCY_PATH = os.path.join(config.DATA_DIR, "cloud_latency.json")
BASELINE_REGION_ZONE = "US-MIDA-PJM"

TRAIN_END = "2024-01-01T00:00:00.000000"   # region choice only
CHAR_FIT_END = "2025-01-01T00:00:00.000000"  # 2024 = characterization-fit, 2025 = characterization-test


def load_history():
    region_map = ElectricityService.REGION_MAP
    zone_to_region = {meta["zone"]: name for name, meta in region_map.items()}
    series_by_zone, estimated_by_zone = {}, {}
    for fname in os.listdir(HISTORY_DIR):
        if not fname.startswith("ci_history_"):
            continue
        zone = fname[len("ci_history_"):-len(".json")]
        if zone not in zone_to_region:
            continue
        with open(os.path.join(HISTORY_DIR, fname)) as f:
            records = json.load(f)
        series_by_zone[zone] = {r["datetime"]: r["carbonIntensity"] for r in records}
        estimated_by_zone[zone] = {r["datetime"]: bool(r.get("isEstimated")) for r in records}
    return series_by_zone, estimated_by_zone, zone_to_region


def lag1_autocorr(series):
    if len(series) < 3:
        return 0.0
    m = statistics.mean(series)
    num = sum((series[i] - m) * (series[i + 1] - m) for i in range(len(series) - 1))
    den = sum((x - m) ** 2 for x in series)
    return num / den if den else 0.0


def main():
    series_by_zone, estimated_by_zone, zone_to_region = load_history()
    with open(CLOUD_LATENCY_PATH) as f:
        static_latency = json.load(f)["latency_ms"]

    common_ts = sorted(set.intersection(*[set(s.keys()) for s in series_by_zone.values()]))
    train_ts = [t for t in common_ts if t < TRAIN_END]
    test_ts = [t for t in common_ts if t >= TRAIN_END]

    train_avg_ci_by_zone = {
        zone: statistics.mean(series[t] for t in train_ts if t in series)
        for zone, series in series_by_zone.items()
    }
    static_best_zone = min(train_avg_ci_by_zone, key=train_avg_ci_by_zone.get)
    static_best_region = zone_to_region[static_best_zone]
    canada_zone = next(z for z, r in zone_to_region.items() if "Canada" in r)

    test_sample = test_ts[::6]
    scheduler = Scheduler()

    decisions = []  # one dict per decision, all features we might characterize on

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
        canada_ci = series_by_zone[canada_zone].get(ts)
        if static_ci is None or canada_ci is None:
            continue

        dt = datetime.fromisoformat(ts)
        disagree = winner.name != static_best_region

        decisions.append({
            "ts": ts,
            "dt": dt,
            "winner": winner.name,
            "sched_ci": winner.carbon,
            "static_ci": static_ci,
            "diff": static_ci - winner.carbon,
            "disagree": disagree,
            "gap_sweden_minus_canada": static_ci - canada_ci,
            "canada_estimated": estimated_by_zone[canada_zone].get(ts, False),
            "sweden_estimated": estimated_by_zone[static_best_zone].get(ts, False),
            "month": dt.month,
            "hour": dt.hour,
            "year": dt.year,
        })

    n = len(decisions)
    disagreements = [d for d in decisions if d["disagree"]]
    agreements = [d for d in decisions if not d["disagree"]]
    n_dis, n_agree = len(disagreements), len(agreements)

    print(f"Total held-out decisions: {n}  (agree={n_agree}, disagree={n_dis})\n")

    # === POINT 3: artifact check - is disagreement a data-quality artifact? ===
    print("=" * 70)
    print("POINT 3: ARTIFACT CHECK (isEstimated data-quality flag)")
    print("=" * 70)
    dis_canada_est_rate = sum(d["canada_estimated"] for d in disagreements) / n_dis if n_dis else 0
    agree_canada_est_rate = sum(d["canada_estimated"] for d in agreements) / n_agree if n_agree else 0
    dis_sweden_est_rate = sum(d["sweden_estimated"] for d in disagreements) / n_dis if n_dis else 0
    agree_sweden_est_rate = sum(d["sweden_estimated"] for d in agreements) / n_agree if n_agree else 0
    print(f"Canada isEstimated rate | disagreement decisions: {dis_canada_est_rate:.1%}  |  agreement decisions: {agree_canada_est_rate:.1%}")
    print(f"Sweden isEstimated rate | disagreement decisions: {dis_sweden_est_rate:.1%}  |  agreement decisions: {agree_sweden_est_rate:.1%}")
    artifact_flag = dis_canada_est_rate > 2 * agree_canada_est_rate and dis_canada_est_rate > 0.15
    print(f"Artifact concern (disagreement disproportionately on estimated Canada data): {artifact_flag}\n")

    # === POINT 1: characterize the 183 disagreement decisions ===
    print("=" * 70)
    print("POINT 1: CHARACTERIZATION (fit on 2024, test on 2025)")
    print("=" * 70)
    fit = [d for d in decisions if d["dt"] < datetime.fromisoformat(CHAR_FIT_END)]
    test = [d for d in decisions if d["dt"] >= datetime.fromisoformat(CHAR_FIT_END)]
    print(f"Fit period (2024): n={len(fit)}, disagreements={sum(d['disagree'] for d in fit)}")
    print(f"Test period (2025): n={len(test)}, disagreements={sum(d['disagree'] for d in test)}\n")

    # Candidate rule: threshold on the Sweden-Canada CI gap. Disagreement
    # happens (by the scheduler's own logic) when this gap goes negative -
    # so instead of just restating that, we ask whether the DISTRIBUTION of
    # this gap is predictable in advance from time-of-year, i.e. whether the
    # gap tends to go negative in identifiable months, fit on 2024 and
    # checked on 2025.
    fit_dis_months = [d["month"] for d in fit if d["disagree"]]
    fit_month_counts = {m: fit_dis_months.count(m) for m in range(1, 13)}
    top_months = sorted(fit_month_counts, key=fit_month_counts.get, reverse=True)[:4]
    print(f"Months with most disagreements in FIT period (2024): {sorted(top_months)}")
    print(f"  Disagreement count by month (2024 fit): {dict(sorted(fit_month_counts.items()))}")

    # Predict: in the TEST period (2025), is disagreement rate higher in
    # those same top months than in the rest of the year?
    test_in_months = [d for d in test if d["month"] in top_months]
    test_out_months = [d for d in test if d["month"] not in top_months]
    rate_in = sum(d["disagree"] for d in test_in_months) / len(test_in_months) if test_in_months else 0
    rate_out = sum(d["disagree"] for d in test_out_months) / len(test_out_months) if test_out_months else 0
    print(f"\nTEST period (2025) disagreement rate, in fit-selected months:    {rate_in:.1%} (n={len(test_in_months)})")
    print(f"TEST period (2025) disagreement rate, outside fit-selected months: {rate_out:.1%} (n={len(test_out_months)})")
    seasonal_signal = rate_in > 1.5 * rate_out and rate_in > 0.05
    print(f"Seasonal pattern replicates out-of-sample (rate_in > 1.5x rate_out): {seasonal_signal}\n")

    # Candidate rule 2: gap magnitude in the fit period vs test period -
    # does a "small gap last hour predicts a flip this hour" rule generalize?
    fit_gaps_dis = [d["gap_sweden_minus_canada"] for d in fit if d["disagree"]]
    fit_gaps_agree = [d["gap_sweden_minus_canada"] for d in fit if not d["disagree"]]
    print(f"FIT period gap (Sweden CI - Canada CI), disagreement decisions: mean={statistics.mean(fit_gaps_dis):.2f}g" if fit_gaps_dis else "no fit disagreements")
    print(f"FIT period gap, agreement decisions:    mean={statistics.mean(fit_gaps_agree):.2f}g" if fit_gaps_agree else "n/a")
    print("(This restates the decision rule itself - included for completeness, not claimed as a novel predictor.)\n")

    # === POINT 2: autocorrelation within the disagreement subgroup specifically ===
    print("=" * 70)
    print("POINT 2: AUTOCORRELATION WITHIN THE DISAGREEMENT SUBGROUP (n=183)")
    print("=" * 70)
    dis_diffs_ordered = [d["diff"] for d in sorted(disagreements, key=lambda x: x["ts"])]
    rho_dis = lag1_autocorr(dis_diffs_ordered)
    n_eff_dis = n_dis * (1 - rho_dis) / (1 + rho_dis) if (1 + rho_dis) != 0 else n_dis
    mean_dis = statistics.mean(dis_diffs_ordered)
    sd_dis = statistics.stdev(dis_diffs_ordered) if n_dis > 1 else 0
    se_naive_dis = sd_dis / (n_dis ** 0.5) if n_dis > 1 else 0
    se_adj_dis = sd_dis / (max(n_eff_dis, 1) ** 0.5) if n_dis > 1 else 0
    t_naive_dis = mean_dis / se_naive_dis if se_naive_dis else float("nan")
    t_adj_dis = mean_dis / se_adj_dis if se_adj_dis else float("nan")
    from scipy.stats import norm
    p_naive_dis = 2 * (1 - norm.cdf(abs(t_naive_dis))) if se_naive_dis else float("nan")
    p_adj_dis = 2 * (1 - norm.cdf(abs(t_adj_dis))) if se_adj_dis else float("nan")

    print(f"n={n_dis}, mean advantage={mean_dis:.2f}g, lag-1 autocorr rho={rho_dis:.3f}")
    print(f"Naive n={n_dis} -> effective n = {n_eff_dis:.1f}")
    print(f"Naive: t={t_naive_dis:.3f}, p={p_naive_dis:.6f}")
    print(f"Adjusted: t={t_adj_dis:.3f}, p={p_adj_dis:.6f}")
    small_neff_warning = n_eff_dis < 50
    print(f"Effective n < 50 (needs wide-uncertainty framing): {small_neff_warning}\n")

    out_path = os.path.join(config.DATA_DIR, "subgroup_characterization.json")
    with open(out_path, "w") as f:
        json.dump({
            "n_total": n, "n_agree": n_agree, "n_disagree": n_dis,
            "artifact_check": {
                "canada_estimated_rate_disagreement": dis_canada_est_rate,
                "canada_estimated_rate_agreement": agree_canada_est_rate,
                "sweden_estimated_rate_disagreement": dis_sweden_est_rate,
                "sweden_estimated_rate_agreement": agree_sweden_est_rate,
                "artifact_flag": artifact_flag,
            },
            "seasonal_characterization": {
                "fit_top_months": top_months,
                "fit_month_disagreement_counts": fit_month_counts,
                "test_rate_in_fit_months": rate_in,
                "test_rate_out_fit_months": rate_out,
                "n_test_in_months": len(test_in_months),
                "n_test_out_months": len(test_out_months),
                "seasonal_signal_replicates": seasonal_signal,
            },
            "disagreement_subgroup_autocorrelation": {
                "n": n_dis, "mean_advantage_g": mean_dis, "rho": rho_dis,
                "n_effective": n_eff_dis,
                "t_naive": t_naive_dis, "p_naive": p_naive_dis,
                "t_adjusted": t_adj_dis, "p_adjusted": p_adj_dis,
                "small_neff_warning": small_neff_warning,
            },
        }, f, indent=2, default=str)
    print(f"Saved -> {out_path}")


if __name__ == "__main__":
    main()

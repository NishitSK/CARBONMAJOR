"""
Week 2 of the journal-upgrade plan. The paper's Threats to Validity item 2
discloses that the trained ARIMA/LSTM forecasters influence 0 of 7,304
reported scheduling decisions -- every decision uses only the current hour's
real carbon intensity. This script wires the forecasters into actual
decisions and measures what changes, on the SAME held-out 2024-2025 split
used by held_out_generalization_test.py, so the result is a genuine
out-of-sample test, not a tuned demo.

EXPECTED RESULT, STATED UP FRONT: near-zero additional gain over the
current-hour oracle is the anticipated, acceptable outcome. ARIMA's own
measured 6h MAE (~27 gCO2/kWh, scripts/evaluate_forecasters.py) exceeds the
~10g gap between the Sweden/Canada duo that adaptivity actually exploits
(Section IV-D of the paper's own decomposition), so forecast error should
mostly wash out whatever advantage forecasting could add. A pre-registered
null here is a finding, not a failure -- it closes the one disclosed gap in
the "static region selection captures ~97%" thesis (forecasting never
tried) by showing the conclusion survives even when the scheduler is denied
real-time telemetry and forced onto forecasts. This script does not have a
target number to hit; whatever comes out is reported as-is.

CAUSAL DESIGN. A forecast "for hour t" is built using ONLY data available
strictly before the forecast's effective lead time:
  - ARIMA 6h-ahead: at each anchor t, the trailing 720h window ending at
    (t-6h) is passed to a monthly-refit model's .apply(window, refit=False)
    .forecast(steps=6); only the 6th (last) value -- which lands exactly on
    hour t -- is used.
  - LSTM 24h-ahead: one held-out CarbonLSTM(output_size=24) per zone,
    trained once on data strictly before 2024-01-01 (production
    models/lstm_{zone}.pt is never touched). At each anchor t, the input
    window is the 24 real hours ending at (t-24h); only the 24th (last)
    predicted value -- which lands exactly on hour t -- is used.
This is deliberately NOT forecaster.forecast_next_hours(series_ending_at_t)
-- that would use data up to t, which is exactly the "we already have
current-hour telemetry" case this experiment tests the absence of.

Run from carbon_scheduler/: python scripts/forecast_in_the_loop_replay.py
Takes ~20-25 minutes (288 monthly ARIMA refits x ~2.1s + ~35,000 apply()
calls x ~14ms + LSTM training/inference for 12 zones). Run in the
background or with a long timeout -- do not assume a short default
completes it.

Use --smoke-test to restrict to 2 zones and the first 40 anchors, for
quickly checking the code runs before committing to the full pass.
"""
import argparse
import json
import os
import statistics
import sys
import time
import warnings

import torch
import torch.nn as nn
from statsmodels.tsa.arima.model import ARIMA
from scipy import stats as scipy_stats

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from models.region import Region
from services.scheduler import Scheduler
from services.electricity_service import ElectricityService
from services import lstm_forecaster

HISTORY_DIR = os.path.join(config.DATA_DIR, "history")
CLOUD_LATENCY_PATH = os.path.join(config.DATA_DIR, "cloud_latency.json")
HELDOUT_JSON_PATH = os.path.join(config.DATA_DIR, "held_out_generalization_test.json")
BASELINE_REGION_ZONE = "US-MIDA-PJM"  # us-east-1

TRAIN_END = "2024-01-01T00:00:00.000000"  # same boundary as held_out_generalization_test.py
TEST_START = TRAIN_END

ARIMA_ORDER = (2, 1, 2)
ARIMA_FIT_WINDOW = 4320     # 180 days, hours: trailing window used to REFIT parameters monthly
ARIMA_APPLY_WINDOW = 720    # 30 days, hours: trailing window passed to .apply() at each anchor
ARIMA_HORIZON = 6

LSTM_WINDOW = lstm_forecaster.WINDOW_HOURS  # 24
LSTM_HORIZON = 24
LSTM_EPOCHS = 40


def load_sorted_history():
    """Per-zone full sorted (datetimes, series) + a dt->index map, plus zone_to_region.
    Position-based indexing (not calendar arithmetic) matches the convention
    already used by evaluate_forecasters.py / evaluate_forecasters_seasonal.py:
    a "trailing N hours" window is the N most recent REAL recorded readings
    for that zone, tolerant of the rare missing hour."""
    region_map = ElectricityService.REGION_MAP
    zone_to_region = {meta["zone"]: name for name, meta in region_map.items()}
    dts_by_zone, series_by_zone, idx_by_zone = {}, {}, {}
    for fname in os.listdir(HISTORY_DIR):
        if not fname.startswith("ci_history_"):
            continue
        zone = fname[len("ci_history_"):-len(".json")]
        if zone not in zone_to_region:
            continue
        with open(os.path.join(HISTORY_DIR, fname)) as f:
            records = json.load(f)
        records.sort(key=lambda r: r["datetime"])
        dts = [r["datetime"] for r in records]
        vals = [round(float(r["carbonIntensity"]), 2) for r in records]
        dts_by_zone[zone] = dts
        series_by_zone[zone] = vals
        idx_by_zone[zone] = {dt: i for i, dt in enumerate(dts)}
    return dts_by_zone, series_by_zone, idx_by_zone, zone_to_region


# --------------------------------------------------------------------------
# ARIMA 6h-ahead, monthly refit + apply()-based re-forecast per anchor
# --------------------------------------------------------------------------

def fit_arima_safely(window):
    """Fit ARIMA(2,1,2) on `window`. Returns (fitted_or_None, had_warning, failed)."""
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            fitted = ARIMA(window, order=ARIMA_ORDER).fit()
            had_warning = len(caught) > 0
        return fitted, had_warning, False
    except Exception:
        return None, False, True


def build_arima_forecast_series(series, idx_by_ts, test_anchors):
    """
    Monthly-refit ARIMA(2,1,2); at every anchor t, apply() the most recent
    refit to the real 720h trailing window ending at (t-6h) and take the
    6th (last) forecast step, which lands exactly on hour t. Falls back to
    flat persistence (last real value before t) for any anchor where no
    valid fitted model is available or apply()/forecast() raises.
    """
    forecasts = {}
    current_month, current_fit = None, None
    fits_attempted, fits_failed, fits_warned = 0, 0, 0
    fallback_used = 0

    for ts in test_anchors:
        idx_t = idx_by_ts.get(ts)
        if idx_t is None:
            continue
        month_key = ts[:7]  # "YYYY-MM"

        if month_key != current_month:
            current_month = month_key
            fit_end = idx_t - ARIMA_HORIZON          # fit window ends strictly before t-6h+1
            fit_start = fit_end - ARIMA_FIT_WINDOW
            if fit_start < 0:
                current_fit = None
            else:
                fits_attempted += 1
                fitted, had_warning, failed = fit_arima_safely(series[fit_start:fit_end])
                if failed:
                    fits_failed += 1
                    current_fit = None
                else:
                    if had_warning:
                        fits_warned += 1
                    current_fit = fitted

        apply_end = idx_t - ARIMA_HORIZON            # last index in apply() window = t-6h
        apply_start = apply_end - ARIMA_APPLY_WINDOW + 1
        if apply_start < 0 or current_fit is None:
            fallback_used += 1
            forecasts[ts] = series[apply_end] if apply_end >= 0 else series[0]
            continue

        apply_window = series[apply_start: apply_end + 1]
        try:
            applied = current_fit.apply(apply_window, refit=False)
            forecast = applied.forecast(steps=ARIMA_HORIZON)
            forecasts[ts] = max(0.0, round(float(forecast[-1]), 2))
        except Exception:
            fallback_used += 1
            forecasts[ts] = apply_window[-1]

    diagnostics = {
        "monthly_fits_attempted": fits_attempted,
        "monthly_fits_failed": fits_failed,
        "monthly_fits_converged_with_warnings": fits_warned,
        "monthly_fits_converged_clean": fits_attempted - fits_failed - fits_warned,
        "per_anchor_fallback_count": fallback_used,
    }
    return forecasts, diagnostics


# --------------------------------------------------------------------------
# LSTM 24h-ahead, one held-out model per zone trained once on pre-2024 data
# --------------------------------------------------------------------------

def build_lstm_training_windows(series, lo, hi, window, horizon):
    X, y = [], []
    n = len(series)
    for start in range(0, n - window - horizon):
        w = series[start:start + window]
        target = series[start + window:start + window + horizon]
        seq = []
        for i, val in enumerate(w):
            hour_of_day = (start + i) % 24
            s, c = lstm_forecaster._hour_features(hour_of_day)
            seq.append([(val - lo) / (hi - lo), s, c])
        X.append(seq)
        y.append([(v - lo) / (hi - lo) for v in target])
    return torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)


def train_holdout_lstm(train_series):
    lo, hi = lstm_forecaster._normalize(train_series)
    X, y = build_lstm_training_windows(train_series, lo, hi, LSTM_WINDOW, LSTM_HORIZON)
    model = lstm_forecaster.CarbonLSTM(output_size=LSTM_HORIZON)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    loss_fn = nn.MSELoss()
    model.train()
    for _ in range(LSTM_EPOCHS):
        optimizer.zero_grad()
        pred = model(X)
        loss = loss_fn(pred, y)
        loss.backward()
        optimizer.step()
    model.eval()
    return model, lo, hi


def lstm_predict_at(model, lo, hi, window, window_start_idx):
    start_hour = window_start_idx % 24
    seq = []
    for i, val in enumerate(window):
        hour_of_day = (start_hour + i) % 24
        s, c = lstm_forecaster._hour_features(hour_of_day)
        seq.append([(val - lo) / (hi - lo), s, c])
    with torch.no_grad():
        x = torch.tensor([seq], dtype=torch.float32)
        out = model(x)[0].tolist()
    return [max(0.0, v * (hi - lo) + lo) for v in out]


def build_lstm_forecast_series(dts, series, idx_by_ts, test_anchors):
    """
    Trains one held-out CarbonLSTM(output_size=24) on data strictly before
    2024-01-01, then at every anchor t predicts from the real 24h window
    ending at (t-24h), taking the 24th (last) step, which lands exactly on
    hour t. Never touches production models/lstm_{zone}.pt.
    """
    train_cutoff_idx = next((i for i, dt in enumerate(dts) if dt >= TRAIN_END), len(dts))
    train_series = series[:train_cutoff_idx]
    model, lo, hi = train_holdout_lstm(train_series)

    forecasts = {}
    fallback_used = 0
    for ts in test_anchors:
        idx_t = idx_by_ts.get(ts)
        if idx_t is None:
            continue
        window_end = idx_t - LSTM_HORIZON            # last index in window = t-24h
        window_start = window_end - LSTM_WINDOW + 1
        if window_start < 0:
            fallback_used += 1
            forecasts[ts] = series[max(0, window_end)]
            continue
        window = series[window_start: window_end + 1]
        preds = lstm_predict_at(model, lo, hi, window, window_start)
        forecasts[ts] = round(preds[-1], 2)

    return forecasts, {"per_anchor_fallback_count": fallback_used}


# --------------------------------------------------------------------------
# Replay
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true",
                         help="Restrict to 2 zones and 40 anchors, to check the code runs.")
    args = parser.parse_args()

    t0 = time.time()
    dts_by_zone, series_by_zone, idx_by_zone, zone_to_region = load_sorted_history()
    region_to_zone = {v: k for k, v in zone_to_region.items()}
    with open(CLOUD_LATENCY_PATH) as f:
        static_latency = json.load(f)["latency_ms"]
    with open(HELDOUT_JSON_PATH) as f:
        heldout_baseline = json.load(f)

    # Static lookup and fixed baselines are read from the existing, unmodified
    # script's output -- not hardcoded and not recomputed here.
    static_baseline_ci = heldout_baseline["static_lookup_mean_ci"]
    fixed_baseline_ci = heldout_baseline["fixed_baseline_mean_ci"]
    oracle_baseline_ci_published = heldout_baseline["scheduler_mean_ci"]

    # SLA-eligible zones only: the static-lookup-must-be-eligible fix from
    # pool_generalization_sweep.py applies here too, and for the same
    # reason -- a candidate that could never pass filter_regions() would be
    # an invalid comparison.
    eligible_zones = [
        z for z, region in zone_to_region.items()
        if static_latency.get(region) is not None
        and static_latency[region] <= config.DEFAULT_MAX_LATENCY
    ]
    if args.smoke_test:
        eligible_zones = eligible_zones[:2]
    print(f"SLA-eligible zones ({len(eligible_zones)}): "
          f"{[zone_to_region[z] for z in eligible_zones]}\n")

    common_ts = sorted(set.intersection(*[set(dts_by_zone[z]) for z in dts_by_zone]))
    test_ts = [t for t in common_ts if t >= TEST_START]
    test_sample = test_ts[::6]
    if args.smoke_test:
        test_sample = test_sample[:40]
    print(f"Test anchors: n={len(test_sample)} (2024-2025, 6h stride)\n")

    # --- Precompute forecast series per eligible zone ---
    arima_forecasts_by_zone, arima_diag_by_zone = {}, {}
    lstm_forecasts_by_zone, lstm_diag_by_zone = {}, {}

    for i, zone in enumerate(eligible_zones):
        t_zone = time.time()
        idx_by_ts = idx_by_zone[zone]
        dts = dts_by_zone[zone]
        series = series_by_zone[zone]

        arima_fc, arima_diag = build_arima_forecast_series(series, idx_by_ts, test_sample)
        arima_forecasts_by_zone[zone] = arima_fc
        arima_diag_by_zone[zone] = arima_diag

        lstm_fc, lstm_diag = build_lstm_forecast_series(dts, series, idx_by_ts, test_sample)
        lstm_forecasts_by_zone[zone] = lstm_fc
        lstm_diag_by_zone[zone] = lstm_diag

        print(f"[{i+1}/{len(eligible_zones)}] {zone_to_region[zone]:<30} "
              f"ARIMA: fits={arima_diag['monthly_fits_attempted']} "
              f"failed={arima_diag['monthly_fits_failed']} "
              f"warned={arima_diag['monthly_fits_converged_with_warnings']} "
              f"fallback={arima_diag['per_anchor_fallback_count']}  |  "
              f"LSTM fallback={lstm_diag['per_anchor_fallback_count']}  "
              f"({time.time()-t_zone:.1f}s)")

    print(f"\nForecast precompute done in {time.time()-t0:.1f}s\n")

    # --- Replay: oracle (current-hour, recomputed here for per-decision
    #     arrays -- held_out_generalization_test.json only stores aggregates)
    #     vs. ARIMA-driven vs. LSTM-driven, all through the SAME unmodified
    #     Scheduler.filter_regions()/calculate_scores() ---
    scheduler = Scheduler()
    oracle_carbon, arima_carbon, lstm_carbon = [], [], []
    oracle_winner, arima_winner, lstm_winner = [], [], []

    for ts in test_sample:
        oracle_regions, arima_regions, lstm_regions = [], [], []
        for zone in eligible_zones:
            region_name = zone_to_region[zone]
            lat = static_latency.get(region_name)
            idx = idx_by_zone[zone].get(ts)
            if lat is None or idx is None:
                continue
            real_ci = series_by_zone[zone][idx]
            arima_ci = arima_forecasts_by_zone[zone].get(ts, real_ci)
            lstm_ci = lstm_forecasts_by_zone[zone].get(ts, real_ci)

            oracle_regions.append(Region(name=region_name, carbon=real_ci, latency=lat, resources=80.0))
            arima_regions.append(Region(name=region_name, carbon=arima_ci, latency=lat, resources=80.0))
            lstm_regions.append(Region(name=region_name, carbon=lstm_ci, latency=lat, resources=80.0))

        if not oracle_regions:
            continue

        elig_o = scheduler.filter_regions(oracle_regions, config.DEFAULT_MAX_LATENCY)
        elig_a = scheduler.filter_regions(arima_regions, config.DEFAULT_MAX_LATENCY)
        elig_l = scheduler.filter_regions(lstm_regions, config.DEFAULT_MAX_LATENCY)
        if not elig_o or not elig_a or not elig_l:
            continue

        w_o = scheduler.calculate_scores(elig_o, config.DEFAULT_WEIGHTS)[0][0]
        w_a = scheduler.calculate_scores(elig_a, config.DEFAULT_WEIGHTS)[0][0]
        w_l = scheduler.calculate_scores(elig_l, config.DEFAULT_WEIGHTS)[0][0]

        # Actual emissions are determined by the true grid state, not the
        # forecast that chose the region -- so realized carbon always looks
        # up the REAL CI of the winning region at the real hour.
        def realized(region_obj):
            zone = region_to_zone[region_obj.name]
            idx = idx_by_zone[zone].get(ts)
            return series_by_zone[zone][idx]

        oracle_carbon.append(realized(w_o))
        arima_carbon.append(realized(w_a))
        lstm_carbon.append(realized(w_l))
        oracle_winner.append(w_o.name)
        arima_winner.append(w_a.name)
        lstm_winner.append(w_l.name)

    n = len(oracle_carbon)
    oracle_mean = statistics.mean(oracle_carbon)
    arima_mean = statistics.mean(arima_carbon)
    lstm_mean = statistics.mean(lstm_carbon)

    arima_agree = sum(1 for o, a in zip(oracle_winner, arima_winner) if o == a)
    lstm_agree = sum(1 for o, l in zip(oracle_winner, lstm_winner) if o == l)

    t_arima, p_arima = scipy_stats.ttest_rel(arima_carbon, oracle_carbon)
    t_lstm, p_lstm = scipy_stats.ttest_rel(lstm_carbon, oracle_carbon)

    arima_vs_static = (static_baseline_ci - arima_mean) / static_baseline_ci * 100
    arima_vs_fixed = (fixed_baseline_ci - arima_mean) / fixed_baseline_ci * 100
    lstm_vs_static = (static_baseline_ci - lstm_mean) / static_baseline_ci * 100
    lstm_vs_fixed = (fixed_baseline_ci - lstm_mean) / fixed_baseline_ci * 100

    oracle_discrepancy = oracle_mean - oracle_baseline_ci_published

    # --- ARIMA diagnostics rolled up across all zones ---
    total_fits = sum(d["monthly_fits_attempted"] for d in arima_diag_by_zone.values())
    total_failed = sum(d["monthly_fits_failed"] for d in arima_diag_by_zone.values())
    total_warned = sum(d["monthly_fits_converged_with_warnings"] for d in arima_diag_by_zone.values())
    total_clean = sum(d["monthly_fits_converged_clean"] for d in arima_diag_by_zone.values())
    total_arima_fallback = sum(d["per_anchor_fallback_count"] for d in arima_diag_by_zone.values())
    total_lstm_fallback = sum(d["per_anchor_fallback_count"] for d in lstm_diag_by_zone.values())

    print("=" * 78)
    print("FORECAST-IN-THE-LOOP REPLAY -- held-out 2024-2025, n={} decisions".format(n))
    print("=" * 78)
    print(f"Oracle (current-hour, real telemetry):  {oracle_mean:.2f}g avg CI  "
          f"[published: {oracle_baseline_ci_published:.2f}g, discrepancy={oracle_discrepancy:+.4f}g]")
    print(f"ARIMA-6h-forecast-driven scheduler:      {arima_mean:.2f}g avg CI")
    print(f"LSTM-24h-forecast-driven scheduler:       {lstm_mean:.2f}g avg CI")
    print(f"Static lookup (from held_out json):     {static_baseline_ci:.2f}g avg CI")
    print(f"Fixed baseline (from held_out json):    {fixed_baseline_ci:.2f}g avg CI\n")

    print(f"ARIMA-driven vs static lookup: {arima_vs_static:+.2f}%   vs fixed baseline: {arima_vs_fixed:+.2f}%")
    print(f"LSTM-driven  vs static lookup: {lstm_vs_static:+.2f}%   vs fixed baseline: {lstm_vs_fixed:+.2f}%\n")

    print(f"Agreement with oracle's winning region:")
    print(f"  ARIMA-driven: {arima_agree}/{n} ({100*arima_agree/n:.1f}%)")
    print(f"  LSTM-driven:  {lstm_agree}/{n} ({100*lstm_agree/n:.1f}%)\n")

    print(f"Paired t-test, ARIMA-driven vs oracle per-decision CI: t={t_arima:.3f}, p={p_arima:.6f}")
    print(f"Paired t-test, LSTM-driven vs oracle per-decision CI:  t={t_lstm:.3f}, p={p_lstm:.6f}\n")

    print(f"ARIMA fit diagnostics (across all zones x months, {len(eligible_zones)} zones):")
    print(f"  Attempted: {total_fits}  |  Failed (exception, fallback used): {total_failed}  |  "
          f"Converged with warnings: {total_warned}  |  Converged clean: {total_clean}")
    print(f"  Per-anchor fallback triggers -- ARIMA: {total_arima_fallback}  |  LSTM: {total_lstm_fallback}")

    out = {
        "n_decisions": n,
        "oracle_mean_ci": oracle_mean,
        "oracle_mean_ci_published_reference": oracle_baseline_ci_published,
        "oracle_discrepancy_g": oracle_discrepancy,
        "arima_forecast_driven_mean_ci": arima_mean,
        "lstm_forecast_driven_mean_ci": lstm_mean,
        "static_lookup_mean_ci_reference": static_baseline_ci,
        "fixed_baseline_mean_ci_reference": fixed_baseline_ci,
        "arima_vs_static_lookup_pct": arima_vs_static,
        "arima_vs_fixed_baseline_pct": arima_vs_fixed,
        "lstm_vs_static_lookup_pct": lstm_vs_static,
        "lstm_vs_fixed_baseline_pct": lstm_vs_fixed,
        "agreement_with_oracle": {
            "arima_agree_count": arima_agree,
            "arima_agree_pct": 100 * arima_agree / n,
            "lstm_agree_count": lstm_agree,
            "lstm_agree_pct": 100 * lstm_agree / n,
        },
        "paired_t_test_vs_oracle": {
            "arima": {"t_stat": float(t_arima), "p_value": float(p_arima)},
            "lstm": {"t_stat": float(t_lstm), "p_value": float(p_lstm)},
        },
        "arima_fit_diagnostics": {
            "monthly_fits_attempted_total": total_fits,
            "monthly_fits_failed_total": total_failed,
            "monthly_fits_converged_with_warnings_total": total_warned,
            "monthly_fits_converged_clean_total": total_clean,
            "per_anchor_fallback_total": total_arima_fallback,
            "per_zone": arima_diag_by_zone,
        },
        "lstm_fit_diagnostics": {
            "per_anchor_fallback_total": total_lstm_fallback,
            "per_zone": lstm_diag_by_zone,
        },
        "smoke_test": args.smoke_test,
    }

    if not args.smoke_test:
        out_path = os.path.join(config.DATA_DIR, "forecast_in_the_loop_replay.json")
        with open(out_path, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\nSaved -> {out_path}")
    else:
        print("\n[smoke test] not saved to disk")

    print(f"\nTotal elapsed: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()

"""
Workstream B of the "earning AI Scheduling for real" plan. schedule_delay_
tolerant() ([services/scheduler.py]) already makes a real decision -- when
within a look-ahead window to run a delay-tolerant workload -- but decides
it using forecaster.forecast_quarter_hour_window(), which forecasts on top
of a FABRICATED synthetic diurnal curve (generate_synthetic_history()), not
real data. This is the one seam in the whole system where genuine AI
forecasting could drive a genuine decision; this script measures whether
switching it to the real, validated forecasters (ARIMA <=6h, LSTM up to
24h, matching the paper's own documented crossover) actually helps.

Does NOT touch filter_regions()/calculate_scores() or any already-published
spatial-decision number. Region selection at each anchor is computed via
the unmodified Scheduler exactly as in every other script; this benchmark
only compares TEMPORAL policies within the region that decision already
picked.

FOUR POLICIES, same anchors, same region, same deadline, per anchor:
  (a) No shift      -- run immediately at the real current-hour CI.
  (b) Current system -- forecaster.forecast_quarter_hour_window() (synthetic
      diurnal curve), unmodified, called exactly as production does.
  (c) Real-AI-forecast-driven -- adaptive-horizon real forecast (ARIMA
      <=6h monthly-refit + apply(), LSTM >6h held-out, both causal: only
      data up to and including "now" is used to forecast the future).
  (d) Oracle -- perfect-hindsight minimum real CI across [now, deadline].
All four pick a quarter-hour offset from their own information; REALIZED
carbon always looks up the REAL hourly CI of the hour containing that
offset (the forecast/oracle picks the timing, reality determines the
emissions -- same principle as forecast_in_the_loop_replay.py).

The number that matters: (c) minus (b), the incremental value of real
forecasting over the synthetic stand-in it would replace, and how much of
the achievable (d)-(a) gap (c) actually captures. No target to hit --
report whatever comes out, same as Workstream A.

Run from carbon_scheduler/: python scripts/temporal_shift_benchmark.py
Takes ~35-40 minutes (10 zones x 24 monthly ARIMA refits ~2.1s each, plus
held-out LSTM training per zone ~2 min each, plus a cheap anchor x deadline
replay loop). Run in the background or with a long timeout.

Use --smoke-test to restrict to 2 zones and the first 40 anchors.
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

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from models.region import Region
from services.scheduler import Scheduler
from services.electricity_service import ElectricityService
from services import forecaster, lstm_forecaster

HISTORY_DIR = os.path.join(config.DATA_DIR, "history")
CLOUD_LATENCY_PATH = os.path.join(config.DATA_DIR, "cloud_latency.json")

TRAIN_END = "2024-01-01T00:00:00.000000"  # same boundary as held_out_generalization_test.py
TEST_START = TRAIN_END

ARIMA_ORDER = (2, 1, 2)
ARIMA_FIT_WINDOW = 4320     # 180 days, hours: trailing window used to REFIT parameters monthly
ARIMA_APPLY_WINDOW = 720    # 30 days, hours: trailing window passed to .apply() at each anchor
ARIMA_MAX_HORIZON = 6       # ARIMA path used for deadlines <= this many hours

LSTM_WINDOW = lstm_forecaster.WINDOW_HOURS  # 24
LSTM_HORIZON = 24
LSTM_EPOCHS = 40

DEADLINE_HOURS_TESTED = [1, 4, 8, 24]


def load_sorted_history():
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
# ARIMA: monthly refit, then apply() FORWARD from "now" (idx_t inclusive)
# --------------------------------------------------------------------------

def fit_arima_safely(window):
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            fitted = ARIMA(window, order=ARIMA_ORDER).fit()
            had_warning = len(caught) > 0
        return fitted, had_warning, False
    except Exception:
        return None, False, True


def build_monthly_arima_fits(series, idx_by_ts, test_anchors):
    """One ARIMA(2,1,2) refit per calendar month, on the trailing 4320h
    window ending strictly before that month's first anchor. Returns
    {month_key: fitted_or_None} and diagnostics."""
    fits = {}
    fits_attempted, fits_failed, fits_warned = 0, 0, 0
    seen_months = set()
    for ts in test_anchors:
        month_key = ts[:7]
        if month_key in seen_months:
            continue
        seen_months.add(month_key)
        idx_t = idx_by_ts.get(ts)
        if idx_t is None:
            fits[month_key] = None
            continue
        fit_end = idx_t
        fit_start = fit_end - ARIMA_FIT_WINDOW
        if fit_start < 0:
            fits[month_key] = None
            continue
        fits_attempted += 1
        fitted, had_warning, failed = fit_arima_safely(series[fit_start:fit_end])
        if failed:
            fits_failed += 1
            fits[month_key] = None
        else:
            if had_warning:
                fits_warned += 1
            fits[month_key] = fitted
    diagnostics = {
        "monthly_fits_attempted": fits_attempted,
        "monthly_fits_failed": fits_failed,
        "monthly_fits_converged_with_warnings": fits_warned,
        "monthly_fits_converged_clean": fits_attempted - fits_failed - fits_warned,
    }
    return fits, diagnostics


def arima_forward_forecast(monthly_fits, series, idx_t, month_key, n_hours):
    """Forecast n_hours FORWARD from idx_t (inclusive of "now"), using the
    month's fitted model applied to the real 720h trailing window ending
    at idx_t. Falls back to flat persistence if no fit is available or
    apply()/forecast() raises."""
    fitted = monthly_fits.get(month_key)
    apply_start = idx_t - ARIMA_APPLY_WINDOW + 1
    if fitted is None or apply_start < 0:
        return [series[idx_t]] * n_hours, True
    apply_window = series[apply_start: idx_t + 1]
    try:
        applied = fitted.apply(apply_window, refit=False)
        forecast = applied.forecast(steps=n_hours)
        return [max(0.0, round(float(v), 2)) for v in forecast], False
    except Exception:
        return [apply_window[-1]] * n_hours, True


# --------------------------------------------------------------------------
# LSTM: one held-out model per zone, trained once on pre-2024 data
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


def lstm_forward_forecast(lstm_bundle, series, idx_t, n_hours):
    """Forecast n_hours FORWARD from idx_t (inclusive of "now"), using the
    real 24h window ending at idx_t. n_hours must be <= LSTM_HORIZON (24)."""
    model, lo, hi = lstm_bundle
    window_start = idx_t - LSTM_WINDOW + 1
    if window_start < 0:
        return [series[idx_t]] * n_hours, True
    window = series[window_start: idx_t + 1]
    preds = lstm_predict_at(model, lo, hi, window, window_start)
    return preds[:n_hours], False


# --------------------------------------------------------------------------
# Quarter-hour interpolation + decision (shared logic for policies b/c)
# --------------------------------------------------------------------------

def interpolate_quarter_hour(current_ci, hourly_forecast):
    """Same linear interpolation as forecaster.forecast_quarter_hour_window():
    point i (0-indexed) corresponds to t + 15*(i+1) minutes from now."""
    anchors = [current_ci] + list(hourly_forecast)
    points = []
    for h in range(len(hourly_forecast)):
        start, end = anchors[h], anchors[h + 1]
        for step in range(1, 5):
            frac = step / 4
            points.append(start + (end - start) * frac)
    return points


def best_offset_and_hour(quarter_hour_forecast):
    """argmin over the forecast series; returns (offset_idx, hour_block)
    where hour_block = offset_idx // 4 is which post-"now" real hour
    (0-indexed: hour_block=0 is the first hour after now) the chosen
    offset falls into."""
    offset_idx = min(range(len(quarter_hour_forecast)), key=lambda i: quarter_hour_forecast[i])
    return offset_idx, offset_idx // 4


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()

    t0 = time.time()
    dts_by_zone, series_by_zone, idx_by_zone, zone_to_region = load_sorted_history()
    with open(CLOUD_LATENCY_PATH) as f:
        static_latency = json.load(f)["latency_ms"]

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

    # --- Precompute per-zone: monthly ARIMA fits + held-out LSTM ---
    arima_fits_by_zone, arima_diag_by_zone = {}, {}
    lstm_by_zone = {}

    for i, zone in enumerate(eligible_zones):
        t_zone = time.time()
        idx_by_ts = idx_by_zone[zone]
        series = series_by_zone[zone]
        dts = dts_by_zone[zone]

        fits, diag = build_monthly_arima_fits(series, idx_by_ts, test_sample)
        arima_fits_by_zone[zone] = fits
        arima_diag_by_zone[zone] = diag

        train_cutoff_idx = next((k for k, dt in enumerate(dts) if dt >= TRAIN_END), len(dts))
        model, lo, hi = train_holdout_lstm(series[:train_cutoff_idx])
        lstm_by_zone[zone] = (model, lo, hi)

        print(f"[{i+1}/{len(eligible_zones)}] {zone_to_region[zone]:<30} "
              f"ARIMA fits={diag['monthly_fits_attempted']} failed={diag['monthly_fits_failed']} "
              f"warned={diag['monthly_fits_converged_with_warnings']}  ({time.time()-t_zone:.1f}s)")

    print(f"\nPrecompute done in {time.time()-t0:.1f}s\n")

    # --- Replay: pick region via the UNMODIFIED spatial scheduler, then
    #     compare 4 temporal policies within that region, per deadline ---
    scheduler = Scheduler()
    results = {d: {"no_shift": [], "synthetic": [], "real_ai": [], "oracle": []} for d in DEADLINE_HOURS_TESTED}
    arima_fallback_count = {d: 0 for d in DEADLINE_HOURS_TESTED}
    lstm_fallback_count = {d: 0 for d in DEADLINE_HOURS_TESTED}
    n_scored = 0

    max_deadline = max(DEADLINE_HOURS_TESTED)

    for ts in test_sample:
        candidates = []
        for zone in eligible_zones:
            region_name = zone_to_region[zone]
            lat = static_latency.get(region_name)
            idx = idx_by_zone[zone].get(ts)
            if lat is None or idx is None:
                continue
            real_ci = series_by_zone[zone][idx]
            candidates.append(Region(name=region_name, carbon=real_ci, latency=lat, resources=80.0))
        if not candidates:
            continue

        eligible = scheduler.filter_regions(candidates, config.DEFAULT_MAX_LATENCY)
        if not eligible:
            continue
        winner = scheduler.calculate_scores(eligible, config.DEFAULT_WEIGHTS)[0][0]

        # find the winning region's zone code to index its own series/idx maps
        winner_zone = next(z for z in eligible_zones if zone_to_region[z] == winner.name)
        idx_t = idx_by_zone[winner_zone].get(ts)
        series = series_by_zone[winner_zone]
        if idx_t is None or idx_t + max_deadline >= len(series):
            continue  # not enough real future data to score the longest deadline fairly

        current_ci = series[idx_t]
        month_key = ts[:7]

        n_scored += 1
        for deadline in DEADLINE_HOURS_TESTED:
            # (a) No shift
            no_shift_ci = current_ci

            # (b) Current system: synthetic-forecast-driven, unmodified production call
            synthetic_qh = forecaster.forecast_quarter_hour_window(
                current_ci, hours=deadline, seed=hash((winner_zone, ts)) % (2**31)
            )
            _, hour_block_b = best_offset_and_hour(synthetic_qh)
            realized_b = series[idx_t + hour_block_b + 1]

            # (c) Real-AI-forecast-driven: adaptive horizon, causal, forward from "now"
            if deadline <= ARIMA_MAX_HORIZON:
                hourly_fc, fell_back = arima_forward_forecast(
                    arima_fits_by_zone[winner_zone], series, idx_t, month_key, n_hours=deadline
                )
                if fell_back:
                    arima_fallback_count[deadline] += 1
            else:
                hourly_fc, fell_back = lstm_forward_forecast(
                    lstm_by_zone[winner_zone], series, idx_t, n_hours=deadline
                )
                if fell_back:
                    lstm_fallback_count[deadline] += 1
            real_qh = interpolate_quarter_hour(current_ci, hourly_fc)
            _, hour_block_c = best_offset_and_hour(real_qh)
            realized_c = series[idx_t + hour_block_c + 1]

            # (d) Oracle: perfect hindsight over [now, now+deadline] inclusive
            oracle_ci = min(series[idx_t: idx_t + deadline + 1])

            results[deadline]["no_shift"].append(no_shift_ci)
            results[deadline]["synthetic"].append(realized_b)
            results[deadline]["real_ai"].append(realized_c)
            results[deadline]["oracle"].append(oracle_ci)

    print(f"Decisions scored: n={n_scored}\n")

    # --- Report ---
    print("=" * 96)
    print("TEMPORAL-SHIFT BENCHMARK -- held-out 2024-2025, region fixed by the unmodified spatial scheduler")
    print("=" * 96)

    summary = {}
    for deadline in DEADLINE_HOURS_TESTED:
        r = results[deadline]
        n = len(r["no_shift"])
        no_shift_mean = statistics.mean(r["no_shift"])
        synthetic_mean = statistics.mean(r["synthetic"])
        real_ai_mean = statistics.mean(r["real_ai"])
        oracle_mean = statistics.mean(r["oracle"])

        def pct_improve(mean_val):
            return (no_shift_mean - mean_val) / no_shift_mean * 100 if no_shift_mean else float("nan")

        synthetic_improve = pct_improve(synthetic_mean)
        real_ai_improve = pct_improve(real_ai_mean)
        oracle_improve = pct_improve(oracle_mean)
        real_minus_synthetic = real_ai_improve - synthetic_improve
        achievable_gap = no_shift_mean - oracle_mean
        real_ai_gap_closed = ((no_shift_mean - real_ai_mean) / achievable_gap * 100) if achievable_gap else float("nan")

        print(f"\n--- Deadline: {deadline}h (n={n}) ---")
        print(f"No shift:    {no_shift_mean:.2f}g avg CI")
        print(f"Synthetic (current system): {synthetic_mean:.2f}g avg CI  ({synthetic_improve:+.2f}% vs no-shift)")
        print(f"Real-AI-forecast-driven:    {real_ai_mean:.2f}g avg CI  ({real_ai_improve:+.2f}% vs no-shift)")
        print(f"Oracle (perfect hindsight): {oracle_mean:.2f}g avg CI  ({oracle_improve:+.2f}% vs no-shift)")
        print(f"Real AI minus synthetic (incremental value of real forecasting): {real_minus_synthetic:+.2f} pp")
        print(f"Real AI captures {real_ai_gap_closed:.1f}% of the achievable no-shift-to-oracle gap")
        if deadline <= ARIMA_MAX_HORIZON:
            print(f"ARIMA fallback triggers: {arima_fallback_count[deadline]}/{n}")
        else:
            print(f"LSTM fallback triggers: {lstm_fallback_count[deadline]}/{n}")

        summary[str(deadline)] = {
            "n": n,
            "no_shift_mean_ci": no_shift_mean,
            "synthetic_mean_ci": synthetic_mean,
            "real_ai_mean_ci": real_ai_mean,
            "oracle_mean_ci": oracle_mean,
            "synthetic_improve_vs_no_shift_pct": synthetic_improve,
            "real_ai_improve_vs_no_shift_pct": real_ai_improve,
            "oracle_improve_vs_no_shift_pct": oracle_improve,
            "real_ai_minus_synthetic_pp": real_minus_synthetic,
            "real_ai_pct_of_achievable_gap_closed": real_ai_gap_closed,
            "arima_fallback_count": arima_fallback_count[deadline],
            "lstm_fallback_count": lstm_fallback_count[deadline],
        }

    out = {
        "n_zones": len(eligible_zones),
        "n_anchors_scored": n_scored,
        "deadlines_tested_hours": DEADLINE_HOURS_TESTED,
        "results_by_deadline": summary,
        "arima_fit_diagnostics_per_zone": arima_diag_by_zone,
        "smoke_test": args.smoke_test,
    }

    if not args.smoke_test:
        out_path = os.path.join(config.DATA_DIR, "temporal_shift_benchmark.json")
        with open(out_path, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\nSaved -> {out_path}")
    else:
        print("\n[smoke test] not saved to disk")

    print(f"\nTotal elapsed: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()

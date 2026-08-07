"""
Equivalence check: proves services/real_temporal_forecaster.py produces
IDENTICAL output to the already-validated logic inside
scripts/temporal_shift_benchmark.py (the script that actually produced
data/temporal_shift_benchmark.json), on real data, before the new module is
trusted for a live AWS deployment.

Loads temporal_shift_benchmark.py as a module directly (not reimplemented
here) so the "old" side of the comparison is provably the exact validated
code, not a paraphrase of it. Fits one real monthly ARIMA model and one real
held-out LSTM for a single zone, then compares both modules' forward-forecast
functions on several real anchor points for both the ARIMA (4h) and LSTM
(24h) paths.

Run from carbon_scheduler/: python scripts/verify_real_temporal_forecaster.py
"""
import importlib.util
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from services import real_temporal_forecaster as rtf

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TSB_PATH = os.path.join(SCRIPT_DIR, "temporal_shift_benchmark.py")

spec = importlib.util.spec_from_file_location("temporal_shift_benchmark", TSB_PATH)
tsb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tsb)


def main():
    dts_by_zone, series_by_zone, idx_by_zone, zone_to_region = tsb.load_sorted_history()
    zone = "SE"  # Sweden - always SLA-eligible, dominant region, plenty of history
    series = series_by_zone[zone]
    dts = dts_by_zone[zone]
    idx_by_ts = idx_by_zone[zone]

    test_start_idx = next(i for i, dt in enumerate(dts) if dt >= tsb.TRAIN_END)
    # A handful of real anchors spread across the held-out period
    check_indices = [test_start_idx + k * 2000 for k in range(6)
                      if test_start_idx + k * 2000 + 24 < len(series)]

    print(f"Zone: {zone}, checking {len(check_indices)} anchor points\n")

    # --- ARIMA path: fit ONE real monthly model, apply at each check point ---
    fit_end = check_indices[0]
    fit_start = fit_end - tsb.ARIMA_FIT_WINDOW
    fitted, had_warning, failed = tsb.fit_arima_safely(series[fit_start:fit_end])
    assert not failed, "ARIMA fit failed on real data - cannot verify"
    print(f"Fitted one real ARIMA(2,1,2) model on window [{fit_start}:{fit_end}) (warning={had_warning})\n")

    arima_mismatches = 0
    for idx_t in check_indices:
        month_key = dts[idx_t][:7]
        old_forecast, old_fallback = tsb.arima_forward_forecast(
            {month_key: fitted}, series, idx_t, month_key, n_hours=4)

        apply_start = idx_t - rtf.ARIMA_MAX_HORIZON_HOURS * 0  # unused, kept for clarity
        trailing = series[idx_t - tsb.ARIMA_APPLY_WINDOW + 1: idx_t + 1]
        new_forecast, new_fallback = rtf.forecast_arima_forward(fitted, trailing, hours=4)

        match = old_forecast == new_forecast and old_fallback == new_fallback
        if not match:
            arima_mismatches += 1
        print(f"  idx={idx_t} ({dts[idx_t]}): old={old_forecast} fallback={old_fallback} | "
              f"new={new_forecast} fallback={new_fallback} | {'MATCH' if match else 'MISMATCH'}")

    # --- LSTM path: train ONE real held-out model, predict at each check point ---
    print("\nTraining one real held-out LSTM (output_size=24) on pre-2024 data...")
    train_cutoff_idx = next((k for k, dt in enumerate(dts) if dt >= tsb.TRAIN_END), len(dts))
    model, lo, hi = tsb.train_holdout_lstm(series[:train_cutoff_idx])
    lstm_bundle_new_style = {"model": model, "lo": lo, "hi": hi}
    print("Done.\n")

    lstm_mismatches = 0
    for idx_t in check_indices:
        old_forecast, old_fallback = tsb.lstm_forward_forecast((model, lo, hi), series, idx_t, n_hours=24)

        window_start_idx = idx_t - tsb.LSTM_WINDOW + 1
        trailing_24h = series[window_start_idx: idx_t + 1]
        new_forecast, new_fallback = rtf.forecast_lstm_forward(
            lstm_bundle_new_style, trailing_24h, window_start_hour_of_day=window_start_idx % 24, hours=24)

        match = old_forecast == new_forecast and old_fallback == new_fallback
        if not match:
            lstm_mismatches += 1
        print(f"  idx={idx_t} ({dts[idx_t]}): old[:3]={old_forecast[:3]} | "
              f"new[:3]={new_forecast[:3]} | {'MATCH' if match else 'MISMATCH'}")

    print(f"\n{'='*60}")
    print(f"ARIMA path: {len(check_indices) - arima_mismatches}/{len(check_indices)} match")
    print(f"LSTM path:  {len(check_indices) - lstm_mismatches}/{len(check_indices)} match")
    if arima_mismatches == 0 and lstm_mismatches == 0:
        print("\nVERIFIED: real_temporal_forecaster.py is behaviorally identical to the "
              "validated temporal_shift_benchmark.py logic on this sample. Safe to use as "
              "the basis for a live deployment.")
    else:
        print("\nNOT VERIFIED: mismatches found. Do not use real_temporal_forecaster.py for "
              "a live deployment until this is resolved.")


if __name__ == "__main__":
    main()

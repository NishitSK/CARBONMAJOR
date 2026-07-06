"""
Seasonal multi-window backtest: trains ONE held-out LSTM per zone on
2021-2024 only (entire 2025 unseen during training), then walk-forward
evaluates it against ARIMA and naive persistence across FOUR separate,
non-overlapping 7-day windows spread across all four seasons of 2025.

This directly answers "is the 6h-vs-24h crossover just one lucky/unlucky
December week?" by testing across winter/spring/summer/autumn instead of
a single calendar week.

Does NOT touch production models/lstm_{zone}.pt files.

Run from carbon_scheduler/:
    python scripts/evaluate_forecasters_seasonal.py --horizon 6
    python scripts/evaluate_forecasters_seasonal.py --horizon 24
"""
import argparse
import glob
import json
import os
import sys
import time

import torch
import torch.nn as nn

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from services import lstm_forecaster, forecaster

HISTORY_DIR = os.path.join(config.DATA_DIR, "history")
TRAIN_CUTOFF = "2025-01-01T00:00:00.000000"  # train on everything before this
SEASON_WINDOWS = [
    ("Winter", "2025-02-01T00:00:00.000000", 168),
    ("Spring", "2025-05-01T00:00:00.000000", 168),
    ("Summer", "2025-08-01T00:00:00.000000", 168),
    ("Autumn", "2025-11-01T00:00:00.000000", 168),
]
ANCHOR_STEP = 6
WINDOW = lstm_forecaster.WINDOW_HOURS  # 24h input
EPOCHS = 40


def load_sorted(zone_path):
    with open(zone_path) as f:
        history = json.load(f)
    history.sort(key=lambda e: e["datetime"])
    datetimes = [e["datetime"] for e in history]
    series = [round(float(e["carbonIntensity"]), 2) for e in history]
    return datetimes, series


def build_windows(series, lo, hi, window, horizon, abs_offset):
    X, y = [], []
    n = len(series)
    for start in range(0, n - window - horizon):
        w = series[start:start + window]
        target = series[start + window:start + window + horizon]
        seq = []
        for i, val in enumerate(w):
            h = (abs_offset + start + i) % 24
            s, c = lstm_forecaster._hour_features(h)
            seq.append([(val - lo) / (hi - lo), s, c])
        X.append(seq)
        y.append([(v - lo) / (hi - lo) for v in target])
    return torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)


def train_holdout_model(train_series, horizon):
    lo, hi = lstm_forecaster._normalize(train_series)
    X, y = build_windows(train_series, lo, hi, WINDOW, horizon, abs_offset=0)
    model = lstm_forecaster.CarbonLSTM(output_size=horizon)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    loss_fn = nn.MSELoss()
    model.train()
    for _ in range(EPOCHS):
        optimizer.zero_grad()
        pred = model(X)
        loss = loss_fn(pred, y)
        loss.backward()
        optimizer.step()
    model.eval()
    return model, lo, hi


def lstm_predict(model, lo, hi, window, start_hour_of_day):
    seq = []
    for i, val in enumerate(window):
        h = (start_hour_of_day + i) % 24
        s, c = lstm_forecaster._hour_features(h)
        seq.append([(val - lo) / (hi - lo), s, c])
    with torch.no_grad():
        x = torch.tensor([seq], dtype=torch.float32)
        out = model(x)[0].tolist()
    return [max(0.0, v * (hi - lo) + lo) for v in out]


def mae(actual, predicted):
    return sum(abs(a - p) for a, p in zip(actual, predicted)) / len(actual)


def evaluate_zone(zone, datetimes, series, horizon):
    train_cutoff_idx = next((i for i, dt in enumerate(datetimes) if dt >= TRAIN_CUTOFF), len(datetimes))
    train_series = series[:train_cutoff_idx]
    model, lo, hi = train_holdout_model(train_series, horizon)

    season_results = {}
    for season_name, start_dt, holdout_hours in SEASON_WINDOWS:
        start_idx = next((i for i, dt in enumerate(datetimes) if dt >= start_dt), None)
        if start_idx is None or start_idx < WINDOW:
            season_results[season_name] = None
            continue
        context_start = start_idx - WINDOW
        test_series = series[context_start: start_idx + holdout_hours]

        n_anchors = (holdout_hours - horizon) // ANCHOR_STEP
        lstm_maes, arima_maes, persist_maes = [], [], []
        for a in range(n_anchors):
            idx = a * ANCHOR_STEP
            w = test_series[idx: idx + WINDOW]
            actual = test_series[idx + WINDOW: idx + WINDOW + horizon]
            if len(w) < WINDOW or len(actual) < horizon:
                continue
            start_hour = (context_start + idx) % 24

            lstm_pred = lstm_predict(model, lo, hi, w, start_hour)
            arima_pred = forecaster.forecast_next_hours(w, n_hours=horizon)
            persist_pred = [w[-1]] * horizon

            lstm_maes.append(mae(actual, lstm_pred))
            arima_maes.append(mae(actual, arima_pred))
            persist_maes.append(mae(actual, persist_pred))

        avg = lambda lst: sum(lst) / len(lst) if lst else float("nan")
        season_results[season_name] = {
            "n_anchors": len(lstm_maes),
            "lstm_mae": avg(lstm_maes),
            "arima_mae": avg(arima_maes),
            "persistence_mae": avg(persist_maes),
        }
    return season_results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizon", type=int, default=6, choices=[6, 24])
    args = parser.parse_args()
    horizon = args.horizon

    history_files = sorted(glob.glob(os.path.join(HISTORY_DIR, "ci_history_*.json")))
    all_results = {}
    t0 = time.time()

    for path in history_files:
        zone = os.path.basename(path).replace("ci_history_", "").replace(".json", "")
        datetimes, series = load_sorted(path)
        if len(series) < 8760:
            print(f"{zone}: SKIPPED (insufficient history)")
            continue
        season_results = evaluate_zone(zone, datetimes, series, horizon)
        all_results[zone] = season_results

        row = f"{zone:14s} "
        for season_name, _, _ in SEASON_WINDOWS:
            r = season_results.get(season_name)
            if r:
                row += f"| {season_name}: L={r['lstm_mae']:.1f} A={r['arima_mae']:.1f} P={r['persistence_mae']:.1f} "
            else:
                row += f"| {season_name}: SKIPPED "
        print(row)

    print(f"\nElapsed: {time.time() - t0:.1f}s")

    # Aggregate per season across zones, and overall across everything
    print(f"\n--- Aggregate by season (horizon={horizon}h) ---")
    overall = {"lstm": [], "arima": [], "persistence": []}
    for season_name, _, _ in SEASON_WINDOWS:
        lstm_vals = [r[season_name]["lstm_mae"] for r in all_results.values() if r.get(season_name)]
        arima_vals = [r[season_name]["arima_mae"] for r in all_results.values() if r.get(season_name)]
        persist_vals = [r[season_name]["persistence_mae"] for r in all_results.values() if r.get(season_name)]
        overall["lstm"] += lstm_vals
        overall["arima"] += arima_vals
        overall["persistence"] += persist_vals
        if lstm_vals:
            print(f"{season_name:8s} LSTM={sum(lstm_vals)/len(lstm_vals):.2f}  "
                  f"ARIMA={sum(arima_vals)/len(arima_vals):.2f}  "
                  f"Persistence={sum(persist_vals)/len(persist_vals):.2f}")

    print(f"\n--- Overall (all zones x all seasons, horizon={horizon}h) ---")
    for key in ("lstm", "arima", "persistence"):
        vals = overall[key]
        print(f"{key.capitalize():12s} MAE: {sum(vals)/len(vals):.2f} gCO2/kWh  (n={len(vals)})")

    out_path = os.path.join(config.DATA_DIR, f"evaluation_report_seasonal_{horizon}h.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()

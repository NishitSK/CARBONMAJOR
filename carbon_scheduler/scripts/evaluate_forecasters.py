"""
Walk-forward backtest of LSTM vs ARIMA vs naive persistence on the real
2025 hourly carbon-intensity data, per zone.

Trains a HELD-OUT LSTM per zone on all but the last HOLDOUT_HOURS (does
NOT touch the production models/lstm_{zone}.pt files — this is purely an
evaluation run), then walks forward through the held-out week scoring all
three forecasters on the same 6h-ahead windows.

Run from carbon_scheduler/: python scripts/evaluate_forecasters.py
"""
import glob
import json
import math
import os
import sys
import time

import torch
import torch.nn as nn

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from services import lstm_forecaster, forecaster

HISTORY_DIR = os.path.join(config.DATA_DIR, "history")
HOLDOUT_HOURS = 168   # last 7 days held out per zone
ANCHOR_STEP = 6        # walk forward every 6h
HORIZON = lstm_forecaster.FORECAST_HOURS  # 6h ahead, matches production
WINDOW = lstm_forecaster.WINDOW_HOURS     # 24h input window
EPOCHS = 40


def train_holdout_model(train_series):
    lo, hi = lstm_forecaster._normalize(train_series)
    X, y = lstm_forecaster._windows(train_series, lo, hi)
    model = lstm_forecaster.CarbonLSTM()
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


def errors(actual, predicted):
    n = len(actual)
    abs_errs = [abs(a - p) for a, p in zip(actual, predicted)]
    sq_errs = [(a - p) ** 2 for a, p in zip(actual, predicted)]
    pct_errs = [abs(a - p) / a for a, p in zip(actual, predicted) if a > 1e-6]
    mae = sum(abs_errs) / n
    rmse = math.sqrt(sum(sq_errs) / n)
    mape = (sum(pct_errs) / len(pct_errs) * 100) if pct_errs else float("nan")
    return mae, rmse, mape


def evaluate_zone(zone, full_series):
    train_series = full_series[:-HOLDOUT_HOURS]
    global_start = len(train_series) - WINDOW
    test_series = full_series[global_start:]  # 24h context + HOLDOUT_HOURS test

    model, lo, hi = train_holdout_model(train_series)

    n_anchors = (HOLDOUT_HOURS - HORIZON) // ANCHOR_STEP
    lstm_mae_list, arima_mae_list, persist_mae_list = [], [], []

    for a in range(n_anchors):
        idx = a * ANCHOR_STEP
        window = test_series[idx: idx + WINDOW]
        actual = test_series[idx + WINDOW: idx + WINDOW + HORIZON]
        if len(window) < WINDOW or len(actual) < HORIZON:
            continue

        start_hour = (global_start + idx) % 24

        lstm_pred = lstm_predict(model, lo, hi, window, start_hour)
        arima_pred = forecaster.forecast_next_hours(window, n_hours=HORIZON)
        persist_pred = [window[-1]] * HORIZON

        lstm_mae_list.append(errors(actual, lstm_pred)[0])
        arima_mae_list.append(errors(actual, arima_pred)[0])
        persist_mae_list.append(errors(actual, persist_pred)[0])

    avg = lambda lst: sum(lst) / len(lst) if lst else float("nan")
    return {
        "zone": zone,
        "n_anchors": len(lstm_mae_list),
        "lstm_mae": avg(lstm_mae_list),
        "arima_mae": avg(arima_mae_list),
        "persistence_mae": avg(persist_mae_list),
    }


def main():
    history_files = sorted(glob.glob(os.path.join(HISTORY_DIR, "ci_history_*.json")))
    results = []
    t0 = time.time()

    for path in history_files:
        zone = os.path.basename(path).replace("ci_history_", "").replace(".json", "")
        with open(path) as f:
            real_history = json.load(f)
        if len(real_history) < HOLDOUT_HOURS + WINDOW + HORIZON:
            print(f"{zone}: SKIPPED (insufficient history)")
            continue
        series = lstm_forecaster.series_from_real_history(real_history)
        result = evaluate_zone(zone, series)
        results.append(result)
        print(f"{zone}: n={result['n_anchors']} | LSTM MAE={result['lstm_mae']:.2f} | "
              f"ARIMA MAE={result['arima_mae']:.2f} | Persistence MAE={result['persistence_mae']:.2f}")

    print(f"\nElapsed: {time.time() - t0:.1f}s")

    if results:
        avg = lambda key: sum(r[key] for r in results) / len(results)
        print("\n--- Overall (mean across zones) ---")
        print(f"LSTM MAE:        {avg('lstm_mae'):.2f} gCO2/kWh")
        print(f"ARIMA MAE:       {avg('arima_mae'):.2f} gCO2/kWh")
        print(f"Persistence MAE: {avg('persistence_mae'):.2f} gCO2/kWh")

    with open(os.path.join(config.DATA_DIR, "evaluation_report.json"), "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()

"""
Same walk-forward backtest as evaluate_forecasters.py, but at a 24-hour
forecast horizon instead of 6h, to find the crossover point where LSTM's
seasonal/weekly learning should start separating from the persistence
baseline (per literature: Wiesner et al., Danach et al. report LSTM gains
mainly at 12-24h+ horizons, not <=6h).

Trains a HELD-OUT LSTM per zone (output_size=24) on all but the last
HOLDOUT_HOURS - does NOT touch the production models/lstm_{zone}.pt files
(those stay at the 6h horizon used by the live /forecast endpoint).

Run from carbon_scheduler/: python scripts/evaluate_forecasters_24h.py
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
HOLDOUT_HOURS = 168    # last 7 days held out per zone
ANCHOR_STEP = 6         # walk forward every 6h
HORIZON = 24             # <-- the extension: 24h ahead instead of 6h
WINDOW = lstm_forecaster.WINDOW_HOURS  # 24h input window
EPOCHS = 40


def build_windows(series, lo, hi, window, horizon):
    X, y = [], []
    n = len(series)
    for start in range(0, n - window - horizon):
        w = series[start:start + window]
        target = series[start + window:start + window + horizon]
        seq = []
        for i, val in enumerate(w):
            h = (start + i) % 24
            s, c = lstm_forecaster._hour_features(h)
            seq.append([(val - lo) / (hi - lo), s, c])
        X.append(seq)
        y.append([(v - lo) / (hi - lo) for v in target])
    return torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)


def train_holdout_model_24h(train_series):
    lo, hi = lstm_forecaster._normalize(train_series)
    X, y = build_windows(train_series, lo, hi, WINDOW, HORIZON)
    model = lstm_forecaster.CarbonLSTM(output_size=HORIZON)
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


def lstm_predict_24h(model, lo, hi, window, start_hour_of_day):
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


def evaluate_zone(zone, full_series):
    train_series = full_series[:-HOLDOUT_HOURS]
    global_start = len(train_series) - WINDOW
    test_series = full_series[global_start:]

    model, lo, hi = train_holdout_model_24h(train_series)

    n_anchors = (HOLDOUT_HOURS - HORIZON) // ANCHOR_STEP
    lstm_maes, arima_maes, persist_maes = [], [], []

    for a in range(n_anchors):
        idx = a * ANCHOR_STEP
        window = test_series[idx: idx + WINDOW]
        actual = test_series[idx + WINDOW: idx + WINDOW + HORIZON]
        if len(window) < WINDOW or len(actual) < HORIZON:
            continue

        start_hour = (global_start + idx) % 24

        lstm_pred = lstm_predict_24h(model, lo, hi, window, start_hour)
        arima_pred = forecaster.forecast_next_hours(window, n_hours=HORIZON)
        persist_pred = [window[-1]] * HORIZON

        lstm_maes.append(mae(actual, lstm_pred))
        arima_maes.append(mae(actual, arima_pred))
        persist_maes.append(mae(actual, persist_pred))

    avg = lambda lst: sum(lst) / len(lst) if lst else float("nan")
    return {
        "zone": zone,
        "n_anchors": len(lstm_maes),
        "lstm_mae": avg(lstm_maes),
        "arima_mae": avg(arima_maes),
        "persistence_mae": avg(persist_maes),
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
        print(f"\n--- Overall (mean across zones, {HORIZON}h horizon) ---")
        print(f"LSTM MAE:        {avg('lstm_mae'):.2f} gCO2/kWh")
        print(f"ARIMA MAE:       {avg('arima_mae'):.2f} gCO2/kWh")
        print(f"Persistence MAE: {avg('persistence_mae'):.2f} gCO2/kWh")
        lstm_wins = sum(1 for r in results if r["lstm_mae"] < r["arima_mae"] and r["lstm_mae"] < r["persistence_mae"])
        print(f"LSTM wins outright in {lstm_wins}/{len(results)} zones")

    with open(os.path.join(config.DATA_DIR, "evaluation_report_24h.json"), "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()

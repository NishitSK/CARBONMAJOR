"""
Old vs retrained CarbonLSTM on the held-out window 2026-08-01 .. 2026-09-27
(hourly origins, 24h input window, 6h output), per zone.

Models: old (the weights the pilot ran, trained on 2021-2025), control
(seeded retrain on the same 2021-2025 data), eval (retrained through
2026-07-31), and persistence. The deploy set is not scored: its training
data includes the test window.

Metrics: MAE at 1h and 6h, mean MAE over 1-6h, direction accuracy at 6h, and
a delay-decision test: delay to the forecast minimum within 6h if it promises
>=5% below now; saving is the realised % vs running now, regret = share of
delays that were worse.

Old weights are read from $CADSS_OLD_WEIGHTS_DIR (default
$CADSS_RETRAIN_DIR/weights_old). Writes data/public/lstm_retrain_backtest.json:
error, direction, regret and percentage metrics only, no intensity levels.

Run from carbon_scheduler/, after retrain_lstm_sets.py control eval:
    python scripts/backtest_lstm_retrain.py
"""
import json
import os
import sys

import torch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(REPO)
import config
from services.lstm_forecaster import CarbonLSTM, _hour_features, WINDOW_HOURS, FORECAST_HOURS

WORK = os.environ.get("CADSS_RETRAIN_DIR", os.path.join(config.DATA_DIR, "retrain"))
ZONES = ["AU-NSW", "BR", "CA-QC", "DE", "IE", "IN-WE", "JP", "SE", "SG",
         "US-MIDA-PJM", "US-MIDW-MISO", "US-NW-PACW", "ZA"]
WEIGHTS = {"old": os.environ.get("CADSS_OLD_WEIGHTS_DIR", os.path.join(WORK, "weights_old")),
           "control": os.path.join(WORK, "weights_control"),
           "eval": os.path.join(WORK, "weights_eval")}
TEST_FROM, TEST_TO = "2026-08-01T00", "2026-09-27T23"
PROMISE = 0.05


def series(zone):
    rows = {}
    with open(os.path.join(WORK, "history_2026", f"ci_2026_{zone}.json")) as f:
        for e in json.load(f):
            rows[e["datetime"][:13]] = float(e["carbonIntensity"])
    keys = sorted(rows)
    return keys, [rows[k] for k in keys]


def lstm_preds(path, windows, hours):
    ck = torch.load(path, map_location="cpu", weights_only=False)
    m = CarbonLSTM()
    m.load_state_dict(ck["state_dict"])
    m.eval()
    lo, hi = ck["lo"], ck["hi"]
    X = []
    for w, h0 in zip(windows, hours):
        X.append([[(v - lo) / (hi - lo), *_hour_features((h0 + i) % 24)] for i, v in enumerate(w)])
    with torch.no_grad():
        out = m(torch.tensor(X, dtype=torch.float32)).numpy()
    return [[max(0.0, v * (hi - lo) + lo) for v in row] for row in out]


def score(preds, nows, actuals):
    n = len(preds)
    mae = [sum(abs(p[h] - a[h]) for p, a in zip(preds, actuals)) / n for h in range(FORECAST_HOURS)]
    dir_ok = sum((p[-1] - c > 0) == (a[-1] - c > 0) for p, c, a in zip(preds, nows, actuals)) / n
    delays, saving, regret = 0, 0.0, 0
    for p, c, a in zip(preds, nows, actuals):
        k = min(range(FORECAST_HOURS), key=lambda i: p[i])
        if c > 0 and p[k] <= c * (1 - PROMISE):
            delays += 1
            saving += (c - a[k]) / c
            regret += a[k] > c
    return {"mae_1h": round(mae[0], 3), "mae_6h": round(mae[-1], 3),
            "mae_mean": round(sum(mae) / len(mae), 3), "dir_6h": round(dir_ok, 4),
            "delays": delays, "delay_rate": round(delays / n, 4),
            "saving_when_delayed": round(saving / delays, 4) if delays else None,
            "regret": round(regret / delays, 4) if delays else None,
            "saving_per_decision": round(saving / n, 5)}


def main():
    results = {}
    for zone in ZONES:
        keys, vals = series(zone)
        idx = [i for i, k in enumerate(keys) if TEST_FROM <= k and i + FORECAST_HOURS < len(keys)
               and keys[i + FORECAST_HOURS] <= TEST_TO]
        # origin i: window ends at hour i-1 ("now" = vals[i-1]), targets are hours i .. i+5
        windows = [vals[i - WINDOW_HOURS:i] for i in idx]
        hours = [int(keys[i - WINDOW_HOURS][11:13]) for i in idx]
        nows = [vals[i - 1] for i in idx]
        actuals = [vals[i:i + FORECAST_HOURS] for i in idx]
        results[zone] = {"origins": len(idx)}
        for name, d in WEIGHTS.items():
            results[zone][name] = score(lstm_preds(os.path.join(d, f"lstm_{zone}.pt"), windows, hours), nows, actuals)
        results[zone]["persistence"] = score([[c] * FORECAST_HOURS for c in nows], nows, actuals)

    names = list(WEIGHTS) + ["persistence"]
    summary = {}
    for n in names:
        agg = [r[n] for r in results.values()]
        sv = [a["saving_when_delayed"] for a in agg if a["saving_when_delayed"] is not None]
        rg = [a["regret"] for a in agg if a["regret"] is not None]
        summary[n] = {
            "mae_mean_pct_of_old": round(sum(r[n]["mae_mean"] / r["old"]["mae_mean"] for r in results.values()) / len(results) * 100, 1),
            "dir_6h_pct": round(sum(a["dir_6h"] for a in agg) / len(agg) * 100, 1),
            "delay_rate_pct": round(sum(a["delay_rate"] for a in agg) / len(agg) * 100, 1),
            "saving_when_delayed_pct": round(sum(sv) / len(sv) * 100, 1) if sv else None,
            "regret_pct": round(sum(rg) / len(rg) * 100, 1) if rg else None,
            "saving_per_decision_pct": round(sum(a["saving_per_decision"] for a in agg) / len(agg) * 100, 2),
        }

    out = {"test_window": [TEST_FROM, TEST_TO], "promise_threshold": PROMISE,
           "training": {"old": "2021-2025, pilot weights", "control": "2021-2025, reseeded",
                        "eval": "2021-01-01 to 2026-07-31", "seeds_per_set": 1},
           "mae_unit": "gCO2eq/kWh forecast error (not an intensity level)",
           "summary_mean_over_zones": summary, "zones": results}
    with open(os.path.join(config.DATA_DIR, "public", "lstm_retrain_backtest.json"), "w") as f:
        json.dump(out, f, indent=1)

    print(f"{'zone':14s} " + " ".join(f"{n + ' mMAE%':>17s}" for n in names))
    for zone, r in results.items():
        base = r["old"]["mae_mean"]
        print(f"{zone:14s} " + " ".join(f"{r[n]['mae_mean'] / base * 100:17.0f}" for n in names))
    print("\n(mean MAE over 1-6h as % of the old model's; <100 = better than old)\n")
    for n in names:
        print(f"{n:12s} " + "  ".join(f"{k} {v}" for k, v in summary[n].items()))


if __name__ == "__main__":
    main()

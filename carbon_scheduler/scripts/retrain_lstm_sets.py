"""
Retrains CarbonLSTM per zone with the project's own train_zone() (same
architecture, 60 full-batch epochs, lr 0.01), seeded, and writes weights to
$CADSS_RETRAIN_DIR/weights_<set>/ (default data/retrain/, gitignored) instead
of models/. Needs data/history (2021-2025) and download_history_range.py output.

Sets:
  control  2021-01-01 .. 2025-12-31  (same data as the pilot's weights; measures retrain noise)
  eval     2021-01-01 .. 2026-07-31  (Aug-Sep 2026 held out for the old-vs-new backtest)
  deploy   2021-01-01 .. 2026-09-27  (all data; candidate weights for a second pilot)

Resumable: a zone whose weights file exists is skipped.
Licensed data and derived weights: keep local, never push.

Run from carbon_scheduler/: python scripts/retrain_lstm_sets.py [set ...]
"""
import json
import os
import sys
import time

import torch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(REPO)
import config
from services import lstm_forecaster

WORK = os.environ.get("CADSS_RETRAIN_DIR", os.path.join(config.DATA_DIR, "retrain"))
ZONES = ["AU-NSW", "BR", "CA-QC", "DE", "IE", "IN-WE", "JP", "SE", "SG",
         "US-MIDA-PJM", "US-MIDW-MISO", "US-NW-PACW", "ZA"]
CUTOFF = {"control": "2025-12-31T23", "eval": "2026-07-31T23", "deploy": "2026-09-27T23"}
SEED = 20260928


def load_series(zone, cutoff):
    with open(os.path.join(config.DATA_DIR, "history", f"ci_history_{zone}.json")) as f:
        old = json.load(f)
    with open(os.path.join(WORK, "history_2026", f"ci_2026_{zone}.json")) as f:
        new = json.load(f)
    rows = {}
    for e in old + new:
        key = e["datetime"][:13]  # YYYY-MM-DDTHH, normalises the two timestamp formats
        if key <= cutoff:
            rows[key] = float(e["carbonIntensity"])
    keys = sorted(rows)
    return [round(rows[k], 2) for k in keys], keys[0], keys[-1]


def main(sets):
    for s in sets:
        lstm_forecaster.MODELS_DIR = os.path.join(WORK, f"weights_{s}")
        for zone in ZONES:
            if os.path.exists(os.path.join(lstm_forecaster.MODELS_DIR, f"lstm_{zone}.pt")):
                print(f"{s} {zone}: exists, skipping", flush=True)
                continue
            series, first, last = load_series(zone, CUTOFF[s])
            torch.manual_seed(SEED)
            t = time.time()
            r = lstm_forecaster.train_zone(zone, series, epochs=60)
            rec = {"set": s, "zone": zone, "first": first, "last": last, "hours": len(series),
                   "final_loss": r["final_loss"], "seconds": round(time.time() - t, 1)}
            print(json.dumps(rec), flush=True)
            with open(os.path.join(WORK, "training_log.jsonl"), "a") as f:
                f.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:] or ["control", "eval", "deploy"])

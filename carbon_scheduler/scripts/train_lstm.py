"""
Trains a CarbonLSTM per zone on Electricity Maps history and saves weights
to models/lstm_{zone}.pt. Uses the real series directly (sorted, no
extrapolation) once there's enough of it (>=MIN_REAL_HOURS) to learn actual
seasonal/weekly structure; falls back to the diurnal-profile extrapolation
for sparse history (e.g. only the trailing 24h-48h from a free-tier pull).

Run from carbon_scheduler/, after scripts/download_ci_history.py or
scripts/import_yearly_csv.py:
    python scripts/train_lstm.py
"""
import glob
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from services import lstm_forecaster

HISTORY_DIR = os.path.join(config.DATA_DIR, "history")
MIN_REAL_HOURS = 48  # below this, a single replayed diurnal profile is more useful than the raw series


def main():
    history_files = sorted(glob.glob(os.path.join(HISTORY_DIR, "ci_history_*.json")))
    if not history_files:
        print("No history files found. Run scripts/download_ci_history.py first.")
        return

    for path in history_files:
        zone = os.path.basename(path).replace("ci_history_", "").replace(".json", "")
        with open(path) as f:
            real_history = json.load(f)

        if len(real_history) >= MIN_REAL_HOURS:
            series = lstm_forecaster.series_from_real_history(real_history)
            source = "real"
        else:
            series = lstm_forecaster.build_training_series_from_real(real_history, days=45, seed=hash(zone) % (2**31))
            source = "extrapolated"

        if not series:
            print(f"{zone}: SKIPPED (no usable history)")
            continue

        try:
            result = lstm_forecaster.train_zone(zone, series, epochs=60)
            print(f"{zone}: trained on {result['training_hours']}h ({source}), final_loss={result['final_loss']:.5f} -> {result['path']}")
        except Exception as e:
            print(f"{zone}: FAILED ({e})")


if __name__ == "__main__":
    main()

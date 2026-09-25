"""
Forecast re-verification & calibration review surface.

Refreshes the `recommended` block in data/forecast_calibration.json from
POST-FIX ground-truth records and prints a per-model/horizon verdict table.
Never edits the `applied` block - re-enabling a forecaster is a deliberate
human one-line edit made only after reading this report.

Run:
    python scripts/reverify_and_calibrate.py [--since 2026-09-14T00:00:00+00:00]
"""
import argparse
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import forecast_calibration as fc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=fc.LIVE_HISTORY_FIX_CUTOVER_UTC,
                    help="ISO cutover; only records at/after this origin time count")
    args = ap.parse_args()

    payload = fc.write_calibration(args.since)
    recommended = payload["recommended"]

    print(f"Post-fix cutover: {args.since}")
    print(f"Written: {fc.CALIBRATION_FILE}")
    print("=" * 92)
    print(f"{'Model':<16}{'Hzn':<6}{'N':<7}{'Regimes':<9}{'Verdict':<22}{'Rec.thresh':<12}{'Reason'}")
    print("=" * 92)

    if not recommended:
        print("No post-fix verified records yet.")
    for model in sorted(recommended):
        for horizon in sorted(recommended[model], key=int):
            v = recommended[model][horizon]
            thresh = v["recommended_threshold_pct"]
            thresh_s = "DISABLED" if thresh >= fc.DISABLED_THRESHOLD else f"{thresh:.1f}%"
            print(f"{model:<16}{horizon + 'h':<6}{v['n']:<7}{v['regimes']:<9}"
                  f"{v['verdict']:<22}{thresh_s:<12}{v['reason']}")

    print("=" * 92)

    # Explicit re-enable callouts + the exact manual-flip edit.
    reenable = [(m, h, recommended[m][h])
                for m in recommended for h in recommended[m]
                if recommended[m][h]["verdict"] == "reenable"]
    if reenable:
        print("\nRE-ENABLE candidates (human must apply manually):")
        for m, h, v in reenable:
            print(f"  {m} {h}h @ {v['recommended_threshold_pct']:.1f}%  ->  "
                  f"edit `applied[\"{m}\"][\"{h}\"]` in {os.path.basename(fc.CALIBRATION_FILE)} "
                  f"from its current value to {v['recommended_threshold_pct']:.1f}")
    else:
        print("\nNo model earns re-enabling yet. `applied` unchanged (forecasters stay as-is).")


if __name__ == "__main__":
    main()

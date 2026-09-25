"""
Exports the publishable, derived-only evidence files under data/public/.

Electricity Maps' Terms of Service (updated 2026-03-24) permit academic use of
their Data but prohibit reproducing, publishing or otherwise making Data or
Unmodified Data available to third parties without written consent. Measured
carbon-intensity values are their Data; errors, direction flags, regret flags
and percentage changes are Derived Data ("substantially transformed... such
that the original Data cannot be reverse-engineered or extracted").

So the raw pilot logs and verification records stay local (gitignored), and
this script writes the derived subset that the report's tables are computed
from, which is what a reader needs to reproduce the analysis.

Dropped everywhere: any absolute gCO2/kWh level, measured or predicted.
Kept: model, region, horizon, timestamps, error magnitudes, direction, regret,
percentage changes, decisions, offsets, guard status and dispatch outcomes.

Run from carbon_scheduler/:  python scripts/export_public_evidence.py
"""
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

OUT_DIR = os.path.join(config.DATA_DIR, "public")

# Absolute intensity levels — never exported.
CI_FIELDS = {
    "origin_ci", "actual_ci", "predicted_point_ci", "predicted_optimal_ci",
    "current_ci", "current_ci_at_t0", "raw_predicted_ci", "optimal_predicted_ci",
    "baseline_ci", "winning_ci", "carbon_intensity", "carbon", "best_ci",
    "forecast_12h", "forecast_series", "region_forecasts", "rankings", "ranking",
    "measurements", "rejected",
}

VERIFICATION_KEEP = [
    "verified_at_utc", "origin_timestamp_utc", "target_timestamp_utc", "profile",
    "model_name", "region_name", "horizon_hours", "absolute_error", "squared_error",
    "directional_correct", "expected_savings_pct", "actual_savings_pct",
    "regret_occurred",
]


def scrub(obj):
    """Recursively drop any field carrying an absolute intensity value."""
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items() if k not in CI_FIELDS}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    return obj


def read_jsonl(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip().lstrip("﻿")
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def write_jsonl(name, rows):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"  {name}: {len(rows)} records")
    return path


def main():
    print("Exporting derived-only evidence to data/public/ ...")

    rows = read_jsonl(os.path.join(config.DATA_DIR, "forecast_verification.jsonl"))
    write_jsonl(
        "forecast_verification_derived.jsonl",
        [{k: r[k] for k in VERIFICATION_KEEP if k in r} for r in rows],
    )

    for src, dst in [
        ("pilot_adaptive.jsonl", "pilot_adaptive_decisions.jsonl"),
        ("pilot_lstm.jsonl", "pilot_lstm_decisions.jsonl"),
        ("pilot_arima.jsonl", "pilot_arima_decisions.jsonl"),
        ("pilot_log.jsonl", "pilot_july_decisions.jsonl"),
        ("pilot_log_cloud_vantage.jsonl", "pilot_july_cloud_vantage_decisions.jsonl"),
    ]:
        write_jsonl(dst, [scrub(r) for r in read_jsonl(os.path.join(config.DATA_DIR, src))])

    print("\nData source: Electricity Maps (https://www.electricitymaps.com),")
    print("used under academic access. Derived metrics only; no measured")
    print("carbon-intensity values are redistributed.")


if __name__ == "__main__":
    main()

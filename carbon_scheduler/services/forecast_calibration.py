"""
Forecast Calibration Instrument (measurement, not auto-tuning).

Reads ground-truth verification records (data/forecast_verification.jsonl) and,
per (model, horizon), reports whether acting on a model's own claimed savings
would have paid off - a coarse threshold sweep over POST-FIX records only.

Design stance (per project review, 2026-09-14): this is an EVIDENCE instrument,
not a knob that re-enables a forecaster. It emits a `recommended` block that is
deliberately conservative - default verdict "insufficient_evidence" until there
is enough independent data - and never edits the `applied` block that the live
runners actually read. Re-enabling ARIMA is a human one-line edit to `applied`,
made only after reading a recommendation, never automatic. The fallback path is
always OFF-safe: a missing or malformed calibration file can never silently
lower a guard threshold.
"""
import datetime
import json
import os
import sys
from typing import Dict, List, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

VERIFICATION_LOG = os.path.join(config.DATA_DIR, "forecast_verification.jsonl")
CALIBRATION_FILE = os.path.join(config.DATA_DIR, "forecast_calibration.json")

# Records generated before this cutover used the stale-frozen-history bug
# (fixed 2026-09-14) and are contaminated - excluded from any recommendation.
LIVE_HISTORY_FIX_CUTOVER_UTC = "2026-09-14T00:00:00+00:00"

# Coarse sweep (5% steps) - fine grids on ~100 noisy samples overfit.
SWEEP_THRESHOLDS_PCT = [5.0, 10.0, 15.0, 20.0, 25.0, 30.0]

MIN_POSTFIX_SAMPLES = 100        # per (model, horizon) before any numeric verdict
MIN_INDEPENDENT_REGIMES = 5      # distinct origin-days, so a single grid day can't decide
MIN_MEAN_ACTUAL_SAVING_PCT = 1.0 # a threshold must clear this real delivered saving
MAX_REGRET_PCT = 35.0            # ...and stay under this regret rate

DISABLED_THRESHOLD = 1000.0      # effectively "never act on this forecaster"

# OFF-safe defaults the live runners fall back to and that seed `applied`.
DEFAULT_APPLIED = {
    "ARIMA(2,1,2)": {"1": 1000.0, "3": 1000.0, "6": 1000.0, "12": 1000.0},
    "CarbonLSTM": {"1": 15.0, "3": 15.0, "6": 15.0, "12": 15.0},
}


def load_verification_records(since_iso: str = LIVE_HISTORY_FIX_CUTOVER_UTC) -> List[Dict]:
    """Post-fix verified records only, oldest-first as written."""
    if not os.path.exists(VERIFICATION_LOG):
        return []
    try:
        cutover = datetime.datetime.fromisoformat(since_iso)
    except Exception:
        cutover = None

    out = []
    try:
        with open(VERIFICATION_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if cutover is not None:
                    try:
                        origin = datetime.datetime.fromisoformat(r.get("origin_timestamp_utc", ""))
                        if origin.tzinfo is None:
                            origin = origin.replace(tzinfo=datetime.timezone.utc)
                        if origin < cutover:
                            continue
                    except Exception:
                        continue
                out.append(r)
    except Exception:
        return []
    return out


def _origin_day(record: Dict) -> str:
    return str(record.get("origin_timestamp_utc", ""))[:10]


def _sweep_group(records: List[Dict]) -> List[Dict]:
    """For each candidate threshold, the outcome of acting only when the model
    claimed at least that much saving. Empty subsets are reported, not hidden."""
    rows = []
    for t in SWEEP_THRESHOLDS_PCT:
        subset = [r for r in records if float(r.get("expected_savings_pct", 0.0)) >= t]
        n = len(subset)
        if n == 0:
            rows.append({"threshold_pct": t, "n": 0, "mean_actual_savings_pct": None,
                         "regret_rate_pct": None, "regimes": 0})
            continue
        mean_actual = sum(float(r.get("actual_savings_pct", 0.0)) for r in subset) / n
        regret = sum(1 for r in subset if r.get("regret_occurred")) / n * 100.0
        regimes = len({_origin_day(r) for r in subset})
        rows.append({
            "threshold_pct": t,
            "n": n,
            "mean_actual_savings_pct": round(mean_actual, 2),
            "regret_rate_pct": round(regret, 1),
            "regimes": regimes,
        })
    return rows


def _verdict_for_group(records: List[Dict], sweep: List[Dict]) -> Dict:
    n_total = len(records)
    regimes_total = len({_origin_day(r) for r in records})

    if n_total < MIN_POSTFIX_SAMPLES or regimes_total < MIN_INDEPENDENT_REGIMES:
        return {
            "verdict": "insufficient_evidence",
            "recommended_threshold_pct": DISABLED_THRESHOLD,
            "n": n_total,
            "regimes": regimes_total,
            "reason": f"n={n_total} (need >={MIN_POSTFIX_SAMPLES}), "
                      f"regimes={regimes_total} (need >={MIN_INDEPENDENT_REGIMES})",
        }

    # Lowest threshold that clears both bars with its own adequate subset.
    for row in sweep:
        if (row["n"] >= MIN_POSTFIX_SAMPLES
                and row["regimes"] >= MIN_INDEPENDENT_REGIMES
                and row["mean_actual_savings_pct"] is not None
                and row["mean_actual_savings_pct"] > MIN_MEAN_ACTUAL_SAVING_PCT
                and row["regret_rate_pct"] < MAX_REGRET_PCT):
            return {
                "verdict": "reenable",
                "recommended_threshold_pct": row["threshold_pct"],
                "n": row["n"],
                "regimes": row["regimes"],
                "reason": f"actual={row['mean_actual_savings_pct']}% "
                          f"(> {MIN_MEAN_ACTUAL_SAVING_PCT}%), regret={row['regret_rate_pct']}% "
                          f"(< {MAX_REGRET_PCT}%) at claim>={row['threshold_pct']}%",
            }

    return {
        "verdict": "disable",
        "recommended_threshold_pct": DISABLED_THRESHOLD,
        "n": n_total,
        "regimes": regimes_total,
        "reason": "no threshold delivers real savings within the regret bound",
    }


def compute_recommendations(since_iso: str = LIVE_HISTORY_FIX_CUTOVER_UTC) -> Dict:
    """Full advisory report grouped by (model, horizon). Does not touch disk."""
    records = load_verification_records(since_iso)
    groups: Dict[str, Dict[str, List[Dict]]] = {}
    for r in records:
        model = r.get("model_name", r.get("profile", "Unknown"))
        horizon = str(r.get("horizon_hours", 1))
        groups.setdefault(model, {}).setdefault(horizon, []).append(r)

    report = {}
    for model, horizons in groups.items():
        report[model] = {}
        for horizon, recs in sorted(horizons.items(), key=lambda kv: int(kv[0])):
            sweep = _sweep_group(recs)
            verdict = _verdict_for_group(recs, sweep)
            verdict["sweep"] = sweep
            report[model][horizon] = verdict
    return report


def write_calibration(since_iso: str = LIVE_HISTORY_FIX_CUTOVER_UTC) -> Dict:
    """Refresh the `recommended` block; preserve the human-owned `applied` block
    (seed it with OFF-safe defaults only if the file does not exist yet)."""
    recommended = compute_recommendations(since_iso)

    applied = None
    if os.path.exists(CALIBRATION_FILE):
        try:
            with open(CALIBRATION_FILE, "r", encoding="utf-8") as f:
                applied = json.load(f).get("applied")
        except Exception:
            applied = None
    if not applied:
        applied = json.loads(json.dumps(DEFAULT_APPLIED))  # deep copy

    payload = {
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "cutover_utc": since_iso,
        "note": "`applied` is edited by a human only; runners read it. `recommended` is advisory.",
        "recommended": recommended,
        "applied": applied,
    }
    try:
        with open(CALIBRATION_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception as e:
        print(f"Error writing {CALIBRATION_FILE}: {e}")
    return payload


def applied_threshold(model: str, horizon: int, fallback: float) -> float:
    """Guard threshold the live runners use. Reads only the `applied` block.
    Any missing file / bad JSON / absent key returns `fallback`, which callers
    set to their OFF-safe literal - so this can never silently re-enable a
    forecaster the human has not deliberately switched on."""
    try:
        with open(CALIBRATION_FILE, "r", encoding="utf-8") as f:
            applied = json.load(f).get("applied", {})
        val = applied.get(model, {}).get(str(horizon))
        if isinstance(val, (int, float)):
            return float(val)
    except Exception:
        pass
    return float(fallback)

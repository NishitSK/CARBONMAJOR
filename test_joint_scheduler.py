"""
75 fast test cases for the joint spatial+temporal scheduler
(services/scheduler.py: schedule / schedule_delay_tolerant / schedule_latency_sensitive)
plus its supporting pieces (normalize, filter_regions, forecast_quarter_hour_window).

Run: python test_joint_scheduler.py
"""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "carbon_scheduler"))

from models.region import Region
from models.workload import Workload
from services.scheduler import Scheduler, build_joint_region_pool
from services import forecaster

scheduler = Scheduler()
POOL = build_joint_region_pool()
NORWAY = "EU-North-2 (Norway)"

cases = []  # list of (id, callable) -- callable raises AssertionError on failure


def case(test_id, fn):
    cases.append((test_id, fn))


# ---------------------------------------------------------------------------
# Group A — Workload validation (5)
# ---------------------------------------------------------------------------
case("A1: valid latency-sensitive workload constructs", lambda:
     Workload(cpu_util=0.5, tdp_watts=100, exec_time_hours=1, pue=1.2, latency_type="latency-sensitive"))
case("A2: valid delay-tolerant workload constructs", lambda:
     Workload(cpu_util=0.5, tdp_watts=100, exec_time_hours=1, pue=1.2, latency_type="delay-tolerant"))

def _bad_latency_type(value):
    try:
        Workload(cpu_util=0.5, tdp_watts=100, exec_time_hours=1, pue=1.2, latency_type=value)
        raise AssertionError(f"expected ValueError for latency_type={value!r}")
    except ValueError:
        pass

case("A3: invalid latency_type 'urgent' rejected", lambda: _bad_latency_type("urgent"))
case("A4: invalid latency_type '' rejected", lambda: _bad_latency_type(""))
case("A5: invalid latency_type None rejected", lambda: _bad_latency_type(None))

# ---------------------------------------------------------------------------
# Group B — normalize() (10)
# ---------------------------------------------------------------------------
norm_cases = [
    (100, 100, 200, 0.0), (200, 100, 200, 1.0), (150, 100, 200, 0.5),
    (100, 100, 100, 0.0), (0, 0, 10, 0.0), (10, 0, 10, 1.0),
    (5, 0, 10, 0.5), (-5, -10, 0, 0.5), (250, 200, 300, 0.5), (300, 200, 300, 1.0),
]
for i, (val, lo, hi, expected) in enumerate(norm_cases, start=1):
    def _f(val=val, lo=lo, hi=hi, expected=expected):
        result = scheduler.normalize(val, lo, hi)
        assert abs(result - expected) < 1e-9, f"normalize({val},{lo},{hi})={result}, expected {expected}"
    case(f"B{i}: normalize({val},{lo},{hi})=={expected}", _f)

# ---------------------------------------------------------------------------
# Group C — filter_regions() against the 6-region pool (10)
# Pool latencies: Norway 140, Sweden 130, Ireland 85, Virginia 120, Singapore 175, Mumbai 190
# ---------------------------------------------------------------------------
filter_cases = [
    (50, 0), (84, 0), (85, 1), (119, 1), (120, 2), (129, 2),
    (130, 3), (139, 3), (140, 4), (500, 6),
]
for i, (max_lat, expected_count) in enumerate(filter_cases, start=1):
    def _f(max_lat=max_lat, expected_count=expected_count):
        eligible = scheduler.filter_regions(POOL, max_lat)
        assert len(eligible) == expected_count, f"filter_regions(max={max_lat}) -> {len(eligible)}, expected {expected_count}"
    case(f"C{i}: filter_regions(max_latency={max_lat}) -> {expected_count} eligible", _f)

# ---------------------------------------------------------------------------
# Group D — spatial shift always picks Norway regardless of weights (6)
# ---------------------------------------------------------------------------
weight_combos = [
    {"w1": 0.6, "w2": 0.25, "w3": 0.15},
    {"w1": 1.0, "w2": 0.0, "w3": 0.0},
    {"w1": 0.0, "w2": 1.0, "w3": 0.0},
    {"w1": 0.0, "w2": 0.0, "w3": 1.0},
    {"w1": 0.33, "w2": 0.33, "w3": 0.34},
    {"w1": 0.8, "w2": 0.1, "w3": 0.1},
]
for i, weights in enumerate(weight_combos, start=1):
    def _f(weights=weights):
        wl = Workload(cpu_util=0.5, tdp_watts=100, exec_time_hours=1, pue=1.2, latency_type="delay-tolerant", deadline_hours=4)
        result = scheduler.schedule(wl, POOL, weights=weights)
        assert result["region"]["name"] == NORWAY, f"weights={weights} -> {result['region']['name']}, expected {NORWAY}"
    case(f"D{i}: spatial shift picks Norway with weights={weights}", _f)

# ---------------------------------------------------------------------------
# Group E — deadline capping on the temporal shift (12)
# ---------------------------------------------------------------------------
deadline_hours_list = [0.1, 0.25, 0.5, 0.75, 1, 1.5, 2, 2.5, 3, 3.5, 4, 6]
for i, dh in enumerate(deadline_hours_list, start=1):
    def _f(dh=dh):
        wl = Workload(cpu_util=0.5, tdp_watts=100, exec_time_hours=1, pue=1.2, latency_type="delay-tolerant", deadline_hours=dh)
        result = scheduler.schedule(wl, POOL)
        offset = result["start_offset_minutes"]
        assert offset % 15 == 0, f"deadline={dh}h -> offset {offset} not a multiple of 15"
        assert offset <= 240, f"deadline={dh}h -> offset {offset} exceeds 4h lookahead cap"
        cap = max(15, min(240, int(dh * 60 // 15) * 15))
        assert offset <= cap, f"deadline={dh}h -> offset {offset} exceeds deadline cap {cap}"
    case(f"E{i}: deadline_hours={dh} caps temporal shift correctly", _f)

# ---------------------------------------------------------------------------
# Group F — carbon footprint formula correctness (10)
# Carbon = cpu_util x TDP x exec_time x PUE x carbon_intensity
# ---------------------------------------------------------------------------
footprint_inputs = [
    (0.5, 100, 1.0, 1.2), (0.7, 150, 2.0, 1.3), (1.0, 65, 0.5, 1.1),
    (0.3, 200, 4.0, 1.5), (0.9, 95, 1.5, 1.2), (0.6, 120, 3.0, 1.4),
    (0.4, 250, 0.25, 1.6), (0.85, 180, 2.5, 1.25), (0.2, 300, 6.0, 1.1),
    (0.55, 110, 1.75, 1.35),
]
for i, (cpu_util, tdp, exec_time, pue) in enumerate(footprint_inputs, start=1):
    def _f(cpu_util=cpu_util, tdp=tdp, exec_time=exec_time, pue=pue):
        wl = Workload(cpu_util=cpu_util, tdp_watts=tdp, exec_time_hours=exec_time, pue=pue,
                       latency_type="delay-tolerant", deadline_hours=4)
        result = scheduler.schedule(wl, POOL)
        expected = round(cpu_util * tdp * exec_time * pue * result["predicted_carbon_intensity"], 4)
        assert abs(result["estimated_carbon_footprint_g"] - expected) < 1e-3, \
            f"footprint mismatch: got {result['estimated_carbon_footprint_g']}, expected {expected}"
    case(f"F{i}: footprint formula matches for cpu={cpu_util},tdp={tdp},t={exec_time},pue={pue}", _f)

# ---------------------------------------------------------------------------
# Group G — latency-sensitive selection correctness (10): 9 boundary thresholds + 1 no-match
# ---------------------------------------------------------------------------
def _expected_region_for_max_latency(max_lat):
    eligible = scheduler.filter_regions(POOL, max_lat)
    if not eligible:
        return None
    scored = scheduler.calculate_scores(eligible, {"carbon": 0.6, "latency": 0.25, "resources": 0.15})
    return scored[0][0].name

latency_thresholds = [85, 92, 120, 121, 130, 131, 140, 141, 500]
for i, max_lat in enumerate(latency_thresholds, start=1):
    def _f(max_lat=max_lat):
        wl = Workload(cpu_util=0.5, tdp_watts=100, exec_time_hours=1, pue=1.2,
                       latency_type="latency-sensitive", max_latency_ms=max_lat)
        result = scheduler.schedule(wl, POOL)
        expected = _expected_region_for_max_latency(max_lat)
        assert result["region"]["name"] == expected, \
            f"max_latency={max_lat} -> {result['region']['name']}, expected {expected}"
    case(f"G{i}: latency-sensitive max_latency_ms={max_lat} picks correct region", _f)

def _f_no_match():
    wl = Workload(cpu_util=0.5, tdp_watts=100, exec_time_hours=1, pue=1.2,
                   latency_type="latency-sensitive", max_latency_ms=10)
    result = scheduler.schedule(wl, POOL)
    assert result["region"] is None and "error" in result, f"expected no-match error, got {result}"
case("G10: latency-sensitive max_latency_ms=10 -> no eligible region", _f_no_match)

# ---------------------------------------------------------------------------
# Group H — forecast_quarter_hour_window() shape (8)
# ---------------------------------------------------------------------------
hours_list = [1, 2, 3, 4, 5, 6, 8, 12]
for i, hours in enumerate(hours_list, start=1):
    def _f(hours=hours):
        window = forecaster.forecast_quarter_hour_window(230, hours=hours, seed=42)
        assert len(window) == hours * 4, f"hours={hours} -> len {len(window)}, expected {hours * 4}"
        assert all(v >= 0 for v in window), f"hours={hours} -> negative CI in window {window}"
    case(f"H{i}: forecast_quarter_hour_window(hours={hours}) returns {hours*4} points", _f)

# ---------------------------------------------------------------------------
# Group I — score_breakdown bounds for delay-tolerant decisions (4)
# ---------------------------------------------------------------------------
bound_weight_combos = [
    {"w1": 0.6, "w2": 0.25, "w3": 0.15},
    {"w1": 0.5, "w2": 0.5, "w3": 0.0},
    {"w1": 2.0, "w2": 1.0, "w3": 1.0},   # weights need not sum to 1
    {"w1": 0.0, "w2": 0.0, "w3": 0.0},
]
for i, weights in enumerate(bound_weight_combos, start=1):
    def _f(weights=weights):
        wl = Workload(cpu_util=0.5, tdp_watts=100, exec_time_hours=1, pue=1.2, latency_type="delay-tolerant", deadline_hours=4)
        result = scheduler.schedule(wl, POOL, weights=weights)
        for key in ("C_norm", "L_norm", "P_norm"):
            v = result["score_breakdown"][key]
            assert 0.0 <= v <= 1.0, f"{key}={v} out of [0,1] bounds for weights={weights}"
    case(f"I{i}: score_breakdown components stay in [0,1] for weights={weights}", _f)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def main():
    assert len(cases) == 75, f"Expected exactly 75 test cases, found {len(cases)}"
    failures = []
    for test_id, fn in cases:
        try:
            fn()
        except AssertionError as e:
            failures.append((test_id, str(e)))
        except Exception as e:
            failures.append((test_id, f"{type(e).__name__}: {e}"))

    passed = len(cases) - len(failures)
    print(f"{passed}/{len(cases)} passed")
    if failures:
        print("\nFAILURES:")
        for test_id, msg in failures:
            print(f"  [FAIL] {test_id}\n         {msg}")
        sys.exit(1)
    else:
        print("All 75 test cases passed.")


if __name__ == "__main__":
    main()

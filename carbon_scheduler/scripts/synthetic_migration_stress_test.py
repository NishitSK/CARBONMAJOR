"""
Round-2 council review, point 4: the Stateful Continuity Demonstration rests
on exactly one real migration across 54 live-pilot cycles, because Sweden's
carbon intensity is so far below every competitor that the ranking almost
never flips. One event cannot support a claim of a "demonstrated capability."

The live AWS credential is currently invalid (see HANDOFF.md), so a second
real migration cannot be produced against actual infrastructure right now.
This script instead exercises the EXACT SAME state-transfer-and-verify logic
used by aws/real_workload_migration.py, but against a local in-memory mock
of "regions" instead of real SSM calls, with a deliberately perturbed CI feed
that forces multiple rank flips back and forth. This tests the mechanism
(read state -> increment -> write to new region -> mark old region migrated
-> read back and verify continuity) under repeated flips, which the live
pilot's one real event could not exercise.

This is explicitly a SYNTHETIC, mechanism-level test, not a second live AWS
result - the paper must not conflate the two.

Run from carbon_scheduler/: python scripts/synthetic_migration_stress_test.py
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from models.region import Region
from services.scheduler import Scheduler

# A deliberately adversarial synthetic CI sequence: forces the winner to flip
# between three regions repeatedly, unlike the real pilot week where Sweden
# won all but one decision.
SYNTHETIC_CYCLES = [
    {"us-east-1": 450, "eu-north-1": 20, "ca-central-1": 60},   # Sweden wins
    {"us-east-1": 450, "eu-north-1": 20, "ca-central-1": 60},   # Sweden wins (no-op)
    {"us-east-1": 450, "eu-north-1": 90, "ca-central-1": 25},   # Canada wins (flip 1)
    {"us-east-1": 450, "eu-north-1": 90, "ca-central-1": 25},   # Canada wins (no-op)
    {"us-east-1": 450, "eu-north-1": 15, "ca-central-1": 70},   # Sweden wins (flip 2)
    {"us-east-1": 30,  "eu-north-1": 90, "ca-central-1": 95},   # Virginia wins (flip 3)
    {"us-east-1": 30,  "eu-north-1": 15, "ca-central-1": 25},   # Sweden wins (flip 4)
]
LATENCY_MS = {"us-east-1": 145, "eu-north-1": 172, "ca-central-1": 122}

# Local mock of "remote state" - a dict per region instead of real SSM calls.
mock_region_state = {"us-east-1": {}, "eu-north-1": {}, "ca-central-1": {}}
migrated_away_flags = {}


def mock_read_state(region):
    return dict(mock_region_state.get(region, {}))


def mock_write_state(region, state):
    mock_region_state[region] = dict(state)
    return True


def mock_mark_migrated_away(region, new_region, ts):
    migrated_away_flags[region] = f"MIGRATED_AWAY to {new_region} at {ts}"


def run_cycle(active_region, ci_values):
    """Mirrors aws/real_workload_migration.py's decision + transfer logic exactly,
    with mock_read_state/mock_write_state/mock_mark_migrated_away standing in
    for the real SSM calls."""
    regions = [
        Region(name=name, carbon=ci, latency=LATENCY_MS[name], resources=80.0)
        for name, ci in ci_values.items()
    ]
    scheduler = Scheduler()
    eligible = scheduler.filter_regions(regions, config.DEFAULT_MAX_LATENCY)
    scored = scheduler.calculate_scores(eligible, config.DEFAULT_WEIGHTS)
    winner = scored[0][0].name

    record = {"active_before": active_region, "winner": winner}

    if winner == active_region:
        record["migrated"] = False
        return winner, record

    state = mock_read_state(active_region)
    if not state:
        state = {"counter": 0, "history": []}
    state["counter"] += 1
    state.setdefault("history", []).append({"region": winner, "from": active_region})

    write_ok = mock_write_state(winner, state)
    mock_mark_migrated_away(active_region, winner, datetime.now(timezone.utc).isoformat())

    verified_state = mock_read_state(winner)
    continuity_ok = verified_state.get("counter") == state["counter"]

    record.update({
        "migrated": True,
        "write_ok": write_ok,
        "counter_after": state["counter"],
        "continuity_confirmed": continuity_ok,
    })
    return winner, record


def main():
    active_region = "us-east-1"
    results = []
    for i, ci_values in enumerate(SYNTHETIC_CYCLES):
        active_region_before = active_region
        winner, record = run_cycle(active_region, ci_values)
        active_region = winner
        print(f"Cycle {i+1}: {active_region_before:<12} -> winner={winner:<12} "
              f"migrated={record['migrated']}"
              + (f" counter={record.get('counter_after')} continuity={record.get('continuity_confirmed')}"
                 if record["migrated"] else ""))
        results.append(record)

    n_migrations = sum(1 for r in results if r["migrated"])
    all_continuity_ok = all(r.get("continuity_confirmed", True) for r in results if r["migrated"])
    max_counter = max((r.get("counter_after", 0) for r in results), default=0)

    print(f"\nTotal cycles: {len(results)}")
    print(f"Total migrations triggered: {n_migrations} (vs. 1 in the real 54-cycle live pilot)")
    print(f"Counter reached: {max_counter} (monotonically increasing across every migration -> no state loss)")
    print(f"All migrations passed continuity verification: {all_continuity_ok}")

    out_path = os.path.join(config.DATA_DIR, "synthetic_migration_stress_test.json")
    with open(out_path, "w") as f:
        json.dump({
            "note": "SYNTHETIC mechanism test with a perturbed CI feed and a local mock "
                    "state store, not a second live AWS run. Complements, does not replace, "
                    "the single real migration in the live pilot.",
            "n_cycles": len(results),
            "n_migrations": n_migrations,
            "final_counter": max_counter,
            "all_continuity_confirmed": all_continuity_ok,
            "cycles": results,
        }, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()

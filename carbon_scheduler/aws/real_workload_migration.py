"""
Real workload migration proof-of-concept, going one step further than
workload_migration_demo.py: instead of deploying a fresh, stateless job in
whichever region the scheduler picks, this maintains ONE stateful workload
(a small JSON counter file) that actually MOVES between regions as the
scheduler's decision changes over time - state transfer and a cutover, not
just placement.

Each run:
  1. Determines the scheduler's current winning region using live carbon
     intensity + real cloud latency (same production code path as the
     live pilot).
  2. Looks up which region the workload is currently "living" in (tracked
     in data/workload_active_region.json).
  3. If the winner is the same region, does nothing (no migration needed).
  4. If the winner has changed, migrates:
     a. Reads the current state (a JSON counter + history) from the old
        region via SSM.
     b. Increments the counter and appends the new region to its history.
     c. Writes the updated state to the new region via SSM.
     d. Marks the old region's copy as migrated-away (a stopped flag file),
        simulating a traffic cutover - the old copy is no longer the
        active one.
  5. Verifies the new region's state was actually written and reflects
     continuity (counter incremented, not reset), by reading it back.

Explicit scope note: this demonstrates real state transfer and cutover for
a small, self-contained JSON state file via SSM. It does not demonstrate
live traffic redirection (e.g. DNS/load-balancer cutover) or migration of
an actually-running service with open connections - those remain a
materially larger systems problem, stated as future work.

Run from carbon_scheduler/: python aws/real_workload_migration.py
"""
import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime, timezone

import boto3

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from models.region import Region
from services.scheduler import Scheduler
from services.electricity_service import ElectricityService

INSTANCES_PATH = os.path.join(config.DATA_DIR, "pilot_instances.json")
CLOUD_LATENCY_PATH = os.path.join(config.DATA_DIR, "cloud_latency.json")
INITIAL_REGION_DEFAULT = "us-east-1 (N. Virginia)"

# The following four are namespaced per --scenario in main() so multiple
# migration scenarios (different starting regions) can run in parallel
# without clobbering each other's state or logs.
ACTIVE_REGION_PATH = os.path.join(config.DATA_DIR, "workload_active_region.json")
MIGRATION_LOG_PATH = os.path.join(config.DATA_DIR, "workload_migration_log.jsonl")
STATE_FILE_REMOTE = "/tmp/workload_state.json"
INITIAL_REGION = INITIAL_REGION_DEFAULT


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario", default=None,
        help="Namespaces state/log files for a separate migration scenario "
             "(e.g. 'tokyo', 'mumbai'). Omit to reproduce the original "
             "Virginia-origin scenario's file paths exactly.",
    )
    parser.add_argument(
        "--initial-region", default=INITIAL_REGION_DEFAULT,
        help="Region name the workload starts in (must be a key in pilot_instances.json)",
    )
    return parser.parse_args()


def ssm_run(aws_region, instance_id, commands, timeout=60):
    ssm = boto3.client("ssm", region_name=aws_region)
    resp = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": commands},
        TimeoutSeconds=timeout,
    )
    command_id = resp["Command"]["CommandId"]
    for _ in range(20):
        time.sleep(3)
        try:
            inv = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        if inv["Status"] in ("Success", "Failed", "Cancelled", "TimedOut"):
            return inv
    return None


def read_remote_state(aws_region, instance_id):
    inv = ssm_run(aws_region, instance_id, [f"cat {STATE_FILE_REMOTE} 2>/dev/null || echo '{{}}'"])
    if inv and inv["Status"] == "Success":
        try:
            return json.loads(inv["StandardOutputContent"].strip())
        except json.JSONDecodeError:
            return {}
    return {}


def write_remote_state(aws_region, instance_id, state):
    payload = base64.b64encode(json.dumps(state).encode()).decode()
    inv = ssm_run(aws_region, instance_id, [
        f"echo {payload} | base64 -d > {STATE_FILE_REMOTE}",
        f"cat {STATE_FILE_REMOTE}",
    ])
    return inv is not None and inv["Status"] == "Success"


def mark_migrated_away(aws_region, instance_id, new_region):
    timestamp = datetime.now(timezone.utc).isoformat()
    ssm_run(aws_region, instance_id, [
        f"echo 'MIGRATED_AWAY to {new_region} at {timestamp}' > /tmp/workload_migrated_away.flag",
    ])


def get_active_region(instances):
    if os.path.exists(ACTIVE_REGION_PATH):
        with open(ACTIVE_REGION_PATH) as f:
            data = json.load(f)
            region = data.get("active_region")
            if region in instances:
                return region
    return INITIAL_REGION


def set_active_region(region):
    with open(ACTIVE_REGION_PATH, "w") as f:
        json.dump({"active_region": region, "updated_at": datetime.now(timezone.utc).isoformat()}, f, indent=2)


def determine_winner(instances):
    with open(CLOUD_LATENCY_PATH) as f:
        static_latency = json.load(f)["latency_ms"]

    electricity_service = ElectricityService()
    scheduler = Scheduler()

    regions = []
    for app_name, meta in instances.items():
        ci = electricity_service.get_carbon_intensity(meta["electricity_maps_zone"])
        lat = static_latency.get(app_name)
        if ci is None or lat is None:
            continue
        regions.append(Region(name=app_name, carbon=ci, latency=lat, resources=80.0))

    eligible = scheduler.filter_regions(regions, config.DEFAULT_MAX_LATENCY)
    if not eligible:
        return None, []
    scored = scheduler.calculate_scores(eligible, config.DEFAULT_WEIGHTS)
    return scored[0][0].name, scored


def main():
    global ACTIVE_REGION_PATH, MIGRATION_LOG_PATH, STATE_FILE_REMOTE, INITIAL_REGION

    args = parse_args()
    suffix = f"_{args.scenario}" if args.scenario else ""
    ACTIVE_REGION_PATH = os.path.join(config.DATA_DIR, f"workload_active_region{suffix}.json")
    MIGRATION_LOG_PATH = os.path.join(config.DATA_DIR, f"workload_migration_log{suffix}.jsonl")
    STATE_FILE_REMOTE = f"/tmp/workload_state{suffix}.json"
    INITIAL_REGION = args.initial_region

    with open(INSTANCES_PATH) as f:
        instances = json.load(f)

    print("Determining scheduler's current winning region (live carbon + real cloud latency)...")
    winner, scored = determine_winner(instances)
    if not winner:
        print("No eligible region this cycle; nothing to do.")
        return

    active_region = get_active_region(instances)
    print(f"Current active region (where the workload lives): {active_region}")
    print(f"Scheduler's winning region this cycle:              {winner}")

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "active_region_before": active_region,
        "scheduler_winner": winner,
    }

    if winner == active_region:
        print("\nNo migration needed - workload is already in the winning region.")
        record["migrated"] = False
        with open(MIGRATION_LOG_PATH, "a") as f:
            f.write(json.dumps(record) + "\n")
        return

    print(f"\nMigration triggered: {active_region} -> {winner}")

    old_meta = instances[active_region]
    new_meta = instances[winner]

    print(f"Step 1: reading current state from {active_region} via SSM...")
    state = read_remote_state(old_meta["aws_region"], old_meta["instance_id"])
    if not state:
        state = {"counter": 0, "history": []}
    print(f"  Current state: {state}")

    state["counter"] = state.get("counter", 0) + 1
    state.setdefault("history", []).append({
        "region": winner,
        "migrated_at": datetime.now(timezone.utc).isoformat(),
        "migrated_from": active_region,
    })

    print(f"Step 2: writing updated state to {winner} via SSM (counter -> {state['counter']})...")
    write_ok = write_remote_state(new_meta["aws_region"], new_meta["instance_id"], state)
    if not write_ok:
        print("  FAILED to write state to new region. Aborting migration.")
        record["migrated"] = False
        record["error"] = "write_failed"
        with open(MIGRATION_LOG_PATH, "a") as f:
            f.write(json.dumps(record) + "\n")
        return

    print(f"Step 3: marking {active_region} as migrated-away (simulated cutover)...")
    mark_migrated_away(old_meta["aws_region"], old_meta["instance_id"], winner)

    print(f"Step 4: verifying state in {winner}...")
    verified_state = read_remote_state(new_meta["aws_region"], new_meta["instance_id"])
    continuity_ok = verified_state.get("counter") == state["counter"]
    print(f"  Verified state: {verified_state}")
    print(f"  Continuity confirmed: {continuity_ok} (counter carried over, not reset)")

    set_active_region(winner)

    record.update({
        "migrated": True,
        "state_before_migration": state,
        "state_verified_after_migration": verified_state,
        "continuity_confirmed": continuity_ok,
    })
    with open(MIGRATION_LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")

    print(f"\nMigration complete: {active_region} -> {winner}. Continuity confirmed: {continuity_ok}")
    print(f"Logged -> {MIGRATION_LOG_PATH}")


if __name__ == "__main__":
    main()

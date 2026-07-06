"""
One measurement+decision cycle for the live pilot. Meant to be invoked
periodically (e.g. every 3h) over the pilot week via a scheduled trigger,
not run as a long-lived loop in this process.

Each cycle:
  1. Pulls LIVE carbon intensity per region from Electricity Maps (one
     call per region - 13 calls/cycle; at every-3h for 7 days that's
     13 x 56 = 728 calls/week, well inside typical free-tier limits).
  2. Measures REAL latency to each pilot instance via TCP connect timing
     on port 22 (3 samples, median taken).
  3. Pulls REAL CloudWatch CPUUtilization per instance (proves live cloud
     API integration, not just simulated metrics).
  4. Runs the actual production Scheduler.calculate_scores() /
     explain_decision() on this real snapshot - same code path as the
     deployed app, not a separate "pilot" scoring implementation.
  5. Appends one JSON record to data/pilot_log.jsonl.

Run from carbon_scheduler/: python aws/run_one_cycle.py
"""
import json
import os
import socket
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone

import boto3

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from models.region import Region
from services.scheduler import Scheduler
from services.electricity_service import ElectricityService

INSTANCES_PATH = os.path.join(config.DATA_DIR, "pilot_instances.json")
LOG_PATH = os.path.join(config.DATA_DIR, "pilot_log.jsonl")

# Fixed resource-availability stand-in - a single idle micro instance
# doesn't have a meaningful "capacity" signal on its own; kept constant
# so the carbon+latency dimensions (the real measurements) drive ranking.
FIXED_RESOURCES_PCT = 80.0


def measure_tcp_latency_ms(ip, port=22, samples=3, timeout=3.0):
    times = []
    for _ in range(samples):
        start = time.perf_counter()
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                pass
            times.append((time.perf_counter() - start) * 1000)
        except Exception:
            continue
    return round(statistics.median(times), 2) if times else None


def get_cpu_utilization(instance_id, aws_region):
    cw = boto3.client("cloudwatch", region_name=aws_region)
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=15)
    resp = cw.get_metric_statistics(
        Namespace="AWS/EC2",
        MetricName="CPUUtilization",
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=start, EndTime=end, Period=300, Statistics=["Average"]
    )
    points = resp.get("Datapoints", [])
    if not points:
        return None
    return round(sorted(points, key=lambda p: p["Timestamp"])[-1]["Average"], 2)


def main():
    if not os.path.exists(INSTANCES_PATH):
        print(f"No pilot instances found at {INSTANCES_PATH}. Run provision_pilot.py --confirm first.")
        return

    with open(INSTANCES_PATH) as f:
        instances = json.load(f)

    electricity_service = ElectricityService()
    scheduler = Scheduler()
    timestamp = datetime.now(timezone.utc).isoformat()

    regions = []
    raw_measurements = {}
    for app_name, meta in instances.items():
        zone = meta["electricity_maps_zone"]
        carbon = electricity_service.get_carbon_intensity(zone)
        if carbon is None:
            print(f"  {app_name}: carbon intensity fetch failed, skipping this cycle")
            continue

        latency = measure_tcp_latency_ms(meta["public_ip"])
        if latency is None:
            print(f"  {app_name}: latency measurement failed (instance unreachable?), skipping this cycle")
            continue

        cpu = get_cpu_utilization(meta["instance_id"], meta["aws_region"])

        raw_measurements[app_name] = {
            "carbon_intensity": carbon, "latency_ms": latency, "cpu_utilization_pct": cpu
        }
        regions.append(Region(name=app_name, carbon=carbon, latency=latency, resources=FIXED_RESOURCES_PCT))
        print(f"  {app_name}: CI={carbon}g  latency={latency}ms  cpu={cpu}%")

    if not regions:
        print("No regions measured successfully this cycle; nothing logged.")
        return

    eligible = scheduler.filter_regions(regions, config.DEFAULT_MAX_LATENCY)
    rejected = [r.name for r in regions if r not in eligible]

    record = {
        "timestamp": timestamp,
        "scoring_method": config.SCORING_METHOD_VERSION,
        "measurements": raw_measurements,
        "rejected": rejected,
    }

    if eligible:
        scored = scheduler.calculate_scores(eligible, config.DEFAULT_WEIGHTS)
        best_region, best_score, best_meta = scored[0]
        explanation = scheduler.explain_decision(scored[0])
        record["decision"] = {
            "selected_region": best_region.name,
            "score": best_score,
            "summary": explanation["summary"],
        }
        record["ranking"] = [{"region": r.name, "score": s} for r, s, _ in scored]
    else:
        record["decision"] = None

    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")

    print(f"\nCycle complete -> {record.get('decision', {}).get('selected_region', 'NO ELIGIBLE REGION')}")
    print(f"Logged -> {LOG_PATH}")


if __name__ == "__main__":
    main()

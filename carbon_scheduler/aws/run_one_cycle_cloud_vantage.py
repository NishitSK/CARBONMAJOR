"""
Parallel measurement cycle using the cloud-vantage-point fixes: EC2-to-EC2
latency averaged across SIX geographically spread prober regions (not a
single vantage point), and a real small CPU workload instead of the
hardcoded 80% resources constant.

Deliberately logged to a SEPARATE file from pilot_log.jsonl rather than
replacing it mid-series - switching methodology partway through an already-
running clean series would recreate exactly the kind of undisclosed
discontinuity the pilot's contamination-tagging was built to prevent.

Cycles before the multi-vantage upgrade are tagged "cloud_ec2_to_ec2"
(single Virginia prober); cycles from this version on are tagged
"cloud_multi_vantage_6region" so the two are never silently conflated in
analysis.

Run from carbon_scheduler/: python aws/run_one_cycle_cloud_vantage.py
"""
import base64
import json
import os
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
LOG_PATH = os.path.join(config.DATA_DIR, "pilot_log_cloud_vantage.jsonl")

PROBER_REGIONS = [
    "us-east-1 (N. Virginia)",     # North America
    "eu-west-1 (Ireland)",          # Europe
    "ap-south-1 (Mumbai)",          # South Asia
    "ap-southeast-2 (Sydney)",      # Oceania
    "sa-east-1 (Sao Paulo)",        # South America
    "ap-northeast-1 (Tokyo)",       # East Asia
]

LATENCY_PROBE_SCRIPT = """
import socket, time, json
targets = {targets_json}
results = {{}}
for name, ip in targets.items():
    samples = []
    for _ in range(3):
        start = time.perf_counter()
        try:
            with socket.create_connection((ip, 22), timeout=3):
                pass
            samples.append((time.perf_counter() - start) * 1000)
        except Exception:
            continue
    results[name] = round(sorted(samples)[len(samples)//2], 2) if samples else None
print(json.dumps(results))
"""

WORKLOAD_SCRIPT = """
import hashlib, time
end = time.time() + 20
x = b'carbon-aware-scheduler-workload'
while time.time() < end:
    x = hashlib.sha256(x).digest()
print("done")
"""


def start_latency_probe(prober_name, instances):
    prober_meta = instances[prober_name]
    targets = {name: meta["public_ip"] for name, meta in instances.items() if name != prober_name}
    script = LATENCY_PROBE_SCRIPT.format(targets_json=json.dumps(targets))
    script_b64 = base64.b64encode(script.encode()).decode()

    ssm = boto3.client("ssm", region_name=prober_meta["aws_region"])
    resp = ssm.send_command(
        InstanceIds=[prober_meta["instance_id"]],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [f"echo {script_b64} | base64 -d > /tmp/probe.py", "python3 /tmp/probe.py"]},
        TimeoutSeconds=60,
    )
    return ssm, resp["Command"]["CommandId"], prober_meta["instance_id"]


def measure_multi_vantage_latency(instances):
    # Fire all 6 probes without waiting between them, then poll each
    pending = {}
    for prober in PROBER_REGIONS:
        ssm, command_id, instance_id = start_latency_probe(prober, instances)
        pending[prober] = (ssm, command_id, instance_id)

    matrix = {}
    for prober, (ssm, command_id, instance_id) in pending.items():
        for _ in range(20):
            time.sleep(3)
            try:
                inv = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
            except ssm.exceptions.InvocationDoesNotExist:
                continue
            if inv["Status"] in ("Success", "Failed", "Cancelled", "TimedOut"):
                break
        else:
            continue
        if inv["Status"] == "Success":
            result = json.loads(inv["StandardOutputContent"].strip())
            result[prober] = 0.0
            matrix[prober] = result

    all_regions = list(instances.keys())
    averaged = {}
    for region in all_regions:
        values = [results.get(region) for prober, results in matrix.items()
                  if prober != region and results.get(region) is not None]
        averaged[region] = round(sum(values) / len(values), 2) if values else None

    return averaged, matrix


def trigger_workload_and_measure_cpu(instances):
    for app_name, meta in instances.items():
        script_b64 = base64.b64encode(WORKLOAD_SCRIPT.encode()).decode()
        ssm = boto3.client("ssm", region_name=meta["aws_region"])
        ssm.send_command(
            InstanceIds=[meta["instance_id"]],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": [
                f"echo {script_b64} | base64 -d > /tmp/wl.py",
                "nohup python3 /tmp/wl.py > /tmp/wl.log 2>&1 &",
            ]},
            TimeoutSeconds=30,
        )

    time.sleep(35)  # let the 20s workload run + CloudWatch catch up

    cpu_by_region = {}
    for app_name, meta in instances.items():
        cw = boto3.client("cloudwatch", region_name=meta["aws_region"])
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=5)
        resp = cw.get_metric_statistics(
            Namespace="AWS/EC2", MetricName="CPUUtilization",
            Dimensions=[{"Name": "InstanceId", "Value": meta["instance_id"]}],
            StartTime=start, EndTime=end, Period=60, Statistics=["Maximum"]
        )
        points = resp.get("Datapoints", [])
        cpu_by_region[app_name] = max((p["Maximum"] for p in points), default=None)
    return cpu_by_region


def main():
    with open(INSTANCES_PATH) as f:
        instances = json.load(f)

    electricity_service = ElectricityService()
    scheduler = Scheduler()
    timestamp = datetime.now(timezone.utc).isoformat()

    print("Measuring EC2-to-EC2 latency from 6 globally-spread probers via SSM...")
    avg_latency, matrix = measure_multi_vantage_latency(instances)

    print("Triggering real CPU workload and measuring via CloudWatch...")
    cpu_by_region = trigger_workload_and_measure_cpu(instances)

    regions = []
    raw_measurements = {}
    for app_name, meta in instances.items():
        zone = meta["electricity_maps_zone"]
        carbon = electricity_service.get_carbon_intensity(zone)
        latency = avg_latency.get(app_name)
        peak_cpu = cpu_by_region.get(app_name)

        if carbon is None or latency is None:
            print(f"  {app_name}: missing carbon or latency, skipping")
            continue

        resources = 100.0 - peak_cpu if peak_cpu is not None else 50.0

        raw_measurements[app_name] = {
            "carbon_intensity": carbon,
            "latency_ms_multi_vantage_avg": latency,
            "peak_cpu_pct": peak_cpu,
            "resources_pct": round(resources, 2),
        }
        regions.append(Region(name=app_name, carbon=carbon, latency=latency, resources=resources))
        print(f"  {app_name}: CI={carbon}g  latency={latency}ms  resources={resources:.1f}%")

    if not regions:
        print("No regions measured successfully; nothing logged.")
        return

    eligible = scheduler.filter_regions(regions, config.DEFAULT_MAX_LATENCY)
    record = {
        "timestamp": timestamp,
        "vantage": "cloud_multi_vantage_6region",
        "scoring_method": config.SCORING_METHOD_VERSION,
        "prober_regions": PROBER_REGIONS,
        "measurements": raw_measurements,
    }

    if eligible:
        scored = scheduler.calculate_scores(eligible, config.DEFAULT_WEIGHTS)
        best_region, best_score, _ = scored[0]
        record["decision"] = {"selected_region": best_region.name, "score": best_score}
        record["ranking"] = [{"region": r.name, "score": s} for r, s, _ in scored]
    else:
        record["decision"] = None

    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")

    print(f"\nCycle complete -> {record.get('decision', {}).get('selected_region', 'NO ELIGIBLE REGION')}")
    print(f"Logged -> {LOG_PATH}")


if __name__ == "__main__":
    main()

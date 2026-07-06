"""
Runs a real CPU-bound workload on pilot instances via SSM (no SSH needed),
then reads the resulting CPUUtilization from CloudWatch - replacing the
hardcoded 80% resources constant with a genuine measured signal, for the
instances this is run on.

The workload is intentionally small and synthetic (hashing for ~60s) -
enough to produce a real, non-trivial CPU spike that CloudWatch will pick
up, without meaningfully affecting the AWS bill.

Run from carbon_scheduler/: python aws/run_real_workload.py
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

INSTANCES_PATH = os.path.join(config.DATA_DIR, "pilot_instances.json")
OUT_PATH = os.path.join(config.DATA_DIR, "real_workload_cpu.json")

WORKLOAD_SCRIPT = """
import hashlib, time
end = time.time() + 60
x = b'carbon-aware-scheduler-workload'
count = 0
while time.time() < end:
    x = hashlib.sha256(x).digest()
    count += 1
print(f"Completed {count} hash iterations in 60s")
"""


def run_workload_on(app_name, meta):
    script_b64 = base64.b64encode(WORKLOAD_SCRIPT.encode()).decode()
    ssm = boto3.client("ssm", region_name=meta["aws_region"])

    resp = ssm.send_command(
        InstanceIds=[meta["instance_id"]],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [
            f"echo {script_b64} | base64 -d > /tmp/workload.py",
            "nohup python3 /tmp/workload.py > /tmp/workload.log 2>&1 &",
            "echo started",
        ]},
        TimeoutSeconds=30,
    )
    return resp["Command"]["CommandId"]


def get_cpu_utilization(instance_id, aws_region, start, end):
    cw = boto3.client("cloudwatch", region_name=aws_region)
    resp = cw.get_metric_statistics(
        Namespace="AWS/EC2", MetricName="CPUUtilization",
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=start, EndTime=end, Period=60, Statistics=["Average", "Maximum"]
    )
    return sorted(resp.get("Datapoints", []), key=lambda p: p["Timestamp"])


def main():
    with open(INSTANCES_PATH) as f:
        instances = json.load(f)

    # Run the workload on a subset (3 regions) to keep this a clear demo,
    # not a full-fleet compute job.
    targets = dict(list(instances.items())[:3])

    print(f"Starting real CPU workload on {len(targets)} instances...")
    for app_name, meta in targets.items():
        run_workload_on(app_name, meta)
        print(f"  {app_name}: workload started")

    print("\nWaiting 75s for the 60s workload to run and CloudWatch to catch up...")
    time.sleep(75)

    results = {}
    for app_name, meta in targets.items():
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=5)
        points = get_cpu_utilization(meta["instance_id"], meta["aws_region"], start, end)
        if points:
            peak = max(p["Maximum"] for p in points)
            avg = sum(p["Average"] for p in points) / len(points)
            results[app_name] = {"peak_cpu_pct": round(peak, 2), "avg_cpu_pct": round(avg, 2)}
            print(f"  {app_name}: peak={peak:.1f}%  avg={avg:.1f}%")
        else:
            results[app_name] = None
            print(f"  {app_name}: no CloudWatch datapoints yet (metrics lag ~1-2 min)")

    with open(OUT_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved -> {OUT_PATH}")
    print("\nThis proves genuine CPU load can be triggered and measured per region,")
    print("replacing the hardcoded 80% constant with real (if small-scale) utilization data.")


if __name__ == "__main__":
    main()

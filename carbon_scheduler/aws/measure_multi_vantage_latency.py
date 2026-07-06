"""
Measures EC2-to-EC2 latency from SIX geographically spread prober regions
(not just one), to test whether a single-vantage-point measurement (e.g.
Virginia only) produces a biased/unrepresentative picture, the same way the
original laptop-vantage measurement did.

Probers chosen for global spread: N. America, Europe, South Asia, Oceania,
South America, East Asia. Each prober measures latency to all 11 other
instances via SSM (no SSH). Produces both the full per-prober matrix and a
simple cross-prober average per target region.

Run from carbon_scheduler/: python aws/measure_multi_vantage_latency.py
"""
import base64
import json
import os
import sys
import time

import boto3

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

INSTANCES_PATH = os.path.join(config.DATA_DIR, "pilot_instances.json")
OUT_PATH = os.path.join(config.DATA_DIR, "multi_vantage_latency.json")

PROBER_REGIONS = [
    "us-east-1 (N. Virginia)",     # North America
    "eu-west-1 (Ireland)",          # Europe
    "ap-south-1 (Mumbai)",          # South Asia
    "ap-southeast-2 (Sydney)",      # Oceania
    "sa-east-1 (Sao Paulo)",        # South America
    "ap-northeast-1 (Tokyo)",       # East Asia
]

PROBE_SCRIPT = """
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


def probe_from(prober_name, instances):
    prober_meta = instances[prober_name]
    targets = {name: meta["public_ip"] for name, meta in instances.items() if name != prober_name}
    script = PROBE_SCRIPT.format(targets_json=json.dumps(targets))
    script_b64 = base64.b64encode(script.encode()).decode()

    ssm = boto3.client("ssm", region_name=prober_meta["aws_region"])
    resp = ssm.send_command(
        InstanceIds=[prober_meta["instance_id"]],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [f"echo {script_b64} | base64 -d > /tmp/probe.py", "python3 /tmp/probe.py"]},
        TimeoutSeconds=60,
    )
    command_id = resp["Command"]["CommandId"]

    for _ in range(20):
        time.sleep(3)
        try:
            inv = ssm.get_command_invocation(CommandId=command_id, InstanceId=prober_meta["instance_id"])
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        if inv["Status"] in ("Success", "Failed", "Cancelled", "TimedOut"):
            break
    else:
        return None

    if inv["Status"] != "Success":
        print(f"  {prober_name}: FAILED ({inv['Status']})")
        return None

    result = json.loads(inv["StandardOutputContent"].strip())
    result[prober_name] = 0.0
    return result


def main():
    with open(INSTANCES_PATH) as f:
        instances = json.load(f)

    matrix = {}
    for prober in PROBER_REGIONS:
        print(f"Probing from {prober}...")
        result = probe_from(prober, instances)
        if result:
            matrix[prober] = result
            print(f"  done ({len(result)} targets measured)")

    # Cross-prober average per target region (skip None values and self-zeros
    # when averaging, since 0.0 for the prober itself would skew the average down)
    all_regions = list(instances.keys())
    averaged = {}
    for region in all_regions:
        values = []
        for prober, results in matrix.items():
            if prober == region:
                continue  # don't include a region's distance to itself
            v = results.get(region)
            if v is not None:
                values.append(v)
        averaged[region] = round(sum(values) / len(values), 2) if values else None

    print("\n--- Cross-prober average latency per region (n={} probers) ---".format(len(matrix)))
    for region, avg in sorted(averaged.items(), key=lambda kv: (kv[1] is None, kv[1])):
        print(f"  {region:<30} {avg} ms" if avg is not None else f"  {region:<30} FAILED")

    with open(OUT_PATH, "w") as f:
        json.dump({"probers": PROBER_REGIONS, "matrix": matrix, "cross_prober_average": averaged}, f, indent=2)
    print(f"\nSaved -> {OUT_PATH}")


if __name__ == "__main__":
    main()

"""
Measures latency EC2-to-EC2 instead of laptop-to-EC2, using SSM Run Command
so no SSH key is needed. One instance (the "prober", default us-east-1) is
told via SSM to open a TCP connection to every other pilot instance's public
IP and time it, then the result is retrieved via SSM and parsed.

This directly addresses the single-vantage-point latency bias found in
scripts/latency_bias_correction.py (r^2=0.85 with home-laptop distance) -
this measurement's bias, if any, is relative to the prober instance's AWS
region instead of a residential ISP, which is a materially different (and
more representative of real inter-region cloud traffic) signal.

Run from carbon_scheduler/: python aws/measure_cloud_latency.py
"""
import json
import os
import sys
import time

import boto3

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

INSTANCES_PATH = os.path.join(config.DATA_DIR, "pilot_instances.json")
OUT_PATH = os.path.join(config.DATA_DIR, "cloud_latency.json")
PROBER_REGION_NAME = "us-east-1 (N. Virginia)"

PYTHON_PROBE_SCRIPT = """
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


def main():
    with open(INSTANCES_PATH) as f:
        instances = json.load(f)

    prober_meta = instances[PROBER_REGION_NAME]
    targets = {name: meta["public_ip"] for name, meta in instances.items() if name != PROBER_REGION_NAME}

    script = PYTHON_PROBE_SCRIPT.format(targets_json=json.dumps(targets))
    import base64
    script_b64 = base64.b64encode(script.encode()).decode()

    ssm = boto3.client("ssm", region_name=prober_meta["aws_region"])
    print(f"Sending latency probe command to {PROBER_REGION_NAME} ({prober_meta['instance_id']})...")

    commands = [
        f"echo {script_b64} | base64 -d > /tmp/probe.py",
        "python3 /tmp/probe.py",
    ]
    resp = ssm.send_command(
        InstanceIds=[prober_meta["instance_id"]],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": commands},
        TimeoutSeconds=60,
    )
    command_id = resp["Command"]["CommandId"]

    print("Waiting for command to complete...")
    for _ in range(20):
        time.sleep(3)
        try:
            invocation = ssm.get_command_invocation(CommandId=command_id, InstanceId=prober_meta["instance_id"])
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        if invocation["Status"] in ("Success", "Failed", "Cancelled", "TimedOut"):
            break
    else:
        print("Command did not finish in time.")
        return

    if invocation["Status"] != "Success":
        print(f"Command failed: {invocation['Status']}")
        print("StandardErrorContent:", invocation.get("StandardErrorContent"))
        return

    output = invocation["StandardOutputContent"].strip()
    cloud_latency = json.loads(output)

    # Prober's own latency to itself is 0 by definition
    cloud_latency[PROBER_REGION_NAME] = 0.0

    print(f"\nEC2-to-EC2 latency from {PROBER_REGION_NAME}:")
    for name, ms in sorted(cloud_latency.items(), key=lambda kv: (kv[1] is None, kv[1])):
        print(f"  {name:<30} {ms} ms" if ms is not None else f"  {name:<30} FAILED")

    with open(OUT_PATH, "w") as f:
        json.dump({"prober": PROBER_REGION_NAME, "latency_ms": cloud_latency}, f, indent=2)
    print(f"\nSaved -> {OUT_PATH}")


if __name__ == "__main__":
    main()

"""
Syncs live pilot logs from the Cloud Orchestrator down to your local laptop.

Usage:
  python scripts/sync_pilot_logs.py --profile aws-lstm
"""
import argparse
import os
import sys
import time

import boto3

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

ORCHESTRATOR_REGION = "us-east-1"
ORCHESTRATOR_NAME = "carbon-pilot-cloud-orchestrator"


def sync_logs(profile: str):
    print(f"Syncing logs from Cloud Orchestrator [{profile}]...")
    session = boto3.Session(profile_name=profile, region_name=ORCHESTRATOR_REGION)
    ec2 = session.client("ec2")
    ssm = session.client("ssm")

    # Find orchestrator
    desc = ec2.describe_instances(Filters=[
        {"Name": "tag:Name", "Values": [ORCHESTRATOR_NAME]},
        {"Name": "instance-state-name", "Values": ["running"]}
    ])["Reservations"]

    if not desc or not desc[0]["Instances"]:
        print("  No running Cloud Orchestrator found in us-east-1.")
        return

    inst_id = desc[0]["Instances"][0]["InstanceId"]
    print(f"  Connected to Cloud Orchestrator {inst_id}")

    # Fetch pilot_lstm.jsonl from orchestrator via SSM
    cmd = "cat /opt/carbon_scheduler/data/pilot_lstm.jsonl 2>/dev/null || echo ''"
    try:
        resp = ssm.send_command(
            InstanceIds=[inst_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": [cmd]},
            TimeoutSeconds=30
        )
        cmd_id = resp["Command"]["CommandId"]
        time.sleep(3)
        out = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=inst_id)
        remote_data = out.get("StandardOutputContent", "").strip()

        if remote_data:
            local_file = os.path.join(config.DATA_DIR, "pilot_lstm.jsonl")
            with open(local_file, "w", encoding="utf-8") as f:
                f.write(remote_data + "\n")
            print(f"  Successfully synced {len(remote_data.splitlines())} records -> {local_file}")
        else:
            print("  Cloud Orchestrator logs are currently in sync.")
    except Exception as e:
        print(f"  Sync check notice: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="aws-lstm", help="AWS profile")
    args = parser.parse_args()

    sync_logs(args.profile)


if __name__ == "__main__":
    main()

"""
Terminates pilot instances across one or all 3 AWS accounts.

Usage:
  python aws/teardown_multi_account.py --profile aws-adaptive --confirm
  python aws/teardown_multi_account.py --all --confirm
"""
import argparse
import json
import os
import sys

import boto3

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from aws.pilot_regions import PILOT_REGIONS
from aws.aws_session import get_session

PROFILES = ["aws-adaptive", "aws-lstm", "aws-arima"]


def teardown_account(profile: str, confirm: bool):
    print(f"\n========================================================")
    print(f" Teardown Pilot Fleet for Profile: [{profile}]")
    print(f"========================================================")
    inst_file = os.path.join(config.DATA_DIR, f"pilot_instances_{profile.replace('aws-', '')}.json")
    if not os.path.exists(inst_file):
        print(f"  No instances record found at {inst_file}")
        return

    with open(inst_file, "r") as f:
        instances = json.load(f)

    print(f"  Found {len(instances)} instances recorded.")
    if not confirm:
        print("  [DRY RUN MODE] Pass --confirm to terminate these instances.")
        return

    session = get_session(profile)
    for app_name, info in instances.items():
        aws_region = info["aws_region"]
        inst_id = info["instance_id"]
        try:
            ec2 = session.client("ec2", region_name=aws_region)
            ec2.terminate_instances(InstanceIds=[inst_id])
            print(f"  Terminated {inst_id} in {aws_region} ({app_name})")
        except Exception as e:
            print(f"  Failed to terminate {inst_id} in {aws_region}: {e}")

    try:
        os.remove(inst_file)
        print(f"  Removed instance registry file: {inst_file}")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Teardown pilot instances across 3 AWS accounts.")
    parser.add_argument("--profile", choices=PROFILES, help="Target specific named AWS CLI profile")
    parser.add_argument("--all", action="store_true", help="Teardown all 3 accounts")
    parser.add_argument("--confirm", action="store_true", help="Actually terminate instances")
    args = parser.parse_args()

    if not args.profile and not args.all:
        print("Please specify either --profile <name> or --all")
        return

    profiles_to_run = PROFILES if args.all else [args.profile]
    for p in profiles_to_run:
        teardown_account(p, confirm=args.confirm)


if __name__ == "__main__":
    main()

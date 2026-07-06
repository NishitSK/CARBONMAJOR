"""
Terminates all pilot instances and deletes the security groups created by
provision_pilot.py. Run this at the end of the pilot week so you don't
get billed beyond the planned window.

Run from carbon_scheduler/:
    python aws/teardown_pilot.py --confirm
"""
import argparse
import json
import os
import sys
import time

import boto3

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from aws.pilot_regions import SECURITY_GROUP_NAME, TAG_KEY, TAG_VALUE

INSTANCES_PATH = os.path.join(config.DATA_DIR, "pilot_instances.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true", help="Actually terminate instances. Without this, dry-run only.")
    args = parser.parse_args()

    if not os.path.exists(INSTANCES_PATH):
        print(f"No pilot instances file at {INSTANCES_PATH}. Nothing to tear down.")
        return

    with open(INSTANCES_PATH) as f:
        instances = json.load(f)

    by_region = {}
    for app_name, meta in instances.items():
        by_region.setdefault(meta["aws_region"], []).append(meta["instance_id"])

    print(f"Plan: terminate {sum(len(v) for v in by_region.values())} instances across {len(by_region)} regions.")
    if not args.confirm:
        print("Dry run only. Pass --confirm to actually terminate.")
        return

    for aws_region, instance_ids in by_region.items():
        ec2 = boto3.client("ec2", region_name=aws_region)
        ec2.terminate_instances(InstanceIds=instance_ids)
        print(f"  {aws_region}: terminating {instance_ids}")

    print("\nWaiting for instances to terminate before cleaning up security groups...")
    for aws_region, instance_ids in by_region.items():
        ec2 = boto3.client("ec2", region_name=aws_region)
        waiter = ec2.get_waiter("instance_terminated")
        waiter.wait(InstanceIds=instance_ids)

        try:
            sgs = ec2.describe_security_groups(Filters=[{"Name": "group-name", "Values": [SECURITY_GROUP_NAME]}])["SecurityGroups"]
            for sg in sgs:
                ec2.delete_security_group(GroupId=sg["GroupId"])
                print(f"  {aws_region}: deleted security group {sg['GroupId']}")
        except Exception as e:
            print(f"  {aws_region}: could not delete security group ({e}) - check manually")

    os.remove(INSTANCES_PATH)
    print(f"\nTeardown complete. Removed {INSTANCES_PATH}.")
    print("Double-check the EC2 console across all regions to confirm nothing is left running.")


if __name__ == "__main__":
    main()

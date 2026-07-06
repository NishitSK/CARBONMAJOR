"""
Creates an IAM role + instance profile granting SSM access, and attaches it
to every pilot instance. This lets us run commands ON the instances via
AWS Systems Manager (no SSH key needed) - specifically so we can measure
latency EC2-to-EC2 instead of laptop-to-EC2, and run a real CPU workload
for a genuine (non-hardcoded) resource utilization signal.

Run from carbon_scheduler/: python aws/setup_ssm_role.py --confirm
"""
import argparse
import json
import os
import sys
import time

import boto3
from botocore.exceptions import ClientError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

INSTANCES_PATH = os.path.join(config.DATA_DIR, "pilot_instances.json")
ROLE_NAME = "carbon-pilot-ssm-role"
PROFILE_NAME = "carbon-pilot-ssm-profile"

TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "ec2.amazonaws.com"},
        "Action": "sts:AssumeRole"
    }]
}


def ensure_role_and_profile():
    iam = boto3.client("iam")

    try:
        iam.create_role(RoleName=ROLE_NAME, AssumeRolePolicyDocument=json.dumps(TRUST_POLICY))
        print(f"Created IAM role {ROLE_NAME}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"IAM role {ROLE_NAME} already exists")
        else:
            raise

    iam.attach_role_policy(
        RoleName=ROLE_NAME,
        PolicyArn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
    )
    print("Attached AmazonSSMManagedInstanceCore policy")

    try:
        iam.create_instance_profile(InstanceProfileName=PROFILE_NAME)
        print(f"Created instance profile {PROFILE_NAME}")
        iam.add_role_to_instance_profile(InstanceProfileName=PROFILE_NAME, RoleName=ROLE_NAME)
        print("Added role to instance profile")
        time.sleep(10)  # IAM propagation delay
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"Instance profile {PROFILE_NAME} already exists")
        else:
            raise


def attach_to_instances(confirm):
    with open(INSTANCES_PATH) as f:
        instances = json.load(f)

    for app_name, meta in instances.items():
        ec2 = boto3.client("ec2", region_name=meta["aws_region"])
        if not confirm:
            print(f"  [dry-run] would attach {PROFILE_NAME} to {app_name} ({meta['instance_id']})")
            continue
        try:
            ec2.associate_iam_instance_profile(
                IamInstanceProfile={"Name": PROFILE_NAME},
                InstanceId=meta["instance_id"]
            )
            print(f"  {app_name}: attached SSM instance profile")
        except ClientError as e:
            print(f"  {app_name}: FAILED ({e.response['Error']['Code']}: {e.response['Error']['Message']})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()

    ensure_role_and_profile()
    attach_to_instances(args.confirm)

    if args.confirm:
        print("\nWaiting 60s for SSM agent to register on instances...")
        time.sleep(60)
        print("Done. Check registration with: aws ssm describe-instance-information --region us-east-1")


if __name__ == "__main__":
    main()

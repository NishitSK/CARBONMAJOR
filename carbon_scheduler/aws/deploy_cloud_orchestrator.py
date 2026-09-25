"""
Deploys an autonomous Cloud Orchestrator EC2 instance in us-east-1.
The orchestrator runs 24/7 in the AWS cloud with Linux crontab:
- :10 past the hour -> Adaptive Spatial (Account 1)
- :25 past the hour -> LSTM Temporal 24h (Account 2)
- :40 past the hour -> ARIMA Temporal 6h (Account 3)

You can close/shut down your laptop completely and the pilot continues running in AWS.

Usage:
  python aws/deploy_cloud_orchestrator.py --profile aws-lstm --confirm
"""
import argparse
import os
import sys
import time

import boto3
from botocore.exceptions import ClientError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from aws.pilot_regions import INSTANCE_TYPE, SECURITY_GROUP_NAME

AMI_SSM_PARAM = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
SSM_PROFILE_NAME = "carbon-pilot-ssm-profile"
ORCHESTRATOR_REGION = "us-east-1"
ORCHESTRATOR_NAME = "carbon-pilot-cloud-orchestrator"


def get_default_vpc_and_subnet(ec2_client):
    vpcs = ec2_client.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"]
    if not vpcs:
        raise RuntimeError("No default VPC in us-east-1")
    vpc_id = vpcs[0]["VpcId"]
    subnets = ec2_client.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["Subnets"]
    if not subnets:
        raise RuntimeError("No subnets in default VPC")
    return vpc_id, subnets[0]["SubnetId"]


def get_or_create_sg(ec2_client, vpc_id):
    existing = ec2_client.describe_security_groups(Filters=[
        {"Name": "group-name", "Values": [SECURITY_GROUP_NAME]},
        {"Name": "vpc-id", "Values": [vpc_id]},
    ])["SecurityGroups"]
    if existing:
        return existing[0]["GroupId"]

    sg = ec2_client.create_security_group(
        GroupName=SECURITY_GROUP_NAME,
        Description="Carbon-aware orchestrator security group",
        VpcId=vpc_id,
    )
    return sg["GroupId"]


def deploy_orchestrator(profile: str, confirm: bool):
    print(f"\n========================================================")
    print(f" Deploying Cloud Orchestrator in AWS [{ORCHESTRATOR_REGION}]")
    print(f" Profile: {profile}")
    print(f"========================================================")

    session = boto3.Session(profile_name=profile, region_name=ORCHESTRATOR_REGION)
    ec2 = session.client("ec2")
    ssm = session.client("ssm")

    # Check if orchestrator already exists
    existing = ec2.describe_instances(Filters=[
        {"Name": "tag:Name", "Values": [ORCHESTRATOR_NAME]},
        {"Name": "instance-state-name", "Values": ["pending", "running"]}
    ])["Reservations"]

    if existing and existing[0]["Instances"]:
        inst_id = existing[0]["Instances"][0]["InstanceId"]
        ip = existing[0]["Instances"][0].get("PublicIpAddress", "Allocating...")
        print(f"  Existing Cloud Orchestrator found: {inst_id} ({ip})")
        print("  Orchestrator is already active and running in AWS.")
        return inst_id

    if not confirm:
        print("  [DRY RUN] Pass --confirm to deploy the orchestrator.")
        return None

    vpc_id, subnet_id = get_default_vpc_and_subnet(ec2)
    sg_id = get_or_create_sg(ec2, vpc_id)
    ami_id = ssm.get_parameter(Name=AMI_SSM_PARAM)["Parameter"]["Value"]

    # UserData bootstrap script for autonomous Linux crontab execution
    user_data = """#!/bin/bash
dnf update -y
dnf install -y python3.11 python3.11-pip git cronie
systemctl enable crond
systemctl start crond
pip3.11 install --upgrade pip
pip3.11 install requests statsmodels torch pydantic boto3 python-dotenv scipy numpy

mkdir -p /opt/carbon_scheduler/data
echo "[$(date)] Cloud Orchestrator Bootstrapped" >> /opt/carbon_scheduler/bootstrap.log
"""

    resp = ec2.run_instances(
        ImageId=ami_id,
        InstanceType=INSTANCE_TYPE,
        MinCount=1, MaxCount=1,
        SubnetId=subnet_id,
        SecurityGroupIds=[sg_id],
        IamInstanceProfile={"Name": SSM_PROFILE_NAME},
        UserData=user_data,
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "Project", "Value": "carbon-pilot-3way"},
                {"Key": "Role", "Value": "cloud-orchestrator"},
                {"Key": "Name", "Value": ORCHESTRATOR_NAME}
            ]
        }],
    )

    inst_id = resp["Instances"][0]["InstanceId"]
    print(f"  + Launched Cloud Orchestrator instance: {inst_id}")
    print("  Waiting for public IP...")

    for _ in range(25):
        desc = ec2.describe_instances(InstanceIds=[inst_id])
        inst = desc["Reservations"][0]["Instances"][0]
        ip = inst.get("PublicIpAddress")
        if ip:
            print(f"  Public IP assigned: {ip}")
            break
        time.sleep(3)

    print(f"\n  Cloud Orchestrator successfully deployed in us-east-1!")
    print(f"  Instance ID: {inst_id}")
    print(f"  You can now close your laptop and the pilot will continue running 24/7 in AWS.")
    return inst_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="aws-lstm", help="AWS CLI profile to deploy into")
    parser.add_argument("--confirm", action="store_true", help="Launch orchestrator (billed cost ~$7/mo)")
    args = parser.parse_args()

    deploy_orchestrator(args.profile, confirm=args.confirm)


if __name__ == "__main__":
    main()

"""
Provisions the 12-region pilot fleet across one or all 3 AWS accounts.
Supports named AWS CLI profiles: 'aws-adaptive', 'aws-lstm', 'aws-arima'.

Usage:
  python aws/provision_multi_account.py --profile aws-adaptive --dry-run
  python aws/provision_multi_account.py --profile aws-adaptive --confirm
  python aws/provision_multi_account.py --all --confirm
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
from aws.pilot_regions import PILOT_REGIONS, OPT_IN_REGIONS, INSTANCE_TYPE, SECURITY_GROUP_NAME

AMI_SSM_PARAM = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
SSM_ROLE_NAME = "carbon-pilot-ssm-role"
SSM_PROFILE_NAME = "carbon-pilot-ssm-profile"

PROFILES = ["aws-adaptive", "aws-lstm", "aws-arima"]


def get_boto3_session(profile: str):
    try:
        return boto3.Session(profile_name=profile)
    except Exception as e:
        print(f"Error initializing session for profile '{profile}': {e}")
        return None


def ensure_ssm_role_and_profile(session):
    iam = session.client("iam")
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "ec2.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }
    try:
        iam.create_role(RoleName=SSM_ROLE_NAME, AssumeRolePolicyDocument=json.dumps(trust_policy))
        print(f"  Created IAM role {SSM_ROLE_NAME}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "EntityAlreadyExists":
            print(f"  Warning creating role: {e}")

    try:
        iam.attach_role_policy(
            RoleName=SSM_ROLE_NAME,
            PolicyArn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
        )
    except Exception as e:
        pass

    try:
        iam.create_instance_profile(InstanceProfileName=SSM_PROFILE_NAME)
        iam.add_role_to_instance_profile(InstanceProfileName=SSM_PROFILE_NAME, RoleName=SSM_ROLE_NAME)
        time.sleep(8)
    except ClientError as e:
        if e.response["Error"]["Code"] != "EntityAlreadyExists":
            print(f"  Warning creating instance profile: {e}")


def get_default_vpc_and_subnets(ec2_client):
    vpcs = ec2_client.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"]
    if not vpcs:
        raise RuntimeError("No default VPC in this region")
    vpc_id = vpcs[0]["VpcId"]
    subnets = ec2_client.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["Subnets"]
    if not subnets:
        raise RuntimeError("No subnets in default VPC")
    return vpc_id, [s["SubnetId"] for s in subnets]


def get_or_create_security_group(ec2_client, vpc_id, allowed_cidr):
    existing = ec2_client.describe_security_groups(Filters=[
        {"Name": "group-name", "Values": [SECURITY_GROUP_NAME]},
        {"Name": "vpc-id", "Values": [vpc_id]},
    ])["SecurityGroups"]
    if existing:
        return existing[0]["GroupId"]

    sg = ec2_client.create_security_group(
        GroupName=SECURITY_GROUP_NAME,
        Description="Carbon-aware scheduler 3-way pilot - SSH & ICMP",
        VpcId=vpc_id,
        TagSpecifications=[{"ResourceType": "security-group", "Tags": [{"Key": "Project", "Value": "carbon-pilot-3way"}]}],
    )
    sg_id = sg["GroupId"]
    ec2_client.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[
            {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": allowed_cidr}]},
            {"IpProtocol": "icmp", "FromPort": -1, "ToPort": -1, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}
        ]
    )
    return sg_id


def get_latest_ami(ssm_client):
    return ssm_client.get_parameter(Name=AMI_SSM_PARAM)["Parameter"]["Value"]


def provision_account(profile: str, confirm: bool, skip_opt_in: bool = True, allowed_cidr: str = "0.0.0.0/0"):
    print(f"\n========================================================")
    print(f" Provisioning Fleet for Account Profile: [{profile}]")
    print(f"========================================================")
    session = get_boto3_session(profile)
    if session is None:
        print(f"Skipping {profile} due to missing session/credentials.")
        return

    # Check caller identity
    sts = session.client("sts")
    try:
        ident = sts.get_caller_identity()
        print(f"  Authenticated AWS Account: {ident['Account']} ({ident['Arn']})")
    except Exception as e:
        print(f"  FAILED to authenticate with profile '{profile}': {e}")
        return

    ensure_ssm_role_and_profile(session)

    regions_to_use = {
        name: codes for name, codes in PILOT_REGIONS.items()
        if not (skip_opt_in and codes[0] in OPT_IN_REGIONS)
    }

    print(f"  Target regions count: {len(regions_to_use)}")
    if not confirm:
        print("  [DRY RUN MODE] No instances will be created. Pass --confirm to execute.")
        return

    instances_by_region = {}
    for app_name, (aws_region, zone) in regions_to_use.items():
        try:
            ec2 = session.client("ec2", region_name=aws_region)
            ssm = session.client("ssm", region_name=aws_region)

            # Check if an instance is already running
            existing = ec2.describe_instances(Filters=[
                {"Name": "tag:Project", "Values": ["carbon-pilot-3way"]},
                {"Name": "instance-state-name", "Values": ["running", "pending"]}
            ])
            found_id = None
            for res in existing.get("Reservations", []):
                for inst in res.get("Instances", []):
                    found_id = inst["InstanceId"]
                    break
                if found_id:
                    break

            if found_id:
                instances_by_region[app_name] = (found_id, aws_region)
                print(f"  * {app_name:<28} -> {aws_region}: Reusing existing {found_id}")
                continue

            vpc_id, subnet_ids = get_default_vpc_and_subnets(ec2)
            sg_id = get_or_create_security_group(ec2, vpc_id, allowed_cidr)
            ami_id = get_latest_ami(ssm)

            inst_id = None
            last_err = None
            for sub_id in subnet_ids:
                try:
                    resp = ec2.run_instances(
                        ImageId=ami_id,
                        InstanceType=INSTANCE_TYPE,
                        MinCount=1, MaxCount=1,
                        SubnetId=sub_id,
                        SecurityGroupIds=[sg_id],
                        IamInstanceProfile={"Name": SSM_PROFILE_NAME},
                        TagSpecifications=[{
                            "ResourceType": "instance",
                            "Tags": [
                                {"Key": "Project", "Value": "carbon-pilot-3way"},
                                {"Key": "Policy", "Value": profile.replace("aws-", "")},
                                {"Key": "Name", "Value": f"carbon-pilot-{profile}-{aws_region}"}
                            ]
                        }],
                    )
                    inst_id = resp["Instances"][0]["InstanceId"]
                    instances_by_region[app_name] = (inst_id, aws_region)
                    print(f"  + {app_name:<28} -> {aws_region}: Launched {inst_id}")
                    break
                except ClientError as ce:
                    last_err = ce
                    if "Unsupported" in str(ce):
                        continue
                    raise ce
            if not inst_id and last_err:
                raise last_err
        except Exception as e:
            print(f"  x {app_name:<28} -> {aws_region}: Failed ({e})")

    print("\n  Waiting for instances to acquire Public IPs...")
    results = {}
    for app_name, (inst_id, aws_region) in instances_by_region.items():
        ec2 = session.client("ec2", region_name=aws_region)
        for _ in range(30):
            desc = ec2.describe_instances(InstanceIds=[inst_id])
            inst = desc["Reservations"][0]["Instances"][0]
            ip = inst.get("PublicIpAddress")
            if ip:
                results[app_name] = {
                    "aws_region": aws_region,
                    "instance_id": inst_id,
                    "public_ip": ip,
                    "electricity_maps_zone": PILOT_REGIONS[app_name][1]
                }
                break
            time.sleep(4)

    out_file = os.path.join(config.DATA_DIR, f"pilot_instances_{profile.replace('aws-', '')}.json")
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Saved {len(results)} instances -> {out_file}")


def main():
    parser = argparse.ArgumentParser(description="Provision pilot instances across 3 AWS accounts.")
    parser.add_argument("--profile", choices=PROFILES, help="Target specific named AWS CLI profile")
    parser.add_argument("--all", action="store_true", help="Provision all 3 account fleets (aws-adaptive, aws-lstm, aws-arima)")
    parser.add_argument("--confirm", action="store_true", help="Actually launch instances (billed cost)")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without launching")
    parser.add_argument("--allowed-cidr", default="0.0.0.0/0", help="CIDR allowed for ingress")
    args = parser.parse_args()

    if not args.profile and not args.all:
        print("Please specify either --profile <name> or --all")
        return

    profiles_to_run = PROFILES if args.all else [args.profile]
    for p in profiles_to_run:
        provision_account(p, confirm=args.confirm, allowed_cidr=args.allowed_cidr)


if __name__ == "__main__":
    main()

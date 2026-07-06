"""
Launches one t3.micro per region (13 regions, ~$25-35/week total at
on-demand rates) for the live carbon-aware-scheduler pilot. Creates a
security group allowing inbound SSH (port 22) from 0.0.0.0/0 by default -
restrict --allowed-cidr to your own IP/32 if you want it tighter.

SAFETY: this creates real, billed AWS resources. Defaults to --dry-run.
Pass --confirm to actually launch anything.

Run from carbon_scheduler/:
    python aws/provision_pilot.py --dry-run          # shows the plan, launches nothing
    python aws/provision_pilot.py --confirm           # actually launches 13 instances
    python aws/provision_pilot.py --confirm --allowed-cidr 203.0.113.5/32
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
from aws.pilot_regions import PILOT_REGIONS, OPT_IN_REGIONS, INSTANCE_TYPE, SECURITY_GROUP_NAME, TAG_KEY, TAG_VALUE

OUT_PATH = os.path.join(config.DATA_DIR, "pilot_instances.json")
AMI_SSM_PARAM = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"


def get_default_vpc_and_subnet(ec2_client):
    vpcs = ec2_client.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"]
    if not vpcs:
        raise RuntimeError("No default VPC in this region")
    vpc_id = vpcs[0]["VpcId"]
    subnets = ec2_client.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["Subnets"]
    if not subnets:
        raise RuntimeError("No subnets in default VPC")
    return vpc_id, subnets[0]["SubnetId"]


def get_or_create_security_group(ec2_client, vpc_id, allowed_cidr):
    existing = ec2_client.describe_security_groups(Filters=[
        {"Name": "group-name", "Values": [SECURITY_GROUP_NAME]},
        {"Name": "vpc-id", "Values": [vpc_id]},
    ])["SecurityGroups"]
    if existing:
        return existing[0]["GroupId"]

    sg = ec2_client.create_security_group(
        GroupName=SECURITY_GROUP_NAME,
        Description="Carbon-aware scheduler pilot - SSH access for latency measurement",
        VpcId=vpc_id,
        TagSpecifications=[{"ResourceType": "security-group", "Tags": [{"Key": TAG_KEY, "Value": TAG_VALUE}]}],
    )
    sg_id = sg["GroupId"]
    ec2_client.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[{
            "IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
            "IpRanges": [{"CidrIp": allowed_cidr}]
        }]
    )
    return sg_id


def get_latest_ami(ssm_client):
    return ssm_client.get_parameter(Name=AMI_SSM_PARAM)["Parameter"]["Value"]


def provision_region(app_name, aws_region, allowed_cidr):
    ec2 = boto3.client("ec2", region_name=aws_region)
    ssm = boto3.client("ssm", region_name=aws_region)

    vpc_id, subnet_id = get_default_vpc_and_subnet(ec2)
    sg_id = get_or_create_security_group(ec2, vpc_id, allowed_cidr)
    ami_id = get_latest_ami(ssm)

    resp = ec2.run_instances(
        ImageId=ami_id,
        InstanceType=INSTANCE_TYPE,
        MinCount=1, MaxCount=1,
        SubnetId=subnet_id,
        SecurityGroupIds=[sg_id],
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [{"Key": TAG_KEY, "Value": TAG_VALUE}, {"Key": "Name", "Value": f"carbon-pilot-{aws_region}"}]
        }],
    )
    instance_id = resp["Instances"][0]["InstanceId"]
    return instance_id, aws_region


def wait_for_public_ips(instances_by_region):
    """Poll until each instance has a public IP assigned."""
    results = {}
    for app_name, (instance_id, aws_region) in instances_by_region.items():
        ec2 = boto3.client("ec2", region_name=aws_region)
        for _ in range(30):
            desc = ec2.describe_instances(InstanceIds=[instance_id])
            inst = desc["Reservations"][0]["Instances"][0]
            ip = inst.get("PublicIpAddress")
            if ip:
                results[app_name] = {"aws_region": aws_region, "instance_id": instance_id, "public_ip": ip}
                break
            time.sleep(5)
        else:
            print(f"  WARNING: {app_name} never got a public IP in time")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true", help="Actually launch instances (real cost).")
    parser.add_argument("--dry-run", action="store_true", help="Show the plan without launching anything (default).")
    parser.add_argument("--allowed-cidr", default="0.0.0.0/0", help="CIDR allowed SSH access. Default open to internet.")
    parser.add_argument("--skip-opt-in", action="store_true", help="Skip regions that require manual opt-in (e.g. af-south-1).")
    args = parser.parse_args()

    regions_to_use = {
        name: codes for name, codes in PILOT_REGIONS.items()
        if not (args.skip_opt_in and codes[0] in OPT_IN_REGIONS)
    }

    print(f"Plan: launch 1x {INSTANCE_TYPE} in each of {len(regions_to_use)} regions:")
    for name, (aws_region, zone) in regions_to_use.items():
        flag = " (OPT-IN - must be enabled in your account first)" if aws_region in OPT_IN_REGIONS else ""
        print(f"  {name:<30} -> {aws_region}{flag}")

    if not args.confirm:
        print("\nDry run only. Pass --confirm to actually launch these instances (real AWS cost).")
        return

    print(f"\nLaunching with SSH access from {args.allowed_cidr} ...")
    instances_by_region = {}
    for app_name, (aws_region, zone) in regions_to_use.items():
        try:
            instance_id, region = provision_region(app_name, aws_region, args.allowed_cidr)
            instances_by_region[app_name] = (instance_id, region)
            print(f"  {app_name}: launched {instance_id} in {aws_region}")
        except ClientError as e:
            print(f"  {app_name}: FAILED ({e.response['Error']['Code']}: {e.response['Error']['Message']})")
        except Exception as e:
            print(f"  {app_name}: FAILED ({e})")

    print("\nWaiting for public IPs...")
    results = wait_for_public_ips(instances_by_region)

    output = {
        name: {**results[name], "electricity_maps_zone": PILOT_REGIONS[name][1]}
        for name in results
    }
    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved {len(output)} provisioned instances -> {OUT_PATH}")
    print("Run aws/teardown_pilot.py when the pilot week is over.")


if __name__ == "__main__":
    main()

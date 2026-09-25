import boto3
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aws.pilot_regions import PILOT_REGIONS

session = boto3.Session(profile_name='aws-lstm')
sts = session.client('sts')
ident = sts.get_caller_identity()

acc = ident.get('Account')
arn = ident.get('Arn')
print('=========================================================================================================')
print(f' LIVE AWS VERIFICATION REPORT | Account ID: {acc} | IAM User: {arn}')
print('=========================================================================================================\n')

# 1. Check Orchestrator in us-east-1
ec2_va = session.client('ec2', region_name='us-east-1')
orch = ec2_va.describe_instances(Filters=[{'Name': 'tag:Name', 'Values': ['carbon-pilot-cloud-orchestrator']}])['Reservations']
if orch:
    inst = orch[0]['Instances'][0]
    print('  [CLOUD ORCHESTRATOR INSTANCE]')
    print(f'    Instance ID:   {inst.get("InstanceId")}')
    print(f'    State:         {inst.get("State", {}).get("Name")}')
    print(f'    Public IP:     {inst.get("PublicIpAddress", "N/A")}')
    print(f'    Launch Time:   {inst.get("LaunchTime")}')
    print(f'    Instance Type: {inst.get("InstanceType")}\n')

# 2. Check 12-Region Fleet
print('  [LIVE 12-REGION PILOT FLEET]')
header = f'    {"App Region Name":<28} | {"AWS Region":<15} | {"Instance ID":<20} | {"State":<10} | {"Public IP":<16}'
print(header)
print('    ' + '-' * (len(header) - 4))

for app_name, (aws_reg, zone) in PILOT_REGIONS.items():
    if aws_reg == 'af-south-1':
        continue
    try:
        ec2 = session.client('ec2', region_name=aws_reg)
        res = ec2.describe_instances(Filters=[
            {'Name': 'tag:Project', 'Values': ['carbon-pilot-3way']},
            {'Name': 'instance-state-name', 'Values': ['running', 'pending']}
        ])['Reservations']
        if res and res[0]['Instances']:
            inst = res[0]['Instances'][0]
            print(f'    {app_name:<28} | {aws_reg:<15} | {inst["InstanceId"]:<20} | {inst["State"]["Name"]:<10} | {inst.get("PublicIpAddress", "N/A"):<16}')
        else:
            print(f'    {app_name:<28} | {aws_reg:<15} | {"No instance found":<20} | --         | --')
    except Exception as e:
        print(f'    {app_name:<28} | {aws_reg:<15} | Error: {e}')

print('\n=========================================================================================================')

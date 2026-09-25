#!/bin/bash
# Cron wrapper: run one pilot leg on the cloud orchestrator, then sync data to S3.
# Usage: cloud_run.sh <adaptive|lstm|arima>
LEG="$1"
# Set CARBON_PILOT_BUCKET (or edit here) to your own data bucket.
BUCKET="${CARBON_PILOT_BUCKET:-carbon-pilot-data-ACCOUNT_ID}"
REGION="us-east-1"
ROOT="/opt/carbon/carbon_scheduler"

cd "$ROOT" || exit 1
# ElectricityMaps token from SSM Parameter Store (never stored in the image).
TOKEN=$(aws ssm get-parameter --name /carbonpilot/em_token --with-decryption \
        --query Parameter.Value --output text --region "$REGION" 2>/dev/null)
export ELECTRICITY_MAPS_TOKEN="$TOKEN"

python3.11 "aws/pilot_runner_${LEG}.py" >> "/opt/carbon/run_${LEG}.log" 2>&1

# Push collected data (survives teardown; pull with: aws s3 sync s3://$BUCKET/data ./data)
aws s3 sync "$ROOT/data" "s3://$BUCKET/data" --region "$REGION" \
    --exclude "*" --include "*.jsonl" --include "*.json" >> /opt/carbon/sync.log 2>&1

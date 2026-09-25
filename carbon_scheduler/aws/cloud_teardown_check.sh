#!/bin/bash
# Offline hard-stop: on/after TEARDOWN_DATE, sync final data then terminate the
# ENTIRE fleet (including this orchestrator). Runs daily from cron so the pilot
# self-destructs on schedule even while the laptop is offline. Backed by the
# $80 AWS budget alerts and the laptop teardown task.
TEARDOWN_DATE="2026-10-01"
# Set CARBON_PILOT_BUCKET (or edit here) to your own data bucket.
BUCKET="${CARBON_PILOT_BUCKET:-carbon-pilot-data-ACCOUNT_ID}"
REGION="us-east-1"
ROOT="/opt/carbon/carbon_scheduler"

NOW=$(date -u +%Y-%m-%d)
if [[ "$NOW" < "$TEARDOWN_DATE" ]]; then
  exit 0
fi

cd "$ROOT" || exit 1
# Final data flush before we tear everything down.
aws s3 sync "$ROOT/data" "s3://$BUCKET/data" --region "$REGION" >> /opt/carbon/sync.log 2>&1
python3.11 aws/teardown_multi_account.py --all --confirm >> /opt/carbon/teardown.log 2>&1

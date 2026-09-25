#!/bin/bash
# One-shot bootstrap for the cloud orchestrator (run once on the reused
# us-east-1 worker via SSM). Idempotent: safe to re-run.
set -e
# Set CARBON_PILOT_BUCKET (or edit here) to your own data bucket.
BUCKET="${CARBON_PILOT_BUCKET:-carbon-pilot-data-ACCOUNT_ID}"
REGION="us-east-1"
mkdir -p /opt/carbon
exec >> /opt/carbon/bootstrap.log 2>&1
echo "[$(date)] bootstrap start"

# 1. Swap file - guards torch/statsmodels import against OOM on a 1 GB t3.micro.
if [ ! -f /swapfile ]; then
  dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

# 2. Runtime + cron.
dnf install -y python3.11 python3.11-pip tar gzip cronie >/dev/null 2>&1 || \
  yum install -y python3.11 python3.11-pip tar gzip cronie
systemctl enable --now crond || true

# 3. Code bundle from S3.
aws s3 cp "s3://$BUCKET/bootstrap/pilot_bundle.tgz" /opt/carbon/pilot_bundle.tgz --region "$REGION"
cd /opt/carbon && tar xzf pilot_bundle.tgz   # -> /opt/carbon/carbon_scheduler

# 4. Python deps. Upgrade pip first (stock pip 22.x can't resolve modern torch
# wheels and falls back to a failing source build). torch from the CPU wheel
# index (x86_64) - no CUDA, ~10x smaller. Errors stay visible in bootstrap.log.
python3.11 -m pip install --upgrade pip
python3.11 -m pip install --no-cache-dir requests statsmodels pydantic boto3 python-dotenv scipy numpy
python3.11 -m pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 5. Install wrappers + crontab.
install -m 0755 /opt/carbon/carbon_scheduler/aws/cloud_run.sh /usr/local/bin/cloud_run.sh
install -m 0755 /opt/carbon/carbon_scheduler/aws/cloud_teardown_check.sh /usr/local/bin/cloud_teardown_check.sh
cat > /etc/cron.d/carbonpilot <<'CRON'
10 * * * * root /usr/local/bin/cloud_run.sh adaptive
25 * * * * root /usr/local/bin/cloud_run.sh lstm
40 * * * * root /usr/local/bin/cloud_run.sh arima
5 0 * * * root /usr/local/bin/cloud_teardown_check.sh
CRON
chmod 0644 /etc/cron.d/carbonpilot
systemctl restart crond || true
echo "[$(date)] bootstrap done"

"""
Pilot Runner - Policy 1: Adaptive / Reactive Spatial Scheduling (Account 1)
Evaluates live Electricity Maps carbon intensity + real multi-vantage latency,
enforces sovereign data boundaries across APAC, Americas, and Global suites,
and executes the workload on optimal instances via AWS SSM.
Logs to data/pilot_adaptive.jsonl.
"""
import argparse
import datetime
import json
import os
import sys
import time
from typing import Dict, List

import boto3

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from services.electricity_service import ElectricityService
from services.scheduler import Scheduler
from models.region import Region
from services.failsafe_engine import failsafe_engine
from aws.aws_session import get_session

electricity_service = ElectricityService()
scheduler = Scheduler()
SCORING_METHOD_VERSION = getattr(config, "SCORING_METHOD_VERSION", "threshold_v1")

PROFILE_NAME = "aws-adaptive"
INSTANCES_FILE = os.path.join(config.DATA_DIR, "pilot_instances_adaptive.json")
LOG_FILE = os.path.join(config.DATA_DIR, "pilot_adaptive.jsonl")
ACTIVE_REGION_FILE = os.path.join(config.DATA_DIR, "pilot_adaptive_active.json")

WORKLOAD_COMMAND = "python3 -c \"import time, math; start=time.time(); s=sum(math.sqrt(x) for x in range(25000000)); print('workload_complete_seconds:', round(time.time()-start, 2))\""


def get_instances() -> Dict:
    if os.path.exists(INSTANCES_FILE):
        with open(INSTANCES_FILE, "r") as f:
            return json.load(f)
    return {}


def load_default_latencies() -> Dict[str, float]:
    reg_file = os.path.join(config.DATA_DIR, "regions.json")
    if os.path.exists(reg_file):
        try:
            with open(reg_file, "r") as f:
                data = json.load(f)
                return {item["name"]: float(item.get("latency", 150.0)) for item in data}
        except Exception:
            pass
    return {}


def run_ssm_workload(session, instance_id: str, aws_region: str) -> dict:
    try:
        ssm = session.client("ssm", region_name=aws_region)
        resp = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": [WORKLOAD_COMMAND]},
            TimeoutSeconds=60
        )
        cmd_id = resp["Command"]["CommandId"]
        time.sleep(5)
        out = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=instance_id)
        return {
            "status": out.get("Status"),
            "stdout": out.get("StandardOutputContent", "").strip(),
            "execution_time_ms": out.get("ExecutionTime", 0)
        }
    except Exception as e:
        return {"status": "FAILED", "error": str(e)}


JURISDICTION_VANTAGE = {
    "apac_sovereign": "south_india",
    "americas_sovereign": "us_east",
    "global_unconstrained": "south_india",
}


def load_vantage_latencies(vantage: str) -> Dict[str, float]:
    """Real measured latency from the given client vantage point to each AWS
    region - 'south_india' is this project's own direct measurement (data/regions.json),
    'us_east' is the us-east-1 EC2 prober row from data/multi_vantage_latency.json.
    Different jurisdictions model different real client populations (Americas
    Sovereign = US-based enterprise, APAC Sovereign = APAC-based), so the SLA
    filter must use the vantage matching that jurisdiction's actual clients
    rather than one blanket measurement applied to everyone."""
    if vantage == "us_east":
        mv_file = os.path.join(config.DATA_DIR, "multi_vantage_latency.json")
        if os.path.exists(mv_file):
            try:
                with open(mv_file, "r") as f:
                    row = json.load(f).get("matrix", {}).get("us-east-1 (N. Virginia)", {})
                return {k: (v if v is not None else 150.0) for k, v in row.items()}
            except Exception:
                pass
        return {}
    return load_default_latencies()


JURISDICTIONS = {
    "apac_sovereign": {
        "name": "APAC Sovereign (Banking / DPDP)",
        "allowed": ["ap-south-1 (Mumbai)", "ap-southeast-1 (Singapore)", "ap-northeast-1 (Tokyo)", "ap-southeast-2 (Sydney)"],
        "baseline_region": "ap-south-1 (Mumbai)"
    },
    "americas_sovereign": {
        "name": "Americas Sovereign (HIPAA / Enterprise)",
        "allowed": ["us-east-1 (N. Virginia)", "us-east-2 (Ohio)", "us-west-2 (Oregon)", "ca-central-1 (Canada)", "sa-east-1 (Sao Paulo)"],
        "baseline_region": "us-east-1 (N. Virginia)"
    },
    "global_unconstrained": {
        "name": "Global Flexible (Deep Batch AI)",
        "allowed": None,
        "baseline_region": "us-east-1 (N. Virginia)"
    }
}


def run_cycle():
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    print(f"\n================================================================================")
    print(f"[{now_utc}] Adaptive Spatial Multi-Jurisdiction Enterprise Pilot ({PROFILE_NAME})")
    print(f"================================================================================")
    instances = get_instances()

    # 1. Gather live CI for every region (latency is jurisdiction/vantage-specific,
    # applied per-jurisdiction below rather than filtered with one blanket vantage)
    region_metrics = {}
    rejected_regions = []

    for app_name, meta in electricity_service.REGION_MAP.items():
        zone_code = meta["zone"]
        try:
            ci_val = electricity_service.get_carbon_intensity(zone_code)
            ci_val = failsafe_engine.clamp_ci(ci_val if ci_val is not None else 250.0)
        except Exception:
            ci_val = 250.0
        region_metrics[app_name] = {"ci": ci_val, "zone": zone_code}

    weights = {"carbon": 0.40, "latency": 0.30, "resources": 0.30}

    # 2. Evaluate each Multi-Jurisdiction Workload Stream
    workload_decisions = {}
    session = None
    if instances:
        try:
            session = get_session(PROFILE_NAME)
        except Exception:
            session = None

    for jur_key, jur_info in JURISDICTIONS.items():
        allowed = jur_info["allowed"]
        base_region = jur_info["baseline_region"]
        base_ci = region_metrics.get(base_region, {}).get("ci", 400.0)
        vantage_latencies = load_vantage_latencies(JURISDICTION_VANTAGE.get(jur_key, "south_india"))

        eligible = []
        for app_name, m in region_metrics.items():
            if allowed is not None and app_name not in allowed:
                continue
            lat_val = vantage_latencies.get(app_name, 150.0)
            if lat_val > config.DEFAULT_MAX_LATENCY:
                rejected_regions.append({
                    "jurisdiction": jur_key,
                    "name": app_name,
                    "reason": f"Latency {lat_val}ms > SLA {config.DEFAULT_MAX_LATENCY}ms ({JURISDICTION_VANTAGE.get(jur_key, 'south_india')} vantage)"
                })
                continue
            eligible.append(Region(name=app_name, carbon=float(m["ci"]), latency=float(lat_val), resources=80.0))

        if not eligible:
            workload_decisions[jur_key] = {
                "jurisdiction_name": jur_info["name"],
                "baseline_region": base_region,
                "baseline_ci": base_ci,
                "primary_decision": None,
                "ssm_execution": {"status": "NO_SLA_COMPLIANT_REGION"}
            }
            print(f"  [{jur_info['name']}] -> NO SLA-COMPLIANT REGION (all candidates exceed {config.DEFAULT_MAX_LATENCY}ms from this jurisdiction's client vantage)")
            continue

        scored = scheduler.calculate_scores(eligible, weights)
        best_obj, best_sc, _ = scored[0]

        opt_name = best_obj.name
        opt_ci = best_obj.carbon
        carbon_cut = round(max(0.0, (base_ci - opt_ci) / max(1.0, base_ci) * 100), 2)

        # Workload execution via SSM if instances exist
        ssm_res = {"status": "TELEMETRY_ONLY"}
        if session and instances and opt_name in instances:
            inst_id = instances[opt_name].get("instance_id")
            aws_reg = instances[opt_name].get("aws_region")
            if inst_id and aws_reg:
                print(f"  [{jur_info['name']}] Dispatching to {opt_name} ({inst_id} in {aws_reg})...")
                ssm_res = run_ssm_workload(session, inst_id, aws_reg)

        workload_decisions[jur_key] = {
            "jurisdiction_name": jur_info["name"],
            "baseline_region": base_region,
            "baseline_ci": base_ci,
            "primary_decision": {
                "selected_region": opt_name,
                "selected_offset_hours": 0,
                "predicted_optimal_ci": opt_ci,
                "baseline_ci": base_ci,
                "carbon_reduction_pct": carbon_cut,
                "score": best_sc
            },
            "ssm_execution": ssm_res
        }

        print(f"  [{jur_info['name']}] -> {opt_name} (t=0) | {opt_ci:.1f} gCO2 vs {base_ci:.1f} base | Cut: +{carbon_cut}%")

    # Primary unconstrained decision for backward compatibility
    global_dec = workload_decisions["global_unconstrained"]["primary_decision"] or {
        "selected_region": None, "selected_offset_hours": 0, "predicted_optimal_ci": None,
        "baseline_ci": workload_decisions["global_unconstrained"]["baseline_ci"],
        "carbon_reduction_pct": None, "score": None
    }

    # 3. Log cycle entry
    log_entry = {
        "timestamp_utc": now_utc,
        "policy": "adaptive_spatial",
        "profile": PROFILE_NAME,
        "scoring_method": SCORING_METHOD_VERSION,
        "selected_region": global_dec["selected_region"],
        "selected_offset_hours": 0,
        "predicted_optimal_ci": global_dec["predicted_optimal_ci"],
        "baseline_ci": global_dec["baseline_ci"],
        "estimated_temporal_savings_pct": global_dec["carbon_reduction_pct"],
        "workloads": workload_decisions,
        "rejected": rejected_regions
    }

    failsafe_engine.atomic_append_jsonl(LOG_FILE, log_entry)
    print(f"  Logged Adaptive Multi-Jurisdiction cycle -> {LOG_FILE}\n")


if __name__ == "__main__":
    run_cycle()

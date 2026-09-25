"""
Pilot Runner - Policy 2: Neural LSTM Temporal Shifting (Account 2)
Evaluates 24-hour forward carbon intensity forecasts across regions using CarbonLSTM,
identifies the optimal start window t* for delay-tolerant batch workloads,
and executes the workload via SSM. Logs to data/pilot_lstm.jsonl.
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
from services import lstm_forecaster
from services.real_temporal_forecaster import forecast_lstm_forward
from services.failsafe_engine import failsafe_engine
from services import forecast_tracker
from services import forecast_calibration
from aws.aws_session import get_session

electricity_service = ElectricityService()

PROFILE_NAME = "aws-lstm"
INSTANCES_FILE = os.path.join(config.DATA_DIR, "pilot_instances_lstm.json")
LOG_FILE = os.path.join(config.DATA_DIR, "pilot_lstm.jsonl")
LOOKAHEAD_STAGES = [1, 3, 6, 12]
MAX_LOOKAHEAD = 12

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


def load_trailing_history(zone_code: str, hours: int = 24) -> List[float]:
    """Loads the last N hours of real historical data for seeding.
    This is the frozen 2021-2025 backtest dataset - it does NOT extend into
    the live pilot period, so it's only used to bootstrap load_live_trailing_history()
    below when not enough genuine live cycles have accumulated yet."""
    hist_file = os.path.join(config.DATA_DIR, "history", f"ci_history_{zone_code}.json")
    if os.path.exists(hist_file):
        try:
            with open(hist_file, "r") as f:
                data = json.load(f)
                return [failsafe_engine.clamp_ci(p.get("carbonIntensity", 200.0)) for p in data[-hours:]]
        except Exception:
            pass
    return [200.0] * hours


def load_live_trailing_history(app_name: str, zone_code: str, hours: int) -> List[float]:
    """Builds a genuine live trailing series from this pilot's own accumulated
    cycle log (real current_ci readings recorded each past cycle, roughly
    hourly-spaced since this runner's own cadence is hourly - required for
    forecast_lstm_forward's hour-of-day feature alignment to stay correct),
    instead of the frozen 2021-2025 backtest dataset. Falls back to padding
    with the frozen dataset's tail only while not enough live cycles have
    accumulated yet (early pilot life)."""
    values = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                    except Exception:
                        continue
                    rf = entry.get("region_forecasts", {}).get(app_name)
                    if rf and rf.get("current_ci") is not None:
                        values.append(failsafe_engine.clamp_ci(rf["current_ci"]))
        except Exception:
            pass

    values = values[-hours:]
    if len(values) < hours:
        deficit = hours - len(values)
        values = load_trailing_history(zone_code, hours=deficit) + values
    return values


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
        "allowed": None,  # All 12 regions
        "baseline_region": "us-east-1 (N. Virginia)"
    }
}


def run_cycle():
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_utc = now_dt.isoformat()
    hour_of_day = now_dt.hour
    window_start_hour = (hour_of_day - (lstm_forecaster.WINDOW_HOURS - 1)) % 24

    print(f"\n================================================================================")
    print(f"[{now_utc}] Neural LSTM Multi-Jurisdiction Enterprise Pilot ({PROFILE_NAME})")
    print(f"================================================================================")
    instances = get_instances()

    # 1. Forecast carbon trajectories for each region across 3 stages (latency
    # SLA is applied per-jurisdiction below, using that jurisdiction's own
    # client vantage point - not filtered here)
    region_forecasts = {}

    for app_name, meta in electricity_service.REGION_MAP.items():
        zone_code = meta["zone"]

        trailing = load_live_trailing_history(app_name, zone_code, hours=lstm_forecaster.WINDOW_HOURS - 1)
        try:
            live_ci = electricity_service.get_carbon_intensity(zone_code)
            if live_ci is not None:
                trailing.append(failsafe_engine.clamp_ci(live_ci))
        except Exception:
            pass
        if len(trailing) < lstm_forecaster.WINDOW_HOURS:
            trailing = load_trailing_history(zone_code, hours=lstm_forecaster.WINDOW_HOURS - len(trailing)) + trailing

        try:
            lstm_bundle = lstm_forecaster.load_model(zone_code)
            if lstm_bundle:
                raw_preds, fell_back = forecast_lstm_forward(
                    lstm_bundle=lstm_bundle,
                    real_trailing_24h=trailing,
                    window_start_hour_of_day=window_start_hour,
                    hours=MAX_LOOKAHEAD
                )
            else:
                raw_preds = [trailing[-1]] * MAX_LOOKAHEAD
                fell_back = True
        except Exception:
            raw_preds = [trailing[-1]] * MAX_LOOKAHEAD
            fell_back = True

        preds, had_anomaly = failsafe_engine.sanitize_forecast(raw_preds, trailing[-1], MAX_LOOKAHEAD)

        # Evaluate across the 3 lookahead stages
        stage_evals = {}
        for horizon in LOOKAHEAD_STAGES:
            horizon_preds = preds[:horizon]
            raw_opt_offset = min(range(len(horizon_preds)), key=lambda i: horizon_preds[i])
            raw_opt_ci = horizon_preds[raw_opt_offset]

            # Ground-truth verification (2026-09-14, data/forecast_verification.jsonl)
            # showed LSTM is well-calibrated: real delivered savings IMPROVE as claimed
            # savings rise (avg actual 4.8% at >=2.5% claimed threshold, 15.1% at >=20%),
            # with regret rate dropping from 31.3% to 18.5% over that same range. Raised
            # from the shared 2.5% default to 15% - the data-driven point retaining a
            # reasonable sample (n=576) while meaningfully improving real outcomes.
            # 15.0 is the data-driven default (see comment above); now read from
            # the human-owned `applied` block of data/forecast_calibration.json,
            # with 15.0 as the fallback so behavior is unchanged if the file is
            # missing/malformed. Adjust only via scripts/reverify_and_calibrate.py.
            guarded_offset, guarded_ci, guard_reason = failsafe_engine.apply_no_regret_guard(
                current_ci=trailing[-1],
                predicted_optimal_ci=raw_opt_ci,
                optimal_offset=raw_opt_offset,
                min_saving_threshold_pct=forecast_calibration.applied_threshold(
                    "CarbonLSTM", horizon, fallback=15.0)
            )

            stage_saving_pct = round(max(0.0, (trailing[-1] - guarded_ci) / max(1.0, trailing[-1]) * 100.0), 2)
            stage_evals[f"{horizon}h"] = {
                "horizon_hours": horizon,
                "current_ci": trailing[-1],
                "optimal_offset_hours": guarded_offset,
                "optimal_predicted_ci": guarded_ci,
                "raw_offset": raw_opt_offset,
                "raw_predicted_ci": raw_opt_ci,
                "guard_status": guard_reason,
                "savings_pct": stage_saving_pct
            }

        region_forecasts[app_name] = {
            "zone_code": zone_code,
            "current_ci": trailing[-1],
            "forecast_12h": preds,
            "stages": stage_evals,
            "fell_back_to_persistence": fell_back or had_anomaly
        }

    # 2. Evaluate each enterprise workload scenario across all 3 horizons
    workload_results = {}
    session = None
    try:
        session = get_session(PROFILE_NAME)
    except Exception:
        pass

    for w_key, w_meta in JURISDICTIONS.items():
        allowed = w_meta["allowed"]
        baseline_reg = w_meta["baseline_region"]
        base_ci = region_forecasts.get(baseline_reg, {}).get("current_ci", 300.0)
        vantage_latencies = load_vantage_latencies(JURISDICTION_VANTAGE.get(w_key, "south_india"))

        stage_out = {}
        for horizon in LOOKAHEAD_STAGES:
            key = f"{horizon}h"
            best_reg = None
            best_ci = float("inf")
            best_offset = 0

            for r_name, r_data in region_forecasts.items():
                if allowed is not None and r_name not in allowed:
                    continue
                if vantage_latencies.get(r_name, 150.0) > config.DEFAULT_MAX_LATENCY:
                    continue
                ev = r_data["stages"][key]
                if ev["optimal_predicted_ci"] < best_ci:
                    best_ci = ev["optimal_predicted_ci"]
                    best_reg = r_name
                    best_offset = ev["optimal_offset_hours"]

            saving_vs_base = round(max(0.0, (base_ci - best_ci) / max(1.0, base_ci) * 100.0), 2)
            stage_out[key] = {
                "horizon_hours": horizon,
                "selected_region": best_reg,
                "selected_offset_hours": best_offset,
                "predicted_optimal_ci": best_ci,
                "baseline_region": baseline_reg,
                "baseline_ci": base_ci,
                "carbon_reduction_pct": saving_vs_base
            }

        # Primary operational action uses standard 6h stage
        prim = stage_out["6h"]
        target_reg = prim["selected_region"]
        target_offset = prim["selected_offset_hours"]

        # SSM Execution for immediate eligible runs
        exec_info = {"status": "SCHEDULED", "target_offset_hours": target_offset, "scheduled_region": target_reg}
        if target_offset == 0 and target_reg and target_reg in instances and session:
            inst_id = instances[target_reg].get("instance_id")
            aws_reg = instances[target_reg].get("aws_region")
            if inst_id and aws_reg:
                print(f"  [{w_meta['name']}] Executing live workload on {target_reg} ({inst_id})...")
                exec_info = run_ssm_workload(session, inst_id, aws_reg)

        workload_results[w_key] = {
            "name": w_meta["name"],
            "stages": stage_out,
            "primary_decision": prim,
            "ssm_execution": exec_info
        }

    # 3. Log atomic record
    log_entry = {
        "timestamp_utc": now_utc,
        "policy": "lstm_enterprise_jurisdictions",
        "profile": PROFILE_NAME,
        "workloads": workload_results,
        "region_forecasts": region_forecasts
    }
    failsafe_engine.atomic_append_jsonl(LOG_FILE, log_entry)

    # 4. Ground-truth reconciliation and forward recording (1h, 3h, 6h, 12h)
    try:
        now_dt = datetime.datetime.fromisoformat(now_utc)
        live_ci_map = {name: r["current_ci"] for name, r in region_forecasts.items()}
        forecast_tracker.reconcile_with_live_data(live_ci_map, now_dt)
        forecast_tracker.record_cycle_forecasts(PROFILE_NAME, "CarbonLSTM", now_dt, region_forecasts, horizons=[1, 3, 6, 12])
    except Exception as e:
        print(f"  Warning in forecast tracking: {e}")

    print("\n  ================ Multi-Jurisdiction Decision Matrix (Neural LSTM) ================")
    for w_key, res in workload_results.items():
        p = res["primary_decision"]
        if p.get('selected_region') is None:
            print(f"  * {res['name']:<35} -> NO SLA-COMPLIANT REGION (all candidates exceed {config.DEFAULT_MAX_LATENCY}ms latency)")
        else:
            print(f"  * {res['name']:<35} -> {p['selected_region']:<22} at T+{p['selected_offset_hours']}h | {p['predicted_optimal_ci']:.1f} vs {p['baseline_ci']:.1f} gCO2/kWh (+{p['carbon_reduction_pct']}%)")
    print(f"  Logged -> {LOG_FILE}\n")


if __name__ == "__main__":
    run_cycle()

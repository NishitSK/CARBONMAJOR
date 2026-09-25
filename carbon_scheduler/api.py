from fastapi import FastAPI, HTTPException, APIRouter, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import sys
import os
import json

# Add parent directory to path to import current logic
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.region import Region
from models.workload import Workload
from services.simulator import Simulator
from services.scheduler import Scheduler, build_joint_region_pool
from services import forecaster
from services import lstm_forecaster
from services.electricity_service import ElectricityService
from services.failsafe_engine import failsafe_engine
from services import forecast_calibration
import config
from research_api import router as research_router
from history_api import router as history_router

app = FastAPI(title="Carbon-Aware Scheduler API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    # Local dev UI origins only (vite dev + vite preview); the /api proxy
    # path doesn't need CORS at all.
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router for regions
router = APIRouter(prefix="/regions")

# Stateful services (could be moved to dependency injection)
_simulator_fixed = Simulator(demo_mode=True)
_simulator_live = Simulator(demo_mode=False)
scheduler = Scheduler()

def get_simulator(demo_mode: bool = False):
    return _simulator_fixed if demo_mode else _simulator_live

class ScoringRequest(BaseModel):
    regions: List[Dict]
    weights: Dict[str, float]
    max_latency: float
    demo_mode: bool = False

class ForecastRequest(BaseModel):
    region_name: str
    base_ci: float
    max_delay_hours: int = 6
    deadline_hours: int = 8

class CarbonEstimateRequest(BaseModel):
    operational_co2_kg: float
    exec_hours: float
    cpu_fraction: float = 1.0

class ElasticScalingRequest(BaseModel):
    base_vcores: int
    ci_current: float

class ScheduleJointRequest(BaseModel):
    cpu_util: float
    tdp_watts: float
    exec_time_hours: float
    pue: float
    latency_type: str  # "latency-sensitive" | "delay-tolerant"
    max_latency_ms: float = 200.0
    deadline_hours: float = 4.0

@router.get("/")
async def get_regions(mode: str = "fixed", demo_mode: bool = False):
    """Fetch initial region data."""
    sim = get_simulator(demo_mode)
    regions = sim.get_simulation_data(mode)
    return [r.to_dict() for r in regions]

@router.get("/zones")
async def get_zones():
    """
    Pure metadata (name/lat/lng) for every real electricity zone this
    system can pull carbon data for -- no carbon/latency fetch. Powers the
    Client Console's "add a server" zone picker: a client picks which real
    zone their own server lives in, carbon data for it stays real.
    """
    return [
        {"name": name, "lat": meta["lat"], "lng": meta["lng"]}
        for name, meta in ElectricityService.REGION_MAP.items()
    ]

@router.get("/daily-series")
async def get_daily_series(mode: str = "fixed"):
    """
    Deterministic 24h carbon-intensity curve per region, anchored on each
    region's base CI via the same diurnal generator used for forecasting.
    Powers the one-day simulation timeline in the UI.
    """
    sim = get_simulator(True)
    regions = sim.get_simulation_data(mode)
    series = {}
    for r in regions:
        series[r.name] = forecaster.generate_synthetic_history(r.carbon, hours=24, seed=hash(r.name) % (2**31))
    return {"regions": [r.to_dict() for r in regions], "series": series}

@router.post("/drift")
async def drift_regions(regions: List[Dict], demo_mode: bool = Body(False)):
    """Apply small random fluctuations to current region data."""
    try:
        sim = get_simulator(demo_mode)
        region_objs = [Region(**r) for r in regions]
        drifted_objs = sim.apply_drift(region_objs)
        return [r.to_dict() for r in drifted_objs]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/score")
async def score_regions(request: ScoringRequest):
    """Filter and score regions with explainability and rejected reasons."""
    try:
        # 1. Safe Defaults
        weights = request.weights or {"carbon": 0.4, "latency": 0.3, "resources": 0.3}
        max_lat = request.max_latency or 200.0
        
        # Convert dicts back to Region objects
        region_objs = [Region(**r) for r in request.regions]
        
        # 2. Filter by SLA (BEFORE Normalization)
        eligible = scheduler.filter_regions(region_objs, max_lat)
        rejected_objs = [r for r in region_objs if r not in eligible]
        
        rejected = []
        for r in rejected_objs:
            reason = f"Latency {r.latency}ms exceeds SLA {max_lat}ms" if r.latency > max_lat else "Unknown"
            rejected.append({"name": r.name, "reason": reason})
        
        if not eligible:
            return {
                "success": False,
                "message": "No regions meet SLA constraints.",
                "eligible": [],
                "rejected": rejected,
                "final_decision": None,
                "explanation": None
            }
            
        # 3. Score (Only Eligible)
        scored_results = scheduler.calculate_scores(eligible, weights)
        
        # 4. Final Decision & Explanation
        best_result = scored_results[0]
        explanation = scheduler.explain_decision(best_result)
        
        # 5. Format results
        results = []
        for rank, (region, score, metadata) in enumerate(scored_results):
            results.append({
                "rank": rank + 1,
                "region": region.to_dict(),
                "score": score,
                "metadata": metadata
            })
            
        return {
            "success": True,
            "eligible": results,
            "rejected": rejected,
            "final_decision": results[0],
            "explanation": explanation,
            "debug": {
                "weights_used": weights,
                "demo_mode": request.demo_mode
            }
        }
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/forecast")
async def forecast_region(request: ForecastRequest):
    """
    Carbon intensity forecast + optimal shift window (guide sec 10).
    Uses the trained per-zone LSTM (models/lstm_{zone}.pt) when available,
    falling back to ARIMA(2,1,2) otherwise.
    """
    try:
        seed = hash(request.region_name) % (2**31)
        series = forecaster.generate_synthetic_history(request.base_ci, hours=48, seed=seed)
        horizon = max(1, min(request.max_delay_hours, request.deadline_hours))

        zone_meta = ElectricityService.REGION_MAP.get(request.region_name)
        model_used = "arima"
        forecast_vals = None

        if zone_meta:
            zone = zone_meta["zone"]
            lstm_forecast = lstm_forecaster.predict(zone, series[-lstm_forecaster.WINDOW_HOURS:])
            if lstm_forecast is not None:
                forecast_vals = lstm_forecast[:horizon]
                model_used = "lstm"

        if forecast_vals is None:
            forecast_vals = forecaster.forecast_next_hours(series, n_hours=horizon)

        best_offset = min(range(len(forecast_vals)), key=lambda i: forecast_vals[i])
        return {
            "region_name": request.region_name,
            "model_used": model_used,
            "history": series,
            "forecast": forecast_vals,
            "best_offset_hours": best_offset,
            "best_forecast_ci": forecast_vals[best_offset]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/carbon/estimate")
async def carbon_estimate(request: CarbonEstimateRequest):
    """Operational + embodied (Scope 3) lifecycle carbon estimate (guide sec 4.2)."""
    return scheduler.estimate_total_carbon_kg(request.operational_co2_kg, request.exec_hours, request.cpu_fraction)

@app.post("/scaling/elastic")
async def elastic_scaling(request: ElasticScalingRequest):
    """CarbonScaler-style elastic vcore scaling recommendation (guide sec 4.3)."""
    return scheduler.elastic_vcore_count(request.base_vcores, request.ci_current)

@app.post("/schedule/joint")
async def schedule_joint(request: ScheduleJointRequest):
    """
    Joint spatial + temporal shifting for delay-tolerant workloads
    (lowest-carbon region, then lowest-carbon 15-min window within it),
    or immediate SLA-constrained placement for latency-sensitive ones.
    """
    try:
        workload = Workload(
            cpu_util=request.cpu_util,
            tdp_watts=request.tdp_watts,
            exec_time_hours=request.exec_time_hours,
            pue=request.pue,
            latency_type=request.latency_type,
            max_latency_ms=request.max_latency_ms,
            deadline_hours=request.deadline_hours
        )
        region_pool = build_joint_region_pool()
        return scheduler.schedule(workload, region_pool)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/pilot/telemetry")
async def get_pilot_telemetry():
    """Returns the latest pilot telemetry and instance fleet metadata across accounts."""
    import math
    data_dir = config.DATA_DIR

    def _finite(obj):
        # Pilot logs can contain NaN/Infinity (accepted by Python's json, not
        # valid in a JSON response); map them to null so the response serializes.
        if isinstance(obj, float) and not math.isfinite(obj):
            return None
        if isinstance(obj, dict):
            return {k: _finite(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_finite(v) for v in obj]
        return obj

    def read_last_lines(filename, n=15):
        filepath = os.path.join(data_dir, filename)
        if not os.path.exists(filepath):
            return []
        lines = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            lines.append(_finite(json.loads(line.strip())))
                        except Exception:
                            pass
            return lines[-n:]
        except Exception:
            return []

    arima_instances = {}
    lstm_instances = {}
    adaptive_instances = {}
    
    try:
        p_adaptive = os.path.join(data_dir, "pilot_instances_adaptive.json")
        if os.path.exists(p_adaptive):
            with open(p_adaptive, "r") as f:
                adaptive_instances = json.load(f)
    except Exception:
        pass

    try:
        p_arima = os.path.join(data_dir, "pilot_instances_arima.json")
        if os.path.exists(p_arima):
            with open(p_arima, "r") as f:
                arima_instances = json.load(f)
    except Exception:
        pass

    try:
        p_lstm = os.path.join(data_dir, "pilot_instances_lstm.json")
        if os.path.exists(p_lstm):
            with open(p_lstm, "r") as f:
                lstm_instances = json.load(f)
    except Exception:
        pass

    # Instance metadata (instance IDs, public IPs) is used only for a count
    # and never returned to the client.
    return {
        "adaptive_logs": read_last_lines("pilot_adaptive.jsonl", 15),
        "arima_logs": read_last_lines("pilot_arima.jsonl", 15),
        "lstm_logs": read_last_lines("pilot_lstm.jsonl", 15),
        "active_regions_count": len(adaptive_instances) or len(arima_instances) or len(lstm_instances) or 12
    }


@app.get("/forecasting/multi-stage")
async def get_multi_stage_forecasting(region_name: Optional[str] = None):
    """
    Returns 3-stage lookahead (3h, 6h, 12h) comparison across all regions or a specific region.
    """
    try:
        from services.real_temporal_forecaster import forecast_lstm_forward
        from services.forecaster import forecast_next_hours
        import datetime

        now_dt = datetime.datetime.now(datetime.timezone.utc)
        hour_of_day = now_dt.hour
        window_start_hour = (hour_of_day - (lstm_forecaster.WINDOW_HOURS - 1)) % 24

        results = {}
        for app_name, meta in ElectricityService.REGION_MAP.items():
            if region_name and app_name.lower() != region_name.lower() and meta["zone"].lower() != region_name.lower():
                continue

            zone_code = meta["zone"]
            hist_file = os.path.join(config.DATA_DIR, "history", f"ci_history_{zone_code}.json")
            trailing = [200.0] * 24
            if os.path.exists(hist_file):
                try:
                    with open(hist_file, "r") as f:
                        h_data = json.load(f)
                        trailing = [float(p.get("carbonIntensity", 200.0)) for p in h_data[-24:]]
                except Exception:
                    pass

            # Live CI
            try:
                live_ci = ElectricityService().get_carbon_intensity(zone_code)
                if live_ci:
                    trailing[-1] = float(live_ci)
            except Exception:
                pass

            cur_ci = trailing[-1]

            # ARIMA Forecast (12h)
            try:
                arima_preds = forecast_next_hours(trailing, n_hours=12)
            except Exception:
                arima_preds = [cur_ci] * 12

            # LSTM Forecast (12h)
            try:
                bundle = lstm_forecaster.load_model(zone_code)
                if bundle:
                    lstm_preds, _ = forecast_lstm_forward(bundle, trailing, window_start_hour, 12)
                else:
                    lstm_preds = [cur_ci] * 12
            except Exception:
                lstm_preds = [cur_ci] * 12

            # Compute multi-horizon summaries (1h, 3h, 6h, 12h)
            # OFF-safe fallbacks, matching the live runners: if the calibration
            # file is missing or malformed, ARIMA stays disabled and CarbonLSTM
            # keeps its data-driven 15%.
            guard_fallback = {"CarbonLSTM": 15.0, "ARIMA(2,1,2)": 1000.0}

            def summarize_stages(preds, model_name):
                # optimal_offset is HOURS AHEAD: 0 means run now. preds[i] is
                # the forecast for T+(i+1)h. Every stage then passes through the
                # same no-regret guard the live runners use, at that
                # model+horizon's calibrated threshold, so this endpoint can
                # never recommend a delay the guard itself would refuse.
                def stage(n, horizon):
                    window = preds[:n]
                    best_i = min(range(len(window)), key=lambda i: window[i])
                    best_ci = window[best_i]
                    no_cleaner_hour = best_ci >= cur_ci
                    raw_offset = 0 if no_cleaner_hour else best_i + 1
                    raw_savings = round(max(0.0, (cur_ci - best_ci) / max(1.0, cur_ci) * 100), 1)

                    threshold = forecast_calibration.applied_threshold(
                        model_name, horizon, fallback=guard_fallback.get(model_name, 2.5))
                    guarded_offset, guarded_ci, guard_reason = failsafe_engine.apply_no_regret_guard(
                        current_ci=cur_ci,
                        predicted_optimal_ci=best_ci,
                        optimal_offset=raw_offset,
                        min_saving_threshold_pct=threshold,
                    )

                    return {
                        "optimal_offset": guarded_offset,
                        "predicted_ci": guarded_ci,
                        "savings_pct": round(max(0.0, (cur_ci - guarded_ci) / max(1.0, cur_ci) * 100), 1),
                        "no_cleaner_hour": no_cleaner_hour,
                        "guard_held": guarded_offset == 0 and raw_offset > 0,
                        "guard_threshold_pct": threshold,
                        "guard_reason": guard_reason,
                        "model_proposed_offset": raw_offset,
                        "model_proposed_ci": cur_ci if no_cleaner_hour else best_ci,
                        "model_proposed_savings_pct": raw_savings,
                        # The cleanest hour the model sees in this window, even
                        # when it is dirtier than now -- this is what differs
                        # between the 3h, 6h and 12h views.
                        "best_future_offset": best_i + 1,
                        "best_future_ci": best_ci,
                        "best_future_change_pct": round((best_ci - cur_ci) / max(1.0, cur_ci) * 100, 1),
                    }

                return {"1h": stage(1, 1), "3h": stage(3, 3), "6h": stage(6, 6), "12h": stage(12, 12)}

            results[app_name] = {
                "zone": zone_code,
                "current_ci": cur_ci,
                "arima_forecast_12h": arima_preds,
                "lstm_forecast_12h": lstm_preds,
                "arima_stages": summarize_stages(arima_preds, "ARIMA(2,1,2)"),
                "lstm_stages": summarize_stages(lstm_preds, "CarbonLSTM")
            }

        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/forecasting/verification")
async def get_forecast_verification():
    """
    Returns ground-truth verification summary metrics (MAE, RMSE, Directional Accuracy, Realized Savings)
    for 1h, 3h, 6h horizons.
    """
    try:
        from services import forecast_tracker
        return {
            "metrics": forecast_tracker.compute_verification_metrics(),
            "pending_count": len(forecast_tracker.load_pending())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Include routers
app.include_router(router)
app.include_router(research_router)
app.include_router(history_router)

if __name__ == "__main__":
    import uvicorn
    # explicitly reload for dev
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=True)

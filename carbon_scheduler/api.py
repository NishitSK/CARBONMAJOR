from fastapi import FastAPI, HTTPException, APIRouter, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import sys
import os

# Add parent directory to path to import current logic
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.region import Region
from models.workload import Workload
from services.simulator import Simulator
from services.scheduler import Scheduler, build_joint_region_pool
from services import forecaster
from services import lstm_forecaster
from services.electricity_service import ElectricityService
import config

app = FastAPI(title="Carbon-Aware Scheduler API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Include router
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    # explicitly reload for dev
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=True)

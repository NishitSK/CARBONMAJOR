"""
Serves REAL historical carbon-intensity data (carbon_scheduler/data/history/
ci_history_*.json, the same 2021-2025 dataset every research script in
scripts/ is built from) for the main site's historical-replay demo. This is
deliberately separate from the live-simulation endpoints in api.py (which
serve synthetic/current-moment data for the /playground sandbox) -- the
whole point of this endpoint is that it never fabricates anything.

GET /regions/history/range   -> real dataset's start/end bounds
GET /regions/history/at      -> real per-region CI at one real hour,
                                 shaped like the existing GET /regions/
                                 response so the frontend can feed it
                                 straight into the existing POST /score
                                 endpoint for the real decision.
"""
import json
import os

from fastapi import APIRouter, HTTPException

import config
from services.electricity_service import ElectricityService

router = APIRouter(prefix="/regions/history")

HISTORY_DIR = os.path.join(config.DATA_DIR, "history")

_series_by_zone = None
_common_ts = None


def _load():
    """Lazy-loaded, cached: per-zone real CI series + the common timestamp
    range across all zones. Same loader pattern as every scripts/*.py file
    (e.g. static_lookup_baseline.py)."""
    global _series_by_zone, _common_ts
    if _series_by_zone is not None:
        return _series_by_zone, _common_ts

    region_map = ElectricityService.REGION_MAP
    zone_to_region = {meta["zone"]: name for name, meta in region_map.items()}
    series_by_zone = {}
    for fname in os.listdir(HISTORY_DIR):
        if not fname.startswith("ci_history_"):
            continue
        zone = fname[len("ci_history_"):-len(".json")]
        if zone not in zone_to_region:
            continue
        with open(os.path.join(HISTORY_DIR, fname), encoding="utf-8") as f:
            records = json.load(f)
        series_by_zone[zone] = {r["datetime"]: r["carbonIntensity"] for r in records}

    common_ts = sorted(set.intersection(*[set(s.keys()) for s in series_by_zone.values()]))
    _series_by_zone, _common_ts = series_by_zone, common_ts
    return _series_by_zone, _common_ts


@router.get("/range")
async def get_history_range():
    """Real dataset bounds, for the frontend time-scrubber's slider limits."""
    _, common_ts = _load()
    if not common_ts:
        raise HTTPException(status_code=500, detail="No historical data available")
    return {"start": common_ts[0], "end": common_ts[-1], "n_hours": len(common_ts)}


@router.get("/at")
async def get_history_at(timestamp: str):
    """Real per-region CI at one real historical hour, shaped like the
    existing GET /regions/ response (name/carbon/latency/resources/lat/lng)
    so it can be posted straight to the existing /score endpoint."""
    series_by_zone, common_ts = _load()
    if timestamp not in common_ts:
        raise HTTPException(status_code=404, detail="No real data at that timestamp")

    region_map = ElectricityService.REGION_MAP
    zone_to_region = {meta["zone"]: name for name, meta in region_map.items()}
    with open(os.path.join(config.DATA_DIR, "cloud_latency.json"), encoding="utf-8") as f:
        static_latency = json.load(f)["latency_ms"]

    regions = []
    for zone, series in series_by_zone.items():
        region_name = zone_to_region[zone]
        ci = series.get(timestamp)
        lat = static_latency.get(region_name)
        if ci is None or lat is None:
            continue
        meta = region_map[region_name]
        regions.append({
            "name": region_name,
            "carbon": ci,
            "latency": lat,
            "resources": 80.0,
            "lat": meta["lat"],
            "lng": meta["lng"],
        })
    return {"timestamp": timestamp, "regions": regions}

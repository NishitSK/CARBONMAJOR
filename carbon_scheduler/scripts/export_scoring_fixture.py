"""
Writes a golden fixture of the real Scheduler's /score-equivalent output so
the in-browser port (carbon_scheduler_ui/src/sim/scoring.js) can be checked
against it by carbon_scheduler_ui/src/sim/__tests__/parity.test.js.

Uses synthetic region values only -- no licensed carbon data goes into the
fixture. Re-run after any change to services/scheduler.py:

    python scripts/export_scoring_fixture.py
"""
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from models.region import Region
from services.scheduler import Scheduler

OUT_PATH = os.path.join(
    os.path.dirname(BASE_DIR),
    "carbon_scheduler_ui", "src", "sim", "__tests__", "fixtures", "scoring_parity.json",
)

REGIONS = [
    {"name": "r-clean-far", "carbon": 25, "latency": 240, "resources": 60},
    {"name": "r-clean-near", "carbon": 40, "latency": 150, "resources": 45},
    {"name": "r-mid", "carbon": 210, "latency": 120, "resources": 80},
    {"name": "r-mid-tie", "carbon": 210, "latency": 120, "resources": 90},
    {"name": "r-dirty-near", "carbon": 690, "latency": 15, "resources": 95},
    {"name": "r-dirty-far", "carbon": 520, "latency": 310, "resources": 30},
]

CASES = [
    {"id": "default", "weights": {"carbon": 0.4, "latency": 0.3, "resources": 0.3}, "max_latency": 200},
    {"id": "carbon_heavy_wide_sla", "weights": {"carbon": 0.8, "latency": 0.2, "resources": 0.0}, "max_latency": 250},
    {"id": "latency_heavy_widest_sla", "weights": {"carbon": 0.2, "latency": 0.7, "resources": 0.1}, "max_latency": 400},
    {"id": "tight_sla", "weights": {"carbon": 0.4, "latency": 0.3, "resources": 0.3}, "max_latency": 50},
    {"id": "no_eligible", "weights": {"carbon": 0.4, "latency": 0.3, "resources": 0.3}, "max_latency": 10},
]


def run_case(scheduler, case):
    region_objs = [Region(**r) for r in REGIONS]
    eligible = scheduler.filter_regions(region_objs, case["max_latency"])
    rejected = [r.name for r in region_objs if r not in eligible]
    if not eligible:
        return {"success": False, "eligible": [], "rejected": rejected, "summary": None}

    scored = scheduler.calculate_scores(eligible, case["weights"])
    return {
        "success": True,
        "eligible": [
            {
                "name": region.name,
                "score": score,
                "c_norm": meta["c_norm"],
                "l_norm": meta["l_norm"],
                "r_penalty": meta["r_penalty"],
                "strengths": meta["strengths"],
            }
            for region, score, meta in scored
        ],
        "rejected": rejected,
        "summary": scheduler.explain_decision(scored[0])["summary"],
    }


def main():
    scheduler = Scheduler()
    fixture = {
        "regions": REGIONS,
        "cases": [{**case, "expected": run_case(scheduler, case)} for case in CASES],
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(fixture, f, indent=2)
    print(f"Wrote {len(CASES)} cases to {OUT_PATH}")


if __name__ == "__main__":
    main()

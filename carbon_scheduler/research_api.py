"""
Serves the project's research result files (carbon_scheduler/data/*.json)
to the frontend. Every file is a static research artifact produced by a
scripts/*.py run, not live simulation state -- this is deliberately a
read-only, allowlisted pass-through, not 24+ bespoke typed endpoints, since
the files are heterogeneous and the frontend renders them via a config-
driven component (see carbon_scheduler_ui/src/config/resultsConfig.js).

Only files listed in RESEARCH_FILES are servable. Live-demo runtime state
(predictions_24h.json, workload_active_region.json, regions.json) and
internal logs are intentionally excluded -- this is research data, not the
live scheduler's working state.
"""
import json
import os

from fastapi import APIRouter, HTTPException

import config

router = APIRouter(prefix="/research")

RESEARCH_FILES = {
    # --- decomposition & significance ---
    "held_out_generalization_test": {
        "filename": "held_out_generalization_test.json",
        "category": "decomposition",
        "title": "Held-out generalization (2024-2025)",
        "description": "Scheduler vs. static-lookup vs. fixed baseline on a genuine held-out split, with paired significance tests and an autocorrelation-adjusted effective sample size.",
    },
    "static_lookup_baseline": {
        "filename": "static_lookup_baseline.json",
        "category": "decomposition",
        "title": "Static-lookup baseline (in-sample)",
        "description": "Full adaptive scheduler vs. a naive best-region-on-average lookup vs. a fixed baseline, on the full 5-year dataset.",
    },
    "significance_test_adaptivity": {
        "filename": "significance_test_adaptivity.json",
        "category": "decomposition",
        "title": "Significance of the adaptivity gain",
        "description": "Bootstrap confidence interval and significance tests for the scheduler's advantage over the static lookup.",
    },
    "subgroup_characterization": {
        "filename": "subgroup_characterization.json",
        "category": "decomposition",
        "title": "Where the scheduler and baseline disagree",
        "description": "Seasonal and data-quality characterization of the decisions where the adaptive scheduler picks a different region than the static lookup.",
    },
    # --- generalization / robustness ---
    "pool_generalization_sweep": {
        "filename": "pool_generalization_sweep.json",
        "category": "generalization",
        "title": "Region-pool generalization sweep",
        "description": "Leave-one-region-out and carbon/latency-weight sweeps, testing whether the decomposition finding is specific to Sweden and Canada.",
    },
    "resources_ablation": {
        "filename": "resources_ablation.json",
        "category": "generalization",
        "title": "Resources-term ablation",
        "description": "Effect of removing the constant resource-availability scoring term on scheduling decisions.",
    },
    "hypothetical_constrained_benchmark": {
        "filename": "hypothetical_constrained_benchmark.json",
        "category": "generalization",
        "title": "Capacity-constrained scenario benchmark",
        "description": "Scheduler behavior when candidate regions have limited capacity.",
    },
    # --- forecasting ---
    "evaluation_report": {
        "filename": "evaluation_report.json",
        "category": "forecasting",
        "title": "Forecast accuracy (6h horizon)",
        "description": "LSTM vs. ARIMA vs. naive-persistence mean absolute error per zone, 6-hour-ahead forecasts.",
    },
    "evaluation_report_24h": {
        "filename": "evaluation_report_24h.json",
        "category": "forecasting",
        "title": "Forecast accuracy (24h horizon)",
        "description": "LSTM vs. ARIMA vs. naive-persistence mean absolute error per zone, 24-hour-ahead forecasts.",
    },
    "evaluation_report_seasonal_6h": {
        "filename": "evaluation_report_seasonal_6h.json",
        "category": "forecasting",
        "title": "Seasonal forecast accuracy (6h horizon)",
        "description": "Same 6-hour forecast backtest, broken out by season and zone.",
    },
    "evaluation_report_seasonal_24h": {
        "filename": "evaluation_report_seasonal_24h.json",
        "category": "forecasting",
        "title": "Seasonal forecast accuracy (24h horizon)",
        "description": "Same 24-hour forecast backtest, broken out by season and zone -- ARIMA wins at 6h, LSTM wins at 24h.",
    },
    "forecast_in_the_loop_replay": {
        "filename": "forecast_in_the_loop_replay.json",
        "category": "forecasting",
        "title": "Real forecasts driving the region decision (WHERE)",
        "description": "Wiring real ARIMA/LSTM forecasts into the spatial region-pick decision instead of live telemetry -- a near-null result.",
    },
    "temporal_shift_benchmark": {
        "filename": "temporal_shift_benchmark.json",
        "category": "forecasting",
        "title": "Real forecasts driving the delay decision (WHEN)",
        "description": "Wiring real ARIMA/LSTM forecasts into the delay-tolerant timing decision -- a genuinely positive result, up to +8.4% at a 24h deadline.",
    },
    # --- baselines / historical backtests ---
    "baseline_comparison": {
        "filename": "baseline_comparison.json",
        "category": "baselines",
        "title": "Baseline comparison",
        "description": "Scheduler vs. round-robin vs. always-cheapest vs. fixed-region baselines.",
    },
    "baseline_comparison_threshold_v1": {
        "filename": "baseline_comparison_threshold_v1.json",
        "category": "baselines",
        "title": "Baseline comparison (post threshold-scoring fix)",
        "description": "Same baseline comparison after the threshold-based latency scoring fix.",
    },
    "historical_decision_benchmark": {
        "filename": "historical_decision_benchmark.json",
        "category": "baselines",
        "title": "Historical decision backtest",
        "description": "Real historical-date backtest of scheduling decisions.",
    },
    "historical_decision_benchmark_cloud_vantage": {
        "filename": "historical_decision_benchmark_cloud_vantage.json",
        "category": "baselines",
        "title": "Historical decision backtest (cloud-vantage latency)",
        "description": "Same historical backtest using real multi-prober cloud-vantage latency instead of single-vantage measurements.",
    },
    # --- measurement-bias corrections ---
    "latency_bias_analysis": {
        "filename": "latency_bias_analysis.json",
        "category": "measurement",
        "title": "Latency measurement bias analysis",
        "description": "Single-vantage-point latency measurements were biased by distance from the measuring machine -- this is the analysis that caught it.",
    },
    "multi_vantage_latency": {
        "filename": "multi_vantage_latency.json",
        "category": "measurement",
        "title": "Multi-vantage latency correction",
        "description": "Real latency measured from multiple probers, used to correct the single-vantage bias.",
    },
    "cloud_latency": {
        "filename": "cloud_latency.json",
        "category": "measurement",
        "title": "Cloud-vantage latency (used by the scheduler)",
        "description": "Real, corrected latency per region -- the values the scheduler's SLA filter uses today.",
    },
    # --- live AWS pilot ---
    "pilot_report": {
        "filename": "pilot_report.json",
        "category": "pilot",
        "title": "Live AWS pilot report",
        "description": "Summary results from the live multi-region AWS pilot deployment.",
    },
    "pilot_instances": {
        "filename": "pilot_instances.json",
        "category": "pilot",
        "title": "Live AWS pilot instances",
        "description": "Metadata for the real AWS instances used in the pilot deployment.",
    },
    "real_workload_cpu": {
        "filename": "real_workload_cpu.json",
        "category": "pilot",
        "title": "Real measured CPU utilization",
        "description": "CPU utilization measured on a real pilot-region instance during workload execution.",
    },
    "workload_migration_demo": {
        "filename": "workload_migration_demo.json",
        "category": "pilot",
        "title": "Real workload migration",
        "description": "A real recorded scheduling decision and workload execution/migration, confirmed via CloudWatch.",
    },
    "synthetic_migration_stress_test": {
        "filename": "synthetic_migration_stress_test.json",
        "category": "pilot",
        "title": "Migration continuity stress test",
        "description": "Repeated workload-migration cycles testing continuity of a stateful workload across region switches.",
    },
}


@router.get("/manifest")
async def get_manifest():
    """List every servable research result, grouped implicitly by category."""
    return [
        {"id": result_id, "category": meta["category"], "title": meta["title"], "description": meta["description"]}
        for result_id, meta in RESEARCH_FILES.items()
    ]


@router.get("/{result_id}")
async def get_research_result(result_id: str):
    """Return one research result's raw JSON. 404 if not on the allowlist."""
    meta = RESEARCH_FILES.get(result_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Unknown research result id")
    path = os.path.join(config.DATA_DIR, meta["filename"])
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Result file not found on disk")

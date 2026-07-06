"""
Predicts what the scheduler would recommend at a specific future timestamp,
by forecasting each region's carbon intensity forward to that hour (via
ARIMA, which has no fixed horizon cap unlike the 6h-trained production
LSTM) and running the real scoring pipeline (Scheduler.filter_regions /
calculate_scores / explain_decision) on the predicted snapshot.

No network calls - forecasts are generated locally from each region's
known baseline CI via the existing synthetic-diurnal + ARIMA pipeline.

Run from carbon_scheduler/:
    python scripts/predict_at_time.py --target "2026-07-01T12:00:00"
    python scripts/predict_at_time.py   # defaults to 12:00 UTC tomorrow
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from models.region import Region
from services.scheduler import Scheduler
from services.simulator import Simulator
from services import forecaster


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=str, default=None,
                         help="Target UTC datetime, e.g. 2026-07-01T12:00:00. Defaults to 12:00 UTC tomorrow.")
    parser.add_argument("--max-latency", type=float, default=config.DEFAULT_MAX_LATENCY)
    args = parser.parse_args()

    now = datetime.now(timezone.utc).replace(microsecond=0)
    if args.target:
        target = datetime.fromisoformat(args.target).replace(tzinfo=timezone.utc)
    else:
        tomorrow = now + timedelta(days=1)
        target = tomorrow.replace(hour=12, minute=0, second=0)

    hours_ahead = (target - now).total_seconds() / 3600
    hours_ahead_int = max(1, round(hours_ahead))

    print(f"Now (UTC):     {now.isoformat()}")
    print(f"Target (UTC):  {target.isoformat()}")
    print(f"Hours ahead:   {hours_ahead:.2f}h (forecasting {hours_ahead_int} hourly steps via ARIMA)\n")

    sim = Simulator(demo_mode=True)
    base_regions = sim.get_simulation_data("fixed")
    scheduler = Scheduler()

    predicted_regions = []
    forecasts = {}
    for region in base_regions:
        history = forecaster.generate_synthetic_history(region.carbon, hours=24, seed=hash(region.name) % (2**31))
        forecast_vals = forecaster.forecast_next_hours(history, n_hours=hours_ahead_int)
        predicted_ci = forecast_vals[-1]
        forecasts[region.name] = forecast_vals
        predicted_regions.append(Region(
            name=region.name,
            carbon=predicted_ci,
            latency=region.latency,
            resources=region.resources,
            lat=region.lat,
            lng=region.lng
        ))

    print(f"{'Region':<28} {'Current CI':>11} {'Predicted CI':>13} {'Latency':>9} {'Resources':>10}")
    print("-" * 75)
    for base, pred in zip(base_regions, predicted_regions):
        print(f"{base.name:<28} {base.carbon:>9.1f}g {pred.carbon:>11.1f}g {pred.latency:>7.0f}ms {pred.resources:>9.0f}%")

    eligible = scheduler.filter_regions(predicted_regions, args.max_latency)
    rejected = [r for r in predicted_regions if r not in eligible]

    print(f"\nSLA constraint: max_latency={args.max_latency}ms")
    print(f"Eligible: {len(eligible)} | Rejected: {len(rejected)}")
    if rejected:
        print("Rejected (latency > SLA):", ", ".join(r.name for r in rejected))

    if not eligible:
        print("\nNo region meets the latency constraint at the predicted time.")
        return

    scored = scheduler.calculate_scores(eligible, config.DEFAULT_WEIGHTS)
    print(f"\n--- Predicted ranking at {target.isoformat()} (weights={config.DEFAULT_WEIGHTS}) ---")
    print(f"{'Rank':<5} {'Region':<28} {'Pred. CI':>9} {'Score':>8} {'Strengths'}")
    for i, (region, score, meta) in enumerate(scored, start=1):
        print(f"{i:<5} {region.name:<28} {region.carbon:>7.1f}g {score:>8.4f}  {', '.join(meta['strengths']) or '-'}")

    best_region, best_score, best_meta = scored[0]
    explanation = scheduler.explain_decision(scored[0])
    print(f"\n--- Recommendation ---")
    print(f"Region: {best_region.name}")
    print(f"Predicted carbon intensity: {best_region.carbon:.1f} gCO2/kWh at {target.isoformat()}")
    print(f"Score: {best_score:.4f}")
    print(f"Summary: {explanation['summary']}")
    print(f"Details: {explanation['details']}")


if __name__ == "__main__":
    main()

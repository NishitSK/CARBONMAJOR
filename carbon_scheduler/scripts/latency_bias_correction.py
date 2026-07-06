"""
Quantifies the geographic bias in the pilot's latency measurements (TCP
connect from one home laptop in India to 12 AWS regions) instead of leaving
it as an unquantified limitation. Fits latency ~ great-circle distance and
reports the residual per region - i.e. how much of each region's latency
is "distance you can't avoid" versus unexplained variance.

This does not fix the raw measurement (that needs an EC2-to-EC2 vantage
point) but turns "hidden single-vantage-point bias" into "quantified and
disclosed distance effect," which is the defensible framing per the council
review.

Run from carbon_scheduler/: python scripts/latency_bias_correction.py
"""
import json
import math
import os
import statistics
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from services.electricity_service import ElectricityService

TAGGED_LOG_PATH = os.path.join(config.DATA_DIR, "pilot_log_tagged.jsonl")

# Approximate vantage point: Bangalore, India (IST timezone, and observed
# latency ordering - Mumbai/Singapore fastest - is consistent with a South
# Indian origin). This is an assumption, stated explicitly for the paper.
VANTAGE_LAT, VANTAGE_LNG = 12.97, 77.59


def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def main():
    region_map = ElectricityService.REGION_MAP

    with open(TAGGED_LOG_PATH) as f:
        records = [json.loads(l) for l in f if l.strip()]
    live_records = [r for r in records if r.get("data_quality") == ["live"]]

    # Average latency per region across all clean cycles
    lat_samples = {}
    for r in live_records:
        for region, m in r["measurements"].items():
            lat_samples.setdefault(region, []).append(m["latency_ms"])

    rows = []
    for region, samples in lat_samples.items():
        meta = region_map.get(region)
        if not meta:
            continue
        dist = haversine_km(VANTAGE_LAT, VANTAGE_LNG, meta["lat"], meta["lng"])
        avg_lat = statistics.mean(samples)
        rows.append({"region": region, "distance_km": dist, "avg_latency_ms": avg_lat})

    # Simple linear regression: latency = a + b * distance
    n = len(rows)
    mean_d = sum(r["distance_km"] for r in rows) / n
    mean_l = sum(r["avg_latency_ms"] for r in rows) / n
    cov = sum((r["distance_km"] - mean_d) * (r["avg_latency_ms"] - mean_l) for r in rows)
    var = sum((r["distance_km"] - mean_d) ** 2 for r in rows)
    b = cov / var if var else 0
    a = mean_l - b * mean_d

    r_num = sum((r["distance_km"] - mean_d) * (r["avg_latency_ms"] - mean_l) for r in rows)
    r_den = math.sqrt(var * sum((r["avg_latency_ms"] - mean_l) ** 2 for r in rows))
    r_corr = r_num / r_den if r_den else 0

    print(f"Vantage point assumed: ~Bangalore, India ({VANTAGE_LAT}, {VANTAGE_LNG})")
    print(f"Fitted model: latency_ms = {a:.1f} + {b:.4f} * distance_km")
    print(f"Correlation (r): {r_corr:.3f}  (r^2 = {r_corr**2:.3f})")
    print()
    print(f"{'Region':<28} {'Dist (km)':>10} {'Avg Lat (ms)':>13} {'Predicted':>10} {'Residual':>10}")
    print("-" * 75)
    for r in sorted(rows, key=lambda x: x["distance_km"]):
        predicted = a + b * r["distance_km"]
        residual = r["avg_latency_ms"] - predicted
        print(f"{r['region']:<28} {r['distance_km']:>10.0f} {r['avg_latency_ms']:>13.1f} "
              f"{predicted:>10.1f} {residual:>+10.1f}")

    print()
    print(f"Interpretation: r^2={r_corr**2:.2f} of latency variance is explained by pure")
    print("great-circle distance from a single home vantage point. This confirms the")
    print("bias is systematic (distance-driven), not random noise - it does not average")
    print("out with more cycles. Residuals above represent network-specific effects")
    print("(routing, peering, congestion) beyond geographic distance.")

    out_path = os.path.join(config.DATA_DIR, "latency_bias_analysis.json")
    with open(out_path, "w") as f:
        json.dump({
            "vantage_point_assumed": {"lat": VANTAGE_LAT, "lng": VANTAGE_LNG, "label": "Bangalore, India (assumed)"},
            "model": {"intercept": a, "slope": b, "r_squared": r_corr ** 2},
            "regions": rows,
        }, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()

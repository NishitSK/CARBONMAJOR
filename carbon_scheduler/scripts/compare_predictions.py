"""
Compares saved 24h predictions vs actuals from pilot_log.jsonl.
Generates an interactive HTML chart: predicted line + actual dots per region.

Run from carbon_scheduler/: python scripts/compare_predictions.py
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

PREDICTIONS_PATH = os.path.join(config.DATA_DIR, "predictions_24h.json")
LOG_PATH = os.path.join(config.DATA_DIR, "pilot_log.jsonl")
OUT_PATH = os.path.join(config.DATA_DIR, "prediction_comparison.html")

COLORS = [
    "#5EE6C8", "#E8C547", "#E85D4A", "#7B9FE0", "#E8853D",
    "#3DDC84", "#C97BF5", "#F57BBF", "#7BE0E0", "#E0A87B",
    "#A8E07B", "#E07B7B"
]


def load_predictions():
    with open(PREDICTIONS_PATH) as f:
        return json.load(f)


def load_actuals():
    actuals = {}  # region -> list of {timestamp, ci}
    with open(LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            for region, m in r["measurements"].items():
                actuals.setdefault(region, []).append({
                    "timestamp": r["timestamp"],
                    "ci": m["carbon_intensity"]
                })
    return actuals


def build_chart(predictions, actuals):
    generated_at = predictions["generated_at"]
    gen_dt = datetime.fromisoformat(generated_at)
    regions = list(predictions["regions"].keys())

    datasets_js = []
    for i, region in enumerate(regions):
        color = COLORS[i % len(COLORS)]
        pred_data = predictions["regions"][region]["hourly"]

        # Predicted line
        pred_points = [
            "{{x: new Date('{}'), y: {}}}".format(p["timestamp"], p["predicted_ci"])
            for p in pred_data
        ]
        datasets_js.append("""{{
            label: '{} (predicted)',
            data: [{}],
            borderColor: '{}',
            backgroundColor: '{}22',
            borderDash: [6, 3],
            pointRadius: 0,
            tension: 0.3,
            yAxisID: 'y'
        }}""".format(region, ", ".join(pred_points), color, color))

        # Actual dots
        region_actuals = actuals.get(region, [])
        actual_points = []
        for a in region_actuals:
            ts = datetime.fromisoformat(a["timestamp"])
            if ts >= gen_dt:
                actual_points.append("{{x: new Date('{}'), y: {}}}".format(a["timestamp"], a["ci"]))

        if actual_points:
            datasets_js.append("""{{
                label: '{} (actual)',
                data: [{}],
                borderColor: '{}',
                backgroundColor: '{}',
                borderDash: [],
                pointRadius: 6,
                pointStyle: 'circle',
                showLine: false,
                yAxisID: 'y'
            }}""".format(region, ", ".join(actual_points), color, color))  # noqa

    # MAE summary
    mae_rows = ""
    for region in regions:
        pred_data = predictions["regions"][region]["hourly"]
        pred_lookup = {p["timestamp"][:13]: p["predicted_ci"] for p in pred_data}
        region_actuals = actuals.get(region, [])
        errors = []
        for a in region_actuals:
            ts = datetime.fromisoformat(a["timestamp"])
            if ts >= gen_dt:
                key = a["timestamp"][:13]
                if key in pred_lookup:
                    errors.append(abs(pred_lookup[key] - a["ci"]))
        if errors:
            mae = sum(errors) / len(errors)
            mae_rows += "<tr><td>{}</td><td>{:.1f}g</td><td>{}</td></tr>".format(
                region, mae, len(errors))

    mae_table = ""
    if mae_rows:
        mae_table = """
        <div class='mae-box'>
            <h3>Prediction Error (MAE)</h3>
            <table>
                <tr><th>Region</th><th>MAE</th><th>Samples</th></tr>
                {}
            </table>
        </div>""".format(mae_rows)

    html = """<!DOCTYPE html>
<html>
<head>
<meta charset='utf-8'>
<title>Carbon Intensity: Predicted vs Actual</title>
<script src='https://cdn.jsdelivr.net/npm/chart.js@4'></script>
<script src='https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3'></script>
<style>
  body {{ background:#0A0E15; color:#C8D6E5; font-family:'IBM Plex Sans',sans-serif; margin:0; padding:24px; }}
  h1 {{ color:#5EE6C8; font-size:1.4rem; margin-bottom:4px; }}
  .sub {{ color:#6B7E93; font-size:0.85rem; margin-bottom:24px; }}
  .chart-wrap {{ background:#10151F; border-radius:12px; padding:20px; margin-bottom:24px; }}
  .mae-box {{ background:#10151F; border-radius:12px; padding:20px; }}
  .mae-box h3 {{ color:#5EE6C8; margin-top:0; }}
  table {{ border-collapse:collapse; width:100%; }}
  th {{ color:#5EE6C8; text-align:left; padding:6px 12px; border-bottom:1px solid #1E2A3A; }}
  td {{ padding:6px 12px; border-bottom:1px solid #1A2030; }}
  .note {{ color:#6B7E93; font-size:0.8rem; margin-top:16px; }}
</style>
</head>
<body>
<h1>Carbon Intensity — Predicted vs Actual</h1>
<div class='sub'>Predictions generated at {} IST &nbsp;|&nbsp; Dashed = ARIMA forecast &nbsp;|&nbsp; Dots = Real measured values</div>
<div class='chart-wrap'>
  <canvas id='chart' height='120'></canvas>
</div>
{}
<p class='note'>Refresh this file after each new pilot cycle to see updated actuals.</p>
<script>
const ctx = document.getElementById('chart').getContext('2d');
new Chart(ctx, {{
  type: 'line',
  data: {{ datasets: [{}] }},
  options: {{
    responsive: true,
    interaction: {{ mode: 'index', intersect: false }},
    plugins: {{
      legend: {{ labels: {{ color: '#C8D6E5', font: {{ size: 11 }} }} }},
      tooltip: {{ backgroundColor: '#10151F', titleColor: '#5EE6C8', bodyColor: '#C8D6E5' }}
    }},
    scales: {{
      x: {{
        type: 'time',
        time: {{ unit: 'hour', displayFormats: {{ hour: 'dd MMM HH:mm' }} }},
        ticks: {{ color: '#6B7E93' }},
        grid: {{ color: '#1A2030' }}
      }},
      y: {{
        title: {{ display: true, text: 'Carbon Intensity (gCO2/kWh)', color: '#6B7E93' }},
        ticks: {{ color: '#6B7E93' }},
        grid: {{ color: '#1A2030' }}
      }}
    }}
  }}
}});
</script>
</body>
</html>""".format(
        (gen_dt + timedelta(hours=5, minutes=30)).strftime("%d %b %I:%M %p"),
        mae_table,
        ",\n".join(datasets_js)
    )
    return html


def main():
    predictions = load_predictions()
    actuals = load_actuals()
    html = build_chart(predictions, actuals)
    with open(OUT_PATH, "w") as f:
        f.write(html)
    print("Chart saved -> {}".format(OUT_PATH))

    # Quick text summary
    gen_dt = datetime.fromisoformat(predictions["generated_at"])
    total_actuals = sum(
        1 for region in predictions["regions"]
        for a in actuals.get(region, [])
        if datetime.fromisoformat(a["timestamp"]) >= gen_dt
    )
    print("Actual data points plotted: {}".format(total_actuals))


if __name__ == "__main__":
    main()

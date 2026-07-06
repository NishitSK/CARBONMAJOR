"""
Generates an interactive HTML chart of the laptop-vantage pilot data trend
(pilot_log.jsonl) - carbon intensity and latency per region over time, plus
which region won each cycle. This is the pilot tied to the physical laptop
location (home ISP), as opposed to the corrected cloud-vantage pilot.

Run from carbon_scheduler/: python scripts/plot_laptop_vantage_trend.py
"""
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

LOG_PATH = os.path.join(config.DATA_DIR, "pilot_log.jsonl")
OUT_PATH = os.path.join(config.DATA_DIR, "laptop_vantage_trend.html")

COLORS = [
    "#5EE6C8", "#E8C547", "#E85D4A", "#7B9FE0", "#E8853D",
    "#3DDC84", "#C97BF5", "#F57BBF", "#7BE0E0", "#E0A87B",
    "#A8E07B", "#E07B7B"
]


def main():
    with open(LOG_PATH) as f:
        records = [json.loads(l) for l in f if l.strip()]

    regions = sorted(records[0]["measurements"].keys())

    ci_datasets = []
    lat_datasets = []
    winner_points = []

    for i, region in enumerate(regions):
        color = COLORS[i % len(COLORS)]
        ci_points = []
        lat_points = []
        for r in records:
            m = r["measurements"].get(region)
            if not m:
                continue
            ci_points.append("{{x: '{}', y: {}}}".format(r["timestamp"], m["carbon_intensity"]))
            lat_points.append("{{x: '{}', y: {}}}".format(r["timestamp"], m["latency_ms"]))

        ci_datasets.append("""{{
            label: '{}',
            data: [{}],
            borderColor: '{}',
            backgroundColor: '{}22',
            pointRadius: 2,
            tension: 0.2
        }}""".format(region, ", ".join(ci_points), color, color))

        lat_datasets.append("""{{
            label: '{}',
            data: [{}],
            borderColor: '{}',
            backgroundColor: '{}22',
            pointRadius: 2,
            tension: 0.2
        }}""".format(region, ", ".join(lat_points), color, color))

    for r in records:
        d = r.get("decision") or {}
        winner = d.get("selected_region")
        if winner and winner in r["measurements"]:
            ci = r["measurements"][winner]["carbon_intensity"]
            winner_points.append("{{x: '{}', y: {}, region: '{}'}}".format(r["timestamp"], ci, winner))

    scoring_versions = sorted(set(r.get("scoring_method", "unknown") for r in records))

    html = """<!DOCTYPE html>
<html>
<head>
<meta charset='utf-8'>
<title>Laptop-Vantage Pilot Trend</title>
<script src='https://cdn.jsdelivr.net/npm/chart.js@4'></script>
<script src='https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3'></script>
<style>
  body {{ background:#0A0E15; color:#C8D6E5; font-family:'IBM Plex Sans',sans-serif; margin:0; padding:24px; }}
  h1 {{ color:#5EE6C8; font-size:1.4rem; margin-bottom:4px; }}
  .sub {{ color:#6B7E93; font-size:0.85rem; margin-bottom:24px; }}
  .chart-wrap {{ background:#10151F; border-radius:12px; padding:20px; margin-bottom:24px; }}
  h2 {{ color:#C8D6E5; font-size:1rem; margin-top:0; }}
</style>
</head>
<body>
<h1>Laptop-Vantage Pilot Data Trend</h1>
<div class='sub'>Source: pilot_log.jsonl (measured from your home laptop location) &nbsp;|&nbsp;
{n} cycles &nbsp;|&nbsp; Scoring versions in this data: {versions}</div>

<div class='chart-wrap'>
  <h2>Carbon Intensity per Region Over Time (gCO2/kWh)</h2>
  <canvas id='ciChart' height='100'></canvas>
</div>

<div class='chart-wrap'>
  <h2>Latency per Region Over Time (ms, measured from laptop)</h2>
  <canvas id='latChart' height='100'></canvas>
</div>

<div class='chart-wrap'>
  <h2>Winning Region's Carbon Intensity Each Cycle</h2>
  <canvas id='winnerChart' height='80'></canvas>
</div>

<script>
const commonScales = {{
  x: {{ type: 'time', time: {{ unit: 'hour', displayFormats: {{ hour: 'dd MMM HH:mm' }} }},
        ticks: {{ color: '#6B7E93' }}, grid: {{ color: '#1A2030' }} }},
  y: {{ ticks: {{ color: '#6B7E93' }}, grid: {{ color: '#1A2030' }} }}
}};
const legendStyle = {{ labels: {{ color: '#C8D6E5', font: {{ size: 10 }} }} }};

new Chart(document.getElementById('ciChart').getContext('2d'), {{
  type: 'line',
  data: {{ datasets: [{ci_datasets}] }},
  options: {{ responsive: true, interaction: {{ mode: 'index', intersect: false }},
    plugins: {{ legend: legendStyle }}, scales: commonScales }}
}});

new Chart(document.getElementById('latChart').getContext('2d'), {{
  type: 'line',
  data: {{ datasets: [{lat_datasets}] }},
  options: {{ responsive: true, interaction: {{ mode: 'index', intersect: false }},
    plugins: {{ legend: legendStyle }}, scales: commonScales }}
}});

new Chart(document.getElementById('winnerChart').getContext('2d'), {{
  type: 'scatter',
  data: {{ datasets: [{{
    label: 'Winning region CI',
    data: [{winner_points}],
    backgroundColor: '#5EE6C8',
    pointRadius: 5
  }}] }},
  options: {{
    responsive: true,
    plugins: {{
      legend: legendStyle,
      tooltip: {{ callbacks: {{ label: (ctx) => ctx.raw.region + ': ' + ctx.raw.y + 'g' }} }}
    }},
    scales: commonScales
  }}
}});
</script>
</body>
</html>""".format(
        n=len(records),
        versions=", ".join(scoring_versions),
        ci_datasets=",\n".join(ci_datasets),
        lat_datasets=",\n".join(lat_datasets),
        winner_points=", ".join(winner_points),
    )

    with open(OUT_PATH, "w") as f:
        f.write(html)
    print(f"Saved -> {OUT_PATH}")


if __name__ == "__main__":
    main()

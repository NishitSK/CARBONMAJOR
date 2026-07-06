import os
from dotenv import load_dotenv

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load .env from the project root (one level up from carbon_scheduler/)
load_dotenv(os.path.join(os.path.dirname(BASE_DIR), ".env"))

# Data Paths
DATA_DIR = os.path.join(BASE_DIR, "data")
REGIONS_JSON_FILE = os.path.join(DATA_DIR, "regions.json")

# Simulation Settings
DETERMINISTIC_SEED = 42

# DEFAULT_MAX_LATENCY is treated as the workload's genuine indifference
# threshold, not just a loose safety margin: below it, latency differences
# are assumed operationally imperceptible for delay-tolerant workloads, so
# calculate_scores() derives its latency scoring cutoff from this same
# constant rather than a second, independently-tunable number that could
# drift out of sync with the SLA filter.
DEFAULT_MAX_LATENCY = 200

# Version tag for the scoring methodology, logged with every scheduling
# decision so pilot data collected under different scoring logic is never
# silently merged in analysis.
SCORING_METHOD_VERSION = "threshold_v1"

# Scoring Constants (Default weights)
DEFAULT_WEIGHTS = {
    "carbon": 0.4,
    "latency": 0.3,
    "resources": 0.3
}

# API Keys
# Set via environment variable, never hardcode a real token here.
# Copy .env.example to .env and fill in your own key, or export
# ELECTRICITY_MAPS_TOKEN directly in your shell.
ELECTRICITY_MAPS_TOKEN = os.environ.get("ELECTRICITY_MAPS_TOKEN", "")
DEFAULT_TIMESTAMP = "2026-03-31T03:10:00Z"

# Values for random generation
RANDOM_GEN_PARAMS = {
    "carbon": (100, 900),
    "latency": (20, 350),
    "resources": (30, 100),
    "count": 10
}

# Embodied (Scope 3 / manufacturing) carbon — see guide sec 4.2 (Gupta et al. 2022)
EMBODIED_CO2_PER_SERVER_YEAR_KG = 1000
HOURS_PER_YEAR = 8760
EMBODIED_CO2_PER_HOUR_KG = EMBODIED_CO2_PER_SERVER_YEAR_KG / HOURS_PER_YEAR  # ~0.114 kg/hr

# Elastic scaling thresholds (CarbonScaler-style, guide sec 4.3)
ELASTIC_CI_THRESHOLD_LOW = 200   # gCO2/kWh — scale up below this
ELASTIC_CI_THRESHOLD_HIGH = 500  # gCO2/kWh — scale down above this
ELASTIC_MIN_VCORES = 1
ELASTIC_MAX_VCORES = 64

# Joint spatial + temporal shifting (delay-tolerant workloads)
JOINT_SHIFT_REGION_POOL = [
    {"name": "EU-North-2 (Norway)",     "carbon": 15,  "latency": 140, "resources": 92, "lat": 60.47, "lng": 8.47},
    {"name": "EU-North (Sweden)",       "carbon": 40,  "latency": 130, "resources": 90, "lat": 60.13, "lng": 18.64},
    {"name": "EU-West (Ireland)",       "carbon": 230, "latency": 85,  "resources": 95, "lat": 53.0,  "lng": -8.0},
    {"name": "US-East (Virginia)",      "carbon": 380, "latency": 120, "resources": 80, "lat": 38.13, "lng": -78.45},
    {"name": "Asia-Pacific (Singapore)", "carbon": 450, "latency": 175, "resources": 75, "lat": 1.35, "lng": 103.82},
    {"name": "India (Mumbai)",          "carbon": 710, "latency": 190, "resources": 65, "lat": 19.07, "lng": 72.87},
]
# Latency/resources above are illustrative placeholders (not specified by the
# carbon-intensity source) — only `carbon` is the value to treat as authoritative.

# S(r) = w1*C_norm + w2*L_norm + w3*P_norm
JOINT_SHIFT_WEIGHTS = {"w1": 0.6, "w2": 0.25, "w3": 0.15}

LOOKAHEAD_HOURS = 4
STEP_MINUTES = 15

# Formatting & Output
DECIMAL_PLACES = 3
CONSOLE_WIDTH = 80
DEBUG_MODE = True  # Toggle to show normalized values in the scoring table

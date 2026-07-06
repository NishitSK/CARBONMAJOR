import math
import os
import random
from typing import List, Optional

import torch
import torch.nn as nn

import config

WINDOW_HOURS = 24       # input sequence length
FORECAST_HOURS = 6      # output horizon
FEATURES = 3            # [ci_norm, hour_sin, hour_cos]
MODELS_DIR = os.path.join(config.BASE_DIR, "models")


class CarbonLSTM(nn.Module):
    def __init__(self, input_size: int = FEATURES, hidden_size: int = 32, num_layers: int = 2, output_size: int = FORECAST_HOURS):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


def _hour_features(hour_of_day: int):
    angle = 2 * math.pi * hour_of_day / 24
    return math.sin(angle), math.cos(angle)


def build_training_series_from_real(real_history: List[dict], days: int = 45, seed: Optional[int] = None) -> List[float]:
    """
    Electricity Maps' free tier only returns the last 24h of history, which
    is far too short to train an LSTM. We extract the real hourly diurnal
    shape from those 24 points and replay it across `days` with day-to-day
    noise and a slow drift, producing a long-enough series anchored in real
    observed data rather than a fully synthetic curve.
    """
    rng = random.Random(seed)
    hourly_profile = {}
    for entry in real_history:
        dt = entry.get("datetime", "")
        try:
            hour = int(dt[11:13])
        except (ValueError, IndexError):
            continue
        hourly_profile[hour] = entry.get("carbonIntensity", 0)

    if not hourly_profile:
        return []

    avg = sum(hourly_profile.values()) / len(hourly_profile)
    series = []
    for day in range(days):
        drift = 1.0 + 0.02 * math.sin(day / 7.0)  # slow weekly-ish drift
        for hour in range(24):
            base = hourly_profile.get(hour, avg)
            noise = rng.uniform(-0.06, 0.06)
            series.append(round(max(1.0, base * drift * (1 + noise)), 2))
    return series


def series_from_real_history(real_history: List[dict]) -> List[float]:
    """
    Use a real history series directly, sorted chronologically, with no
    extrapolation. Appropriate once there's enough real coverage (a full
    year, in this project's case) that the model can learn real seasonal
    and weekly structure instead of a single replayed diurnal profile.
    """
    sorted_history = sorted(real_history, key=lambda e: e.get("datetime", ""))
    return [round(float(e.get("carbonIntensity", 0)), 2) for e in sorted_history]


def _normalize(series: List[float]):
    lo, hi = min(series), max(series)
    if hi == lo:
        hi = lo + 1.0
    return lo, hi


def _windows(series: List[float], lo: float, hi: float):
    X, y = [], []
    n = len(series)
    for start in range(0, n - WINDOW_HOURS - FORECAST_HOURS):
        window = series[start:start + WINDOW_HOURS]
        target = series[start + WINDOW_HOURS:start + WINDOW_HOURS + FORECAST_HOURS]
        seq = []
        for i, val in enumerate(window):
            hour_of_day = (start + i) % 24
            s, c = _hour_features(hour_of_day)
            seq.append([(val - lo) / (hi - lo), s, c])
        X.append(seq)
        y.append([(v - lo) / (hi - lo) for v in target])
    return torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)


def train_zone(zone: str, series: List[float], epochs: int = 60, lr: float = 0.01) -> dict:
    lo, hi = _normalize(series)
    X, y = _windows(series, lo, hi)
    if len(X) < 4:
        raise ValueError(f"Not enough data points to train ({len(series)} hours)")

    model = CarbonLSTM()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    model.train()
    for _ in range(epochs):
        optimizer.zero_grad()
        pred = model(X)
        loss = loss_fn(pred, y)
        loss.backward()
        optimizer.step()

    os.makedirs(MODELS_DIR, exist_ok=True)
    out_path = os.path.join(MODELS_DIR, f"lstm_{zone}.pt")
    torch.save({"state_dict": model.state_dict(), "lo": lo, "hi": hi}, out_path)
    return {"zone": zone, "final_loss": loss.item(), "path": out_path, "training_hours": len(series)}


_loaded_models = {}


def load_model(zone: str):
    if zone in _loaded_models:
        return _loaded_models[zone]
    path = os.path.join(MODELS_DIR, f"lstm_{zone}.pt")
    if not os.path.exists(path):
        return None
    checkpoint = torch.load(path, weights_only=False)
    model = CarbonLSTM()
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    bundle = {"model": model, "lo": checkpoint["lo"], "hi": checkpoint["hi"]}
    _loaded_models[zone] = bundle
    return bundle


def predict(zone: str, recent_window: List[float], start_hour_of_day: int = 0) -> Optional[List[float]]:
    """Forecast the next FORECAST_HOURS using the trained LSTM for `zone`.
    `recent_window` must have WINDOW_HOURS most-recent CI values."""
    bundle = load_model(zone)
    if bundle is None or len(recent_window) < WINDOW_HOURS:
        return None

    model, lo, hi = bundle["model"], bundle["lo"], bundle["hi"]
    window = recent_window[-WINDOW_HOURS:]
    seq = []
    for i, val in enumerate(window):
        hour_of_day = (start_hour_of_day + i) % 24
        s, c = _hour_features(hour_of_day)
        seq.append([(val - lo) / (hi - lo), s, c])

    with torch.no_grad():
        x = torch.tensor([seq], dtype=torch.float32)
        out = model(x)[0].tolist()
    return [round(max(0.0, v * (hi - lo) + lo), 2) for v in out]

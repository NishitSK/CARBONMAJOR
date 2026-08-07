import random
from typing import List, Dict
from statsmodels.tsa.arima.model import ARIMA


def generate_synthetic_history(base_ci: float, hours: int = 48, seed: int = None) -> List[float]:
    """
    Builds a synthetic hourly carbon-intensity series with a diurnal solar/wind
    cycle plus noise, anchored around a region's known average CI.
    Stand-in for real Electricity Maps history (guide sec 10.1) when no API
    key / historical archive is available.
    """
    rng = random.Random(seed)
    series = []
    for h in range(hours):
        # Diurnal swing: cleaner mid-day (solar), dirtier at night (~±25%)
        diurnal = -0.25 * base_ci * (1 + (((h % 24) - 13) / 13) ** 2) ** -1 + 0.25 * base_ci
        noise = rng.uniform(-0.05, 0.05) * base_ci
        value = max(10.0, base_ci + diurnal * 0.3 + noise)
        series.append(round(value, 2))
    return series


def fit_arima(ci_series: List[float]):
    """Fit ARIMA(2,1,2) to a carbon-intensity time series."""
    model = ARIMA(ci_series, order=(2, 1, 2))
    return model.fit()


def forecast_next_hours(ci_series: List[float], n_hours: int = 6) -> List[float]:
    """Fit + forecast in one call. Falls back to a flat persistence forecast
    if ARIMA fails to converge on a short/degenerate series."""
    try:
        result = fit_arima(ci_series)
        forecast = result.forecast(steps=n_hours)
        return [round(max(0.0, v), 2) for v in forecast.tolist()]
    except Exception:
        last = ci_series[-1] if ci_series else 0.0
        return [round(last, 2)] * n_hours


def forecast_quarter_hour_window(base_ci: float, hours: int = 4, seed: int = None) -> List[float]:
    """
    Carbon-intensity forecast at 15-minute resolution over the next `hours`.

    Electricity Maps (and the ARIMA/LSTM models trained on it elsewhere in
    this codebase) only operate at hourly resolution, so this takes `hours`
    hourly forecasts and linearly interpolates between them rather than
    fabricating independent quarter-hour data. Returns hours*4 points;
    point i corresponds to t + 15*(i+1) minutes from now.
    """
    history = generate_synthetic_history(base_ci, hours=24, seed=seed)
    hourly_forecast = forecast_next_hours(history, n_hours=hours)
    anchors = [history[-1]] + hourly_forecast  # t0, t+1h, ..., t+hours h

    points = []
    for h in range(hours):
        start, end = anchors[h], anchors[h + 1]
        for step in range(1, 5):
            frac = step / 4
            points.append(round(start + (end - start) * frac, 2))
    return points


def forecast_real_hours(real_series: List[float], n_hours: int = 4, lstm_predict_fn=None) -> List[float]:
    """
    Real-data analogue of forecast_next_hours(): adaptive-horizon forecast
    matching this paper's own documented crossover (Section V-C) -- ARIMA
    wins at the 6-hour horizon, LSTM wins at 24 hours. `real_series` must
    already be causally trimmed by the caller (no data at or after the
    point being forecast). For n_hours<=6, or when no LSTM path is
    supplied, fits ARIMA fresh on `real_series` via forecast_next_hours().
    For longer horizons, delegates to `lstm_predict_fn(real_series,
    n_hours)`, a caller-supplied callable, since the LSTM path needs a
    per-zone trained held-out model rather than a fit-per-call model like
    ARIMA. Callers doing many repeated calls (e.g. a backtest) should
    prefer a monthly-refit + .apply(refit=False) pattern instead of calling
    this directly, for the same reason forecast_next_hours() is too slow
    to call at scale -- see scripts/forecast_in_the_loop_replay.py.
    """
    if n_hours <= 6 or lstm_predict_fn is None:
        return forecast_next_hours(real_series, n_hours=n_hours)
    return list(lstm_predict_fn(real_series, n_hours))[:n_hours]


def forecast_quarter_hour_window_real(real_series: List[float], hours: int = 4, lstm_predict_fn=None) -> List[float]:
    """
    Real-data analogue of forecast_quarter_hour_window(): the same
    quarter-hour linear interpolation, but forecasting forward from real
    historical CI via forecast_real_hours() instead of a synthetic diurnal
    curve. `real_series` is real data ending at the current decision time
    (the last point is "now"); the forecast covers hours 1..`hours` ahead.
    """
    hourly_forecast = forecast_real_hours(real_series, n_hours=hours, lstm_predict_fn=lstm_predict_fn)
    anchors = [real_series[-1]] + hourly_forecast

    points = []
    for h in range(hours):
        start, end = anchors[h], anchors[h + 1]
        for step in range(1, 5):
            frac = step / 4
            points.append(round(start + (end - start) * frac, 2))
    return points


def find_optimal_shift_window(ci_series: List[float], max_delay_hours: int = 6, deadline_hours: int = 8) -> Dict:
    """
    For a delay-tolerant workload: forecast the next window and find the
    start offset (hours from now) with the lowest predicted carbon intensity,
    subject to completing within the deadline (guide sec 10.4).
    """
    horizon = max(1, min(max_delay_hours, deadline_hours))
    forecasts = forecast_next_hours(ci_series, n_hours=horizon)
    best_offset = min(range(len(forecasts)), key=lambda i: forecasts[i])
    return {
        "forecast": forecasts,
        "best_offset_hours": best_offset,
        "best_forecast_ci": forecasts[best_offset]
    }

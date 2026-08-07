"""
Real-data-driven temporal-shift forecaster - a verified-equivalent extraction
of the exact logic already validated in scripts/temporal_shift_benchmark.py
(results: data/temporal_shift_benchmark.json), restructured for live/production
use rather than backtest-index bookkeeping.

That benchmark proved a real ARIMA(<=6h)/LSTM(up to 24h) forecast, built from
real trailing history and applied FORWARD from "now", measurably beats both
"no shift" and the synthetic-diurnal stand-in currently used inside
Scheduler.schedule_delay_tolerant() (see forecaster.forecast_quarter_hour_window(),
which forecasts on a FABRICATED series via generate_synthetic_history()):

  4h deadline (system default):  real AI +2.62% vs no-shift; current synthetic
                                  behavior is -0.77% (WORSE than not shifting).
                                  Incremental value of real AI: +3.39 pp.
  24h deadline:                  real AI +8.40% vs no-shift; synthetic -0.75%.
                                  Incremental value: +9.15 pp, capturing half
                                  of the achievable no-shift-to-oracle gap.

Forward-looking design (NOT the same causal rule as forecast_in_the_loop_replay.py):
a temporal-shift decision made "now" legitimately has real-time access to all
real data up to and including now, and forecasts the FUTURE from that point -
unlike the spatial audit in forecast_in_the_loop_replay.py, which deliberately
tests decisions forced onto a forecast that was already stale by the horizon.
Conflating the two designs would invalidate the comparison to the validated
benchmark above.

This module must stay behaviorally identical to temporal_shift_benchmark.py's
arima_forward_forecast()/lstm_forward_forecast() (same fallback conditions,
same 2-decimal rounding, same clip-at-zero) - any future edit here should be
re-validated against that script before being trusted with a live deployment.
See scripts/verify_real_temporal_forecaster.py for the equivalence check.

NOT yet wired into Scheduler.schedule_delay_tolerant(). This is the
production-ready candidate for that wiring, once a live deployment is
approved and the equivalence check has been run.
"""
from typing import List, Optional, Tuple

from services import lstm_forecaster

ARIMA_MAX_HORIZON_HOURS = 6  # matches the paper's own 6h-horizon ARIMA-wins finding


def forecast_arima_forward(prefitted_model, real_trailing_window: List[float],
                            hours: int) -> Tuple[List[float], bool]:
    """
    Forecasts `hours` FORWARD from "now" (the end of real_trailing_window),
    applying a pre-fitted ARIMAResults' PARAMETERS to the given real trailing
    window via .apply(refit=False) - cheap, no re-estimation. Exactly mirrors
    temporal_shift_benchmark.py's arima_forward_forecast(). Returns
    (forecast_list, fell_back_to_persistence).
    """
    if prefitted_model is None or len(real_trailing_window) < 2:
        last = real_trailing_window[-1] if real_trailing_window else 0.0
        return [last] * hours, True
    try:
        applied = prefitted_model.apply(real_trailing_window, refit=False)
        forecast = applied.forecast(steps=hours)
        return [max(0.0, round(float(v), 2)) for v in forecast], False
    except Exception:
        return [real_trailing_window[-1]] * hours, True


def forecast_lstm_forward(lstm_bundle: dict, real_trailing_24h: List[float],
                           window_start_hour_of_day: int, hours: int) -> Tuple[List[float], bool]:
    """
    Forecasts up to 24h FORWARD from "now" (the end of real_trailing_24h),
    using an already-loaded LSTM bundle ({"model", "lo", "hi"}). Exactly
    mirrors temporal_shift_benchmark.py's lstm_forward_forecast(). Returns
    (forecast_list, fell_back_to_persistence).

    IMPORTANT: `window_start_hour_of_day` is the hour-of-day (0-23) of the
    FIRST element of real_trailing_24h (i.e. "now" minus 23 hours), NOT the
    hour-of-day of "now" itself - the model was trained on hour-of-day
    features indexed from the start of each input window. Passing the hour
    of "now" instead silently shifts every prediction by up to 23 hours of
    diurnal phase and was caught exactly this way by
    scripts/verify_real_temporal_forecaster.py during initial validation.
    """
    if len(real_trailing_24h) < lstm_forecaster.WINDOW_HOURS:
        last = real_trailing_24h[-1] if real_trailing_24h else 0.0
        return [last] * hours, True

    import torch

    model, lo, hi = lstm_bundle["model"], lstm_bundle["lo"], lstm_bundle["hi"]
    window = real_trailing_24h[-lstm_forecaster.WINDOW_HOURS:]
    seq = []
    for i, val in enumerate(window):
        h = (window_start_hour_of_day + i) % 24
        s, c = lstm_forecaster._hour_features(h)
        seq.append([(val - lo) / (hi - lo), s, c])
    with torch.no_grad():
        x = torch.tensor([seq], dtype=torch.float32)
        out = model(x)[0].tolist()
    preds = [max(0.0, v * (hi - lo) + lo) for v in out]
    return preds[:hours], False


def forecast_adaptive_forward(real_trailing_history: List[float], hours: int,
                               prefitted_arima=None, lstm_bundle: Optional[dict] = None,
                               window_start_hour_of_day: int = 0) -> Tuple[List[float], str]:
    """
    Adaptive horizon selector, forward-looking: ARIMA for
    hours <= ARIMA_MAX_HORIZON_HOURS, LSTM for longer horizons (falls back to
    ARIMA if no LSTM bundle is supplied for a long-horizon call). Returns
    (forecast_list, "arima"|"lstm"). See forecast_lstm_forward's docstring for
    the meaning of window_start_hour_of_day - it is NOT the hour of "now".
    """
    if hours <= ARIMA_MAX_HORIZON_HOURS or lstm_bundle is None:
        forecast, _ = forecast_arima_forward(prefitted_arima, real_trailing_history, hours)
        return forecast, "arima"
    forecast, _ = forecast_lstm_forward(lstm_bundle, real_trailing_history, window_start_hour_of_day, hours)
    return forecast, "lstm"

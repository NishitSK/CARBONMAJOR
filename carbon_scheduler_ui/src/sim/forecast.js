// Simulated forward forecast for a region, standing in for the real
// CarbonLSTM / ARIMA(2,1,2) pipeline (services/lstm_forecaster.py,
// services/forecaster.py) without needing torch/statsmodels in the browser.
// Deliberately reproduces the *shape* of the real pilot's verified accuracy
// (data/forecast_verification.jsonl): LSTM tracks the true curve closely,
// ARIMA is noisy/biased — so the forecasting page and the audit's no-regret
// guard behave the way the live system actually does.
import { mulberry32, hashSeed } from './rng';
import { carbonAtHour } from './carbonModel';

export function trueForwardSeries(region, fromHour, hours, dayIndex = 0) {
  const out = [];
  for (let i = 1; i <= hours; i++) {
    const h = (fromHour + i) % 24;
    const d = dayIndex + Math.floor((fromHour + i) / 24);
    out.push(carbonAtHour(region, h, d));
  }
  return out;
}

// model: 'lstm' | 'arima'
export function forecastSeries(region, fromHour, hours, model = 'lstm', dayIndex = 0) {
  const truth = trueForwardSeries(region, fromHour, hours, dayIndex);
  const rng = mulberry32(hashSeed(region.name + model + fromHour) + dayIndex * 131);
  return truth.map((v, i) => {
    if (model === 'lstm') {
      // Tight noise, no systematic bias -> ~well-calibrated, matches the
      // pilot's verified ~70% directional accuracy / ~17% regret.
      const noise = 1 + (rng() - 0.5) * 0.1 * (1 + i * 0.02);
      return Math.max(5, v * noise);
    }
    // ARIMA: larger noise + a persistence bias toward the origin value ->
    // matches the pilot's verified ~coin-flip directional accuracy.
    const origin = truth[0];
    const persistence = origin * 0.35 + v * 0.65;
    const noise = 1 + (rng() - 0.5) * 0.32 * (1 + i * 0.05);
    return Math.max(5, persistence * noise);
  });
}

// No-regret guard: only recommend delaying if predicted saving clears the
// model-specific threshold earned from ground-truth verification (mirrors
// services/failsafe_engine.py::apply_no_regret_guard and the calibrated
// thresholds in data/forecast_calibration.json).
const GUARD_THRESHOLD_PCT = { lstm: 15, arima: 1000 }; // ARIMA effectively disabled, same as the live pilot

export function bestDelayedHour(region, fromHour, maxHours, model = 'lstm', dayIndex = 0) {
  const currentCi = carbonAtHour(region, fromHour, dayIndex);
  const preds = forecastSeries(region, fromHour, maxHours, model, dayIndex);
  let bestIdx = -1;
  let bestCi = currentCi;
  preds.forEach((p, i) => {
    if (p < bestCi) {
      bestCi = p;
      bestIdx = i;
    }
  });
  if (bestIdx === -1) return { offsetHours: 0, predictedCi: currentCi, savingsPct: 0, guardPassed: false };

  const savingsPct = ((currentCi - bestCi) / currentCi) * 100;
  const threshold = GUARD_THRESHOLD_PCT[model] ?? 15;
  const guardPassed = savingsPct >= threshold;
  return {
    offsetHours: guardPassed ? bestIdx + 1 : 0,
    predictedCi: guardPassed ? bestCi : currentCi,
    savingsPct: guardPassed ? savingsPct : 0,
    guardPassed,
  };
}

// Ground-truth-style verification table, numerically consistent with the
// real pilot (LSTM ~70% directional / ~17% regret, ARIMA ~50% / ~33%) —
// used by the simulated Forecasting page's accuracy card.
export function verificationMetrics() {
  return {
    metrics: {
      CarbonLSTM: {
        '1h': { sample_count: 638, mae_gco2: 40.3, directional_accuracy_pct: 68.0, regret_rate_pct: 16.5 },
        '3h': { sample_count: 658, mae_gco2: 42.5, directional_accuracy_pct: 71.5, regret_rate_pct: 17.2 },
        '6h': { sample_count: 687, mae_gco2: 47.7, directional_accuracy_pct: 72.4, regret_rate_pct: 18.1 },
        '12h': { sample_count: 707, mae_gco2: 50.1, directional_accuracy_pct: 71.9, regret_rate_pct: 19.4 },
      },
      'ARIMA(2,1,2)': {
        '1h': { sample_count: 628, mae_gco2: 46.0, directional_accuracy_pct: 48.1, regret_rate_pct: 30.3 },
        '3h': { sample_count: 647, mae_gco2: 79.1, directional_accuracy_pct: 45.0, regret_rate_pct: 36.6 },
        '6h': { sample_count: 678, mae_gco2: 80.1, directional_accuracy_pct: 51.9, regret_rate_pct: 34.4 },
        '12h': { sample_count: 678, mae_gco2: 89.4, directional_accuracy_pct: 53.2, regret_rate_pct: 32.2 },
      },
    },
    pending_count: 41,
  };
}

import React, { useState, useEffect } from 'react';
import TopNavbar from '../components/layout/TopNavbar';

// Every horizon side by side, so choosing 3h / 6h / 12h never looks like a
// page that failed to update. When all three agree, it says why.
function HorizonStrip({ stages, selected }) {
  const horizons = ['3h', '6h', '12h'];
  if (!stages || !stages['3h']) return null;
  const rows = horizons.map((h) => ({ h, s: stages[h] || {} }));
  const decisions = rows.map(({ s }) => `${s.optimal_offset}|${s.best_future_offset}|${Math.round(s.best_future_ci || 0)}`);
  const allSame = new Set(decisions).size === 1;
  const first = rows[0].s;

  return (
    <div style={{ marginTop: '1rem', paddingTop: '0.85rem', borderTop: '1px solid var(--border)' }}>
      <div style={{ fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: '0.5rem' }}>
        Across horizons
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '0.5rem' }}>
        {rows.map(({ h, s }) => {
          const change = s.best_future_change_pct;
          const cleaner = typeof change === 'number' && change < 0;
          return (
            <div
              key={h}
              style={{
                padding: '0.55rem 0.65rem',
                borderRadius: 'var(--radius-sm)',
                background: h === selected ? 'var(--primary-subtle)' : 'var(--bg-subtle)',
                border: `1px solid ${h === selected ? 'var(--primary)' : 'var(--border)'}`,
                minWidth: 0,
              }}
            >
              <div className="mono" style={{ fontSize: '0.75rem', fontWeight: 700 }}>{h}</div>
              <div style={{ fontSize: '0.82rem', fontWeight: 600, marginTop: '0.15rem' }}>
                {s.optimal_offset > 0 ? `Delay ${s.optimal_offset}h` : s.guard_held ? 'Run now (held)' : 'Run now'}
              </div>
              <div className="mono" style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
                cleanest T+{s.best_future_offset}h · {Math.round(s.best_future_ci || 0)} g
              </div>
              {typeof change === 'number' && (
                <div className="mono" style={{ fontSize: '0.72rem', color: cleaner ? 'var(--clean)' : 'var(--dirty)' }}>
                  {cleaner ? `${Math.abs(change)}% cleaner` : `${change}% dirtier`}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {allSame && (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.55rem', lineHeight: 1.5 }}>
          Same answer at every horizon: the cleanest forecast hour is T+{first.best_future_offset}h, inside the shortest
          window, so looking 6 or 12 hours ahead finds nothing better.
        </p>
      )}
    </div>
  );
}

export default function ForecastingPage() {
  const [forecastData, setForecastData] = useState({});
  const [regionList, setRegionList] = useState([]);
  const [selectedRegion, setSelectedRegion] = useState('ap-south-1 (Mumbai)');
  const [selectedHorizon, setSelectedHorizon] = useState('6h');
  const [loading, setLoading] = useState(true);
  const [regionLoading, setRegionLoading] = useState(false);
  const [verification, setVerification] = useState(null);

  // The full multi-region forecast takes ~10s (an LSTM run per region), so the
  // region list comes from the fast /regions/ endpoint, the selected region is
  // fetched on its own, and the rest streams in behind it.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch('http://127.0.0.1:8001/regions/');
        if (res.ok) {
          const data = await res.json();
          const names = (Array.isArray(data) ? data : []).map((r) => r.name).filter(Boolean);
          if (!cancelled && names.length) {
            setRegionList(names);
            if (!names.includes(selectedRegion)) setSelectedRegion(names[0]);
          }
        }
      } catch (e) { /* offline: fall back to forecast keys */ }
      if (!cancelled) {
        await fetchForecastFor(selectedRegion);
        fetchForecasts();
      }
    })();
    fetchVerification();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (selectedRegion && !forecastData[selectedRegion]) fetchForecastFor(selectedRegion);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRegion]);

  const fetchForecastFor = async (name) => {
    if (!name) return;
    setRegionLoading(true);
    try {
      const res = await fetch(`http://127.0.0.1:8001/forecasting/multi-stage?region_name=${encodeURIComponent(name)}`);
      if (res.ok) {
        const data = await res.json();
        if (data && Object.keys(data).length) setForecastData((prev) => ({ ...prev, ...data }));
      }
    } catch (e) { /* keep reference values */ } finally {
      setRegionLoading(false);
      setLoading(false);
    }
  };

  const fetchVerification = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8001/forecasting/verification');
      if (res.ok) setVerification(await res.json());
    } catch (e) {
      console.error('Failed to load verification', e);
    }
  };

  const fetchForecasts = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8001/forecasting/multi-stage');
      if (res.ok) {
        const data = await res.json();
        setForecastData(data);
        const keys = Object.keys(data);
        if (keys.length > 0 && !data[selectedRegion]) {
          setSelectedRegion(keys[0]);
        }
      }
    } catch (e) {
      console.error("Failed to load forecasting", e);
    } finally {
      setLoading(false);
    }
  };

  const regionNames = regionList.length > 0 ? regionList : Object.keys(forecastData);
  // No invented numbers: until this region's forecast arrives, the page shows
  // an empty state rather than placeholder values that read as real data.
  const hasForecast = !!forecastData[selectedRegion];
  const activeRegionData = forecastData[selectedRegion] || {
    zone: null,
    current_ci: null,
    arima_forecast_12h: [],
    lstm_forecast_12h: [],
    arima_stages: {},
    lstm_stages: {},
  };

  const horizonSteps = selectedHorizon === '3h' ? 3 : selectedHorizon === '6h' ? 6 : 12;
  const arimaSeries = (activeRegionData.arima_forecast_12h || []).slice(0, horizonSteps);
  const lstmSeries = (activeRegionData.lstm_forecast_12h || []).slice(0, horizonSteps);

  const arimaStage = (activeRegionData.arima_stages && activeRegionData.arima_stages[selectedHorizon]) || { optimal_offset: 0, predicted_ci: activeRegionData.current_ci, savings_pct: 0 };
  const lstmStage = (activeRegionData.lstm_stages && activeRegionData.lstm_stages[selectedHorizon]) || { optimal_offset: 0, predicted_ci: activeRegionData.current_ci, savings_pct: 0 };

  // Ground-truth accuracy rows (flatten metrics: model -> horizon -> stats)
  const HZ_ORDER = ['1h', '3h', '6h', '12h'];
  const vMetrics = (verification && verification.metrics) || {};
  const accRows = [];
  Object.keys(vMetrics).sort().forEach((model) => {
    HZ_ORDER.forEach((hz) => {
      const v = vMetrics[model] && vMetrics[model][hz];
      if (v) accRows.push({ model, hz, ...v });
    });
  });

  return (
    <div className="app-layout">
      <TopNavbar />

      <main className="main-content">
        <div className="page-header">
          <h1 className="page-title">Temporal Forecasting & Multi-Horizon Engine</h1>
          <p className="page-subtitle">
            Comparative 3-stage lookahead analysis: Neural LSTM vs Statistical ARIMA(2,1,2), each decision passed through
            the no-regret guard. Values come from the backend's model output, so they differ from the Placement Audit's
            simulated grid.
          </p>
        </div>

        {!hasForecast && (
          <div className="card" style={{ borderColor: 'var(--moderate-border)', background: 'var(--moderate-bg)', padding: '1rem 1.5rem' }}>
            <strong style={{ color: 'var(--moderate)' }}>
              {regionLoading ? `Loading forecast for ${selectedRegion}\u2026` : `No forecast available for ${selectedRegion}.`}
            </strong>{' '}
            <span style={{ color: 'var(--text-muted)' }}>
              {regionLoading
                ? 'Each region is forecast by its own model run, which takes a few seconds.'
                : 'Start the backend on port 8001 to load forecasts. No placeholder numbers are shown here.'}
            </span>
          </div>
        )}

        {/* 3-Stage Horizon Selector Ribbon */}
        <div id="tour-horizon-stages" className="card" style={{ padding: '1.5rem 2rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1.5rem' }}>
            <div>
              <span style={{ fontSize: '0.85rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-faint)' }}>
                Select Active Lookahead Stage:
              </span>
              <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.6rem', flexWrap: 'wrap' }}>
                {[
                  { id: '3h', title: 'Stage 1: 3-Hour Horizon', subtitle: 'Tight Deadline / CI-CD' },
                  { id: '6h', title: 'Stage 2: 6-Hour Horizon', subtitle: 'Standard Pilot Batch' },
                  { id: '12h', title: 'Stage 3: 12-Hour Horizon', subtitle: 'Deep Diurnal Cycle' }
                ].map(h => (
                  <button
                    key={h.id}
                    className={`btn ${selectedHorizon === h.id ? 'btn-primary' : 'btn-outline'}`}
                    style={{ textAlign: 'left', padding: '0.75rem 1.25rem' }}
                    onClick={() => setSelectedHorizon(h.id)}
                  >
                    <div style={{ fontWeight: 700, fontSize: '1rem' }}>{h.title}</div>
                    <div style={{ fontSize: '0.8rem', color: selectedHorizon === h.id ? 'rgba(255,255,255,0.85)' : 'var(--text-muted)' }}>{h.subtitle}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Region Dropdown */}
            <div>
              <label style={{ fontSize: '0.85rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-faint)', display: 'block', marginBottom: '0.6rem' }}>
                Target Region: {regionLoading && <span style={{ textTransform: 'none', color: 'var(--primary)', fontWeight: 600 }}>loading forecast…</span>}
              </label>
              <select
                value={selectedRegion}
                onChange={(e) => setSelectedRegion(e.target.value)}
                style={{
                  background: 'var(--surface-card)',
                  color: 'var(--text-main)',
                  border: '1px solid var(--border-light)',
                  padding: '0.75rem 1.25rem',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '1rem',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                {regionNames.length > 0 ? regionNames.map(r => (
                  <option key={r} value={r}>{r}</option>
                )) : (
                  <option value="ap-south-1 (Mumbai)">ap-south-1 (Mumbai)</option>
                )}
              </select>
            </div>
          </div>
        </div>

        {/* Dual Model KPI Comparison */}
        <div id="tour-model-compare" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '1.5rem', marginBottom: '2.5rem' }}>
          {/* Neural LSTM Card */}
          <div className="card" style={{ borderColor: 'var(--primary-subtle)' }}>
            <div className="card-header">
              <div>
                <span className="jurisdiction-badge" style={{ color: 'var(--primary)', borderColor: 'var(--primary-subtle)' }}>Deep Neural Model</span>
                <h3 className="card-title">PyTorch CarbonLSTM</h3>
              </div>
              <span className="badge-clean" style={{ fontSize: '0.9rem' }}>Lookahead: {selectedHorizon}</span>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.25rem' }}>
              <div style={{ background: 'var(--bg-subtle)', padding: '1.1rem 1.25rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-faint)' }}>MODEL'S CLEANEST HOUR</div>
                <div className="kpi-val mono" style={{ fontSize: '1.6rem', marginTop: '0.25rem' }}>T+{lstmStage.best_future_offset ?? lstmStage.optimal_offset}h</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                  best hour it forecasts in the next {selectedHorizon}
                </div>
              </div>
              <div style={{ background: 'var(--bg-subtle)', padding: '1.1rem 1.25rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-faint)' }}>FORECAST AT THAT HOUR</div>
                <div className="kpi-val mono" style={{ fontSize: '1.6rem', color: (lstmStage.best_future_change_pct ?? 0) < 0 ? 'var(--clean)' : 'var(--dirty)', marginTop: '0.25rem' }}>{(lstmStage.best_future_ci ?? lstmStage.predicted_ci)?.toFixed(1)} g</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                  vs {activeRegionData.current_ci?.toFixed(1)} now
                  {typeof lstmStage.best_future_change_pct === 'number' && (
                    <> · {lstmStage.best_future_change_pct < 0 ? `${Math.abs(lstmStage.best_future_change_pct)}% cleaner` : `${lstmStage.best_future_change_pct}% dirtier`}</>
                  )}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '1rem', flexWrap: 'wrap', padding: '0.85rem 0 0', borderTop: '1px solid var(--border)' }}>
              <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>Decision after the no-regret guard:</span>
              <span className="mono" style={{ fontSize: '1.2rem', fontWeight: 800, color: lstmStage.optimal_offset > 0 ? 'var(--clean)' : 'var(--text-main)' }}>
                {lstmStage.optimal_offset > 0 ? `delay ${lstmStage.optimal_offset}h (+${lstmStage.savings_pct?.toFixed(1)}%)` : 'run now'}
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.4rem', lineHeight: 1.5 }}>
              {lstmStage.optimal_offset > 0
                ? `Approved: the forecast saving clears this model's earned threshold of ${lstmStage.guard_threshold_pct}%.`
                : lstmStage.guard_held
                  ? `Held: the model wanted T+${lstmStage.model_proposed_offset}h for +${lstmStage.model_proposed_savings_pct?.toFixed(1)}%, below its earned threshold of ${lstmStage.guard_threshold_pct >= 1000 ? 'always hold' : `${lstmStage.guard_threshold_pct}%`}.`
                  : 'No hour in this window is forecast to be cleaner than now.'}
            </p>

            <HorizonStrip stages={activeRegionData.lstm_stages} selected={selectedHorizon} />
          </div>

          {/* Statistical ARIMA Card */}
          <div className="card" style={{ borderColor: 'var(--clean-border)' }}>
            <div className="card-header">
              <div>
                <span className="jurisdiction-badge" style={{ color: 'var(--clean)', borderColor: 'var(--clean-border)' }}>Statistical Time-Series</span>
                <h3 className="card-title">Statsmodels ARIMA(2,1,2)</h3>
              </div>
              <span className="badge-clean" style={{ fontSize: '0.9rem' }}>Lookahead: {selectedHorizon}</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.25rem' }}>
              <div style={{ background: 'var(--bg-subtle)', padding: '1.1rem 1.25rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-faint)' }}>MODEL'S CLEANEST HOUR</div>
                <div className="kpi-val mono" style={{ fontSize: '1.6rem', marginTop: '0.25rem' }}>T+{arimaStage.best_future_offset ?? arimaStage.optimal_offset}h</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                  best hour it forecasts in the next {selectedHorizon}
                </div>
              </div>
              <div style={{ background: 'var(--bg-subtle)', padding: '1.1rem 1.25rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-faint)' }}>FORECAST AT THAT HOUR</div>
                <div className="kpi-val mono" style={{ fontSize: '1.6rem', color: (arimaStage.best_future_change_pct ?? 0) < 0 ? 'var(--clean)' : 'var(--dirty)', marginTop: '0.25rem' }}>{(arimaStage.best_future_ci ?? arimaStage.predicted_ci)?.toFixed(1)} g</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                  vs {activeRegionData.current_ci?.toFixed(1)} now
                  {typeof arimaStage.best_future_change_pct === 'number' && (
                    <> · {arimaStage.best_future_change_pct < 0 ? `${Math.abs(arimaStage.best_future_change_pct)}% cleaner` : `${arimaStage.best_future_change_pct}% dirtier`}</>
                  )}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '1rem', flexWrap: 'wrap', padding: '0.85rem 0 0', borderTop: '1px solid var(--border)' }}>
              <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>Decision after the no-regret guard:</span>
              <span className="mono" style={{ fontSize: '1.2rem', fontWeight: 800, color: arimaStage.optimal_offset > 0 ? 'var(--clean)' : 'var(--text-main)' }}>
                {arimaStage.optimal_offset > 0 ? `delay ${arimaStage.optimal_offset}h (+${arimaStage.savings_pct?.toFixed(1)}%)` : 'run now'}
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.4rem', lineHeight: 1.5 }}>
              {arimaStage.optimal_offset > 0
                ? `Approved: the forecast saving clears this model's earned threshold of ${arimaStage.guard_threshold_pct}%.`
                : arimaStage.guard_held
                  ? `Held: the model wanted T+${arimaStage.model_proposed_offset}h for +${arimaStage.model_proposed_savings_pct?.toFixed(1)}%, below its earned threshold of ${arimaStage.guard_threshold_pct >= 1000 ? 'always hold' : `${arimaStage.guard_threshold_pct}%`}.`
                  : 'No hour in this window is forecast to be cleaner than now.'}
            </p>

            <HorizonStrip stages={activeRegionData.arima_stages} selected={selectedHorizon} />
          </div>
        </div>

        {/* Hourly Forward Trajectory Table */}
        <div className="card" id="tour-forward-table">
          <div className="card-header">
            <div>
              <h2 className="card-title">Forward Trajectory Comparison (Step-by-Step)</h2>
              <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
                Carbon intensity forecast (gCO2/kWh) from T=0 to T+{horizonSteps}h for {selectedRegion} · as of{' '}
                {String(new Date().getUTCHours()).padStart(2, '0')}:00 UTC
                {lstmStage.no_cleaner_hour && arimaStage.no_cleaner_hour && (
                  <strong style={{ color: 'var(--text-main)' }}> — no hour in this window is cleaner than now, so both models say run immediately.</strong>
                )}
              </p>
            </div>
          </div>

          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Horizon Offset</th>
                  <th>Relative Time</th>
                  <th>Neural LSTM Forecast</th>
                  <th>ARIMA(2,1,2) Forecast</th>
                  <th>Current Baseline (t=0)</th>
                  <th>Best Policy Decision</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="mono" style={{ fontSize: '1.05rem' }}><strong>T+0h (Now)</strong></td>
                  <td>Current Hour</td>
                  <td className="mono" style={{ fontSize: '1.05rem' }}>{activeRegionData.current_ci?.toFixed(1)} g</td>
                  <td className="mono" style={{ fontSize: '1.05rem' }}>{activeRegionData.current_ci?.toFixed(1)} g</td>
                  <td className="mono" style={{ fontSize: '1.05rem' }}>{activeRegionData.current_ci?.toFixed(1)} g</td>
                  <td><span style={{ color: 'var(--text-faint)', fontWeight: 600 }}>Baseline Hub</span></td>
                </tr>
                {lstmSeries.map((lstmVal, idx) => {
                  const arimaVal = arimaSeries[idx] || lstmVal;
                  const stepH = idx + 1;
                  const isLstmOpt = (lstmStage.best_future_offset ?? lstmStage.optimal_offset) === stepH;
                  const isArimaOpt = (arimaStage.best_future_offset ?? arimaStage.optimal_offset) === stepH;

                  return (
                    <tr key={stepH} style={{ background: (isLstmOpt || isArimaOpt) ? 'var(--clean-bg)' : undefined }}>
                      <td className="mono" style={{ fontSize: '1.05rem' }}><strong>T+{stepH}h</strong></td>
                      <td>+{stepH} hour{stepH > 1 ? 's' : ''}</td>
                      <td>
                        <span className="mono" style={{ fontWeight: isLstmOpt ? 800 : 500, fontSize: '1.05rem', color: isLstmOpt ? 'var(--clean)' : 'var(--text-main)' }}>
                          {lstmVal.toFixed(1)} g
                        </span>
                        {isLstmOpt && <span className="badge-clean" style={{ marginLeft: '0.6rem', fontSize: '0.8rem' }}>LSTM Optimal</span>}
                      </td>
                      <td>
                        <span className="mono" style={{ fontWeight: isArimaOpt ? 800 : 500, fontSize: '1.05rem', color: isArimaOpt ? 'var(--clean)' : 'var(--text-main)' }}>
                          {arimaVal.toFixed(1)} g
                        </span>
                        {isArimaOpt && <span className="badge-clean" style={{ marginLeft: '0.6rem', fontSize: '0.8rem' }}>ARIMA Optimal</span>}
                      </td>
                      <td className="mono" style={{ color: 'var(--text-faint)', fontSize: '1.05rem' }}>
                        {activeRegionData.current_ci?.toFixed(1)} g
                      </td>
                      <td>
                        {(isLstmOpt || isArimaOpt) ? (
                          <span style={{ color: 'var(--clean)', fontWeight: 700, fontSize: '0.95rem' }}>
                            Cleanest forecast hour
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-faint)', fontSize: '0.9rem' }}>Sub-optimal</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Forecast Accuracy — Ground-Truth Verified */}
        <div className="card" id="tour-accuracy">
          <div className="card-header">
            <div>
              <h2 className="card-title">Forecast Accuracy — Ground-Truth Verified</h2>
              <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
                Every past 1h / 3h / 6h / 12h prediction, once its target hour arrived, checked against the real measured carbon intensity. This is each model's actual track record — not what it predicted about itself.
              </p>
            </div>
            {verification && (
              <span className="jurisdiction-badge">{verification.pending_count} awaiting their target hour</span>
            )}
          </div>

          {accRows.length === 0 ? (
            <p style={{ color: 'var(--text-muted)' }}>
              No verified predictions yet. Forecasts are scored once their horizon elapses — check back after the next few cycles.
            </p>
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>Horizon</th>
                    <th>Verified N</th>
                    <th>Mean Abs. Error</th>
                    <th>Direction Correct</th>
                    <th>Regret Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {accRows.map((r) => (
                    <tr key={r.model + r.hz}>
                      <td style={{ fontWeight: 600 }}>{r.model}</td>
                      <td className="mono">{r.hz}</td>
                      <td className="mono">{r.sample_count}</td>
                      <td className="mono">{r.mae_gco2?.toFixed(1)} g</td>
                      <td className="mono" style={{ color: r.directional_accuracy_pct >= 60 ? 'var(--clean)' : 'var(--text-main)', fontWeight: r.directional_accuracy_pct >= 60 ? 700 : 500 }}>
                        {r.directional_accuracy_pct?.toFixed(1)}%
                      </td>
                      <td className="mono" style={{ color: r.regret_rate_pct <= 25 ? 'var(--clean)' : r.regret_rate_pct <= 35 ? 'var(--moderate)' : 'var(--dirty)', fontWeight: 700 }}>
                        {r.regret_rate_pct?.toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '1rem', lineHeight: 1.6 }}>
            <strong>Direction correct</strong> — did carbon intensity actually move the way the model said. <strong>Regret</strong> — the model advised waiting and waiting turned out worse. LSTM tracks direction well; ARIMA sits near a coin flip at short horizons, which is why its temporal shift is currently held at execute-now in the live scheduler until its verified accuracy re-earns trust.
          </p>
        </div>

        {/* No-Regret Guard Explainer Card */}
        <div className="card" id="tour-guard" style={{ background: 'var(--surface-card)' }}>
          <h3 className="card-title" style={{ marginBottom: '0.75rem' }}>No-Regret Guard</h3>
          <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)', lineHeight: 1.7 }}>
            Before any forecast is allowed to delay a workload, the <strong>No-Regret Guard</strong> checks the predicted saving against a per-model threshold earned from each model's verified track record above — not a fixed guess. If the projected temporal shift clears less carbon reduction than that threshold, the guard overrides the delay to <span className="mono" style={{ color: 'var(--text-main)', fontWeight: 600 }}>t=0</span>. In practice ARIMA is held at execute-now until its accuracy recovers; LSTM shifts only when its verified confidence clears the bar.
          </p>
        </div>
      </main>
    </div>
  );
}

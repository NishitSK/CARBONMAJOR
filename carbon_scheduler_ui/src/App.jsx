import React, { useState, useEffect, useRef } from 'react';
import { 
  Leaf, 
  Zap, 
  Cpu, 
  AlertTriangle,
  CheckCircle,
  Settings,
  RefreshCw,
  Globe,
  TrendingDown,
  Activity,
  Play,
  Pause,
  Lock,
  Unlock,
  Shield,
  Search,
  ChevronDown,
  Info,
  Download,
  Clock
} from 'lucide-react';
import WorldMap from './components/WorldMap';
import { SpectrumDivider, SpectrumTick } from './components/SpectrumBar';

const API_BASE = '/api';

function App() {
  const [regions, setRegions] = useState([]);
  const [results, setResults] = useState([]);
  const [rejected, setRejected] = useState([]);
  const [maxLatency, setMaxLatency] = useState(200);
  const [mode, setMode] = useState('fixed');
  const [weights, setWeights] = useState({
    carbon: 0.4,
    latency: 0.3,
    resources: 0.3
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [renderError, setRenderError] = useState(null);
  
  // Toggles for Polish Pass
  const [isAutoSimulating, setIsAutoSimulating] = useState(false);
  const [demoMode, setDemoMode] = useState(false);
  const [debugMode, setDebugMode] = useState(false);
  const [explanation, setExplanation] = useState(null);
  const [cumulativeSavingsKg, setCumulativeSavingsKg] = useState(0);

  // One-day simulation: steps through a 24h synthetic diurnal carbon curve
  // per region (same generator the ARIMA/LSTM forecaster trains on) so you
  // can watch the recommended region shift as the grid gets cleaner/dirtier.
  const [daySimOn, setDaySimOn] = useState(false);
  const [daySimPlaying, setDaySimPlaying] = useState(true);
  const [simHour, setSimHour] = useState(0);
  const [dailySeries, setDailySeries] = useState(null); // { regions, series }
  const SIM_HOUR_MS = 1000;

  const timerRef = useRef(null);
  const simTimerRef = useRef(null);
  const lastScoredKeyRef = useRef(null);
  // Notional energy draw per scheduling decision, used only to turn a
  // gCO2/kWh delta into an illustrative kg-CO2-avoided counter.
  const ASSUMED_KWH_PER_DECISION = 0.5;

  // Initial Data Fetch
  useEffect(() => {
    fetchData();
  }, [mode, demoMode]);

  // Recalculate whenever weights or maxLatency change
  useEffect(() => {
    if (regions && regions.length > 0) {
      calculateScores();
    }
  }, [weights, maxLatency, regions, demoMode]);

  // Simulation Loop (random drift, disabled during the day simulation)
  useEffect(() => {
    if (isAutoSimulating && !demoMode && !daySimOn) {
      timerRef.current = setInterval(() => {
        fetchDrift();
      }, 5000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isAutoSimulating, regions, demoMode, daySimOn]);

  // Day Simulation: fetch the 24h curve once when switched on
  useEffect(() => {
    if (!daySimOn) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/regions/daily-series?mode=fixed`);
        const data = await res.json();
        if (!cancelled) {
          setDailySeries(data);
          setSimHour(0);
          setDaySimPlaying(true);
        }
      } catch (err) {
        console.error("Daily series fetch error:", err);
        setError("Failed to load day-simulation data.");
      }
    })();
    return () => { cancelled = true; };
  }, [daySimOn]);

  // Day Simulation: advance the clock
  useEffect(() => {
    if (daySimOn && daySimPlaying && dailySeries) {
      simTimerRef.current = setInterval(() => {
        setSimHour(h => (h + 1) % 24);
      }, SIM_HOUR_MS);
    } else if (simTimerRef.current) {
      clearInterval(simTimerRef.current);
    }
    return () => {
      if (simTimerRef.current) clearInterval(simTimerRef.current);
    };
  }, [daySimOn, daySimPlaying, dailySeries]);

  // Day Simulation: project the current simulated hour onto the region list
  useEffect(() => {
    if (!daySimOn || !dailySeries) return;
    const snapshot = dailySeries.regions.map(r => ({
      ...r,
      carbon: (dailySeries.series[r.name] || [])[simHour] ?? r.carbon
    }));
    setRegions(snapshot);
  }, [daySimOn, dailySeries, simHour]);

  const toggleDaySim = () => {
    const turningOn = !daySimOn;
    setDaySimOn(turningOn);
    if (turningOn) {
      setIsAutoSimulating(false);
      if (mode === 'live') setMode('fixed');
    } else {
      setDailySeries(null);
      fetchData();
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/regions?mode=${mode}&demo_mode=${demoMode}`);
      const data = await res.json();
      setRegions(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err) {
      setError("Failed to connect to backend API.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchDrift = async () => {
    if (!regions || regions.length === 0 || demoMode) return;
    try {
      const res = await fetch(`${API_BASE}/regions/drift`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ regions, demo_mode: demoMode })
      });
      const data = await res.json();
      setRegions(Array.isArray(data) ? data : regions);
    } catch (err) {
      console.error("Drift fetch error:", err);
    }
  };

  const calculateScores = async () => {
    try {
      const res = await fetch(`${API_BASE}/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            regions, 
            weights, 
            max_latency: maxLatency,
            demo_mode: demoMode 
        })
      });
      const data = await res.json();
      if (data && data.success) {
        setResults(data.eligible || []);
        setRejected(data.rejected || []);
        setExplanation(data.explanation || null);

        const eligible = data.eligible || [];
        if (eligible.length > 0) {
          const best = eligible[0].region;
          const avgCarbon = eligible.reduce((sum, r) => sum + r.region.carbon, 0) / eligible.length;
          const savingsKg = Math.max(0, (avgCarbon - best.carbon) / 1000 * ASSUMED_KWH_PER_DECISION);

          // Only accrue once per distinct region snapshot (drift tick / new fetch),
          // not on every weight-slider recompute of the same data.
          const snapshotKey = JSON.stringify(regions.map(r => [r.name, r.carbon]));
          if (snapshotKey !== lastScoredKeyRef.current) {
            lastScoredKeyRef.current = snapshotKey;
            setCumulativeSavingsKg(prev => prev + savingsKg);
          }
        }
      } else {
        setResults([]);
        setRejected((data && data.rejected) || []);
        setExplanation(null);
      }
    } catch (err) {
      console.error("Scoring error:", err);
    }
  };

  if (renderError) {
    return (
        <div style={{ background: '#000', color: '#f87171', height: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '2rem', textAlign: 'center', fontFamily: 'monospace' }}>
            <AlertTriangle size={64} />
            <h1 style={{ marginTop: '1rem' }}>Sytem Runtime Failure</h1>
            <p style={{ background: 'rgba(255,255,255,0.1)', padding: '1rem', borderRadius: '4px', maxWidth: '600px' }}>{renderError}</p>
            <button onClick={() => window.location.reload()} style={{ marginTop: '1rem', background: '#4f46e5', color: '#fff', border: 'none', padding: '0.5rem 1rem', borderRadius: '4px', cursor: 'pointer' }}>RETRY DASHBOARD</button>
        </div>
    );
  }

  const handleWeightChange = (key, val) => {
    setWeights(prev => ({ ...prev, [key]: parseFloat(val) }));
  };

  const exportCsv = () => {
    if (!results || results.length === 0) return;
    const headers = ['rank', 'region', 'carbon_g_per_kwh', 'latency_ms', 'resources_pct', 'score', 'strengths'];
    const rows = results.map(r => [
      r.rank,
      r.region.name,
      r.region.carbon,
      r.region.latency,
      r.region.resources,
      r.score,
      (r.metadata?.strengths || []).join('; ')
    ]);
    const rejectedRows = (rejected || []).map(r => [
      '-', r.name, '-', '-', '-', 'REJECTED', r.reason
    ]);
    const csv = [headers, ...rows, ...rejectedRows]
      .map(row => row.map(v => `"${String(v).replace(/"/g, '""')}"`).join(','))
      .join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `carbon_scheduler_report_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const bestResult = results && results.length > 0 ? results[0] : null;
  const bestRegion = bestResult?.region;

  // Final rendering logic with try/catch safeguard
  try {
    return (
        <div className="dashboard-container">
          <header>
            <div className="console-header">
              <div>
                <div className="console-eyebrow">Carbon-aware placement engine</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <Shield size={22} color="var(--accent)" />
                    <h1>Carbon-Aware Scheduler</h1>
                </div>
                <p className="console-sub">
                  {bestRegion
                    ? <>Routing to <strong style={{ color: 'var(--accent)' }}>{bestRegion.name}</strong>{daySimOn ? ` at hour ${String(simHour).padStart(2, '0')}:00` : ' right now'}</>
                    : 'Awaiting region data…'}
                </p>
              </div>

              <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
                <div className="glass-panel savings-counter" title="Illustrative kg CO2 avoided vs. average eligible region, accrued per snapshot">
                  <Leaf size={15} color="var(--spectrum-clean)" />
                  <span className="savings-value mono">{cumulativeSavingsKg.toFixed(3)} kg CO₂ saved</span>
                </div>

                <div className="glass-panel header-controls" style={{ display: 'flex', gap: '0.6rem', padding: '0.4rem 0.6rem' }}>
                  <div className="toggle-group">
                      <button
                        onClick={() => setDemoMode(!demoMode)}
                        className={`toggle-btn ${demoMode ? 'on' : ''}`}
                      >
                        {demoMode ? <Lock size={13} /> : <Unlock size={13} />}
                        DEMO {demoMode ? 'ON' : 'OFF'}
                      </button>
                      <button
                        onClick={() => setDebugMode(!debugMode)}
                         className={`toggle-btn ${debugMode ? 'on' : ''}`}
                      >
                        {debugMode ? <Activity size={13} /> : <RefreshCw size={13} />}
                        DEBUG {debugMode ? 'ON' : 'OFF'}
                      </button>
                  </div>
                  <div className="header-sep"></div>

                  <button
                      onClick={() => setIsAutoSimulating(!isAutoSimulating)}
                      disabled={demoMode || daySimOn}
                      className={`ghost-btn ${isAutoSimulating ? 'ghost-btn-on' : ''}`}
                  >
                    {isAutoSimulating ? <Pause size={13} /> : <Play size={13} />}
                    {isAutoSimulating ? 'Stop drift' : 'Random drift'}
                  </button>
                  <div className="header-sep"></div>
                  <button
                      onClick={() => setMode('live')}
                      disabled={daySimOn}
                      className={`ghost-btn live-btn ${mode === 'live' ? 'live-btn-on' : ''}`}
                  >
                    <Activity size={13} /> Live maps
                  </button>
                  <div className="header-sep"></div>
                  <button
                      onClick={toggleDaySim}
                      className={`ghost-btn day-sim-btn ${daySimOn ? 'day-sim-btn-on' : ''}`}
                  >
                    <Clock size={13} /> Day simulation
                  </button>
                </div>
              </div>
            </div>

            {daySimOn && (
              <div className="glass-panel daysim-console">
                <button
                  className="daysim-playbtn"
                  onClick={() => setDaySimPlaying(p => !p)}
                  disabled={!dailySeries}
                  title={daySimPlaying ? 'Pause' : 'Play'}
                >
                  {daySimPlaying ? <Pause size={15} /> : <Play size={15} />}
                </button>
                <span className="daysim-clock mono">{String(simHour).padStart(2, '0')}:00</span>
                <input
                  type="range"
                  min="0"
                  max="23"
                  step="1"
                  value={simHour}
                  disabled={!dailySeries}
                  onChange={(e) => { setDaySimPlaying(false); setSimHour(parseInt(e.target.value)); }}
                  className="daysim-scrub"
                />
                <span className="daysim-label">
                  {dailySeries ? 'Simulated 24h diurnal carbon curve — scrub or press play' : 'Loading day curve…'}
                </span>
              </div>
            )}

            <SpectrumDivider />
          </header>

          {error && (
            <div className="glass-panel status-fail" style={{ textAlign: 'center', margin: '0 0 1.25rem' }}>
              <AlertTriangle style={{ verticalAlign: 'middle', marginRight: '8px' }} />
              {error} (Check port 8001)
            </div>
          )}
    
          <div className="grid-layout">
            <div className="left-panel">
              
              {/* MAP SECTION */}
              <section className="glass-panel no-padding overflow-hidden" style={{ minHeight: '400px' }}>
                <div className="panel-header">
                    <span className="panel-title">
                        <Globe size={16} color="var(--accent)" /> Deployment Map
                    </span>
                    <div style={{ display: 'flex', gap: '8px' }}>
                        {demoMode && <span className="status-badge" style={{ background: 'var(--accent-dim)', color: 'var(--accent)' }}>Simulation locked · seed 42</span>}
                        {isAutoSimulating && <span className="status-badge pulse" style={{ background: 'var(--accent-dim)', color: 'var(--accent)' }}>Live drift active</span>}
                    </div>
                </div>
                <WorldMap 
                  regions={regions || []} 
                  bestRegionName={bestRegion?.name} 
                  onRegionClick={(r) => {
                    if (!r) return;
                    const el = document.getElementById(`region-${r.name}`);
                    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                  }}
                />
              </section>
    
              {/* EXPLAINABILITY PANEL */}
              {explanation && explanation.details && (
                <section className="glass-panel explainability-panel">
                    <div style={{ display: 'flex', gap: '12px' }}>
                        <div style={{ background: 'var(--spectrum-clean)', borderRadius: '50%', padding: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center', width: '32px', height: '32px', flexShrink: 0 }}>
                            <CheckCircle size={20} color="#06291F" />
                        </div>
                        <div style={{ flex: 1 }}>
                            <h3 style={{ fontSize: '1.05rem', margin: 0, fontFamily: "'Space Grotesk', sans-serif" }}>Recommended placement</h3>
                            <p style={{ color: 'var(--text)', fontSize: '0.92rem', marginTop: '0.4rem', fontWeight: 400 }}>
                                {explanation.summary || "Recommended based on balance."}
                            </p>
                            <div style={{ display: 'flex', gap: '1.5rem', marginTop: '1rem' }}>
                                <div className="explanation-metric">
                                    <span className="label">Carbon Impact</span>
                                    <span className="value">{explanation.details.carbon_impact}</span>
                                </div>
                                <div className="explanation-metric">
                                    <span className="label">Performance</span>
                                    <span className="value">{explanation.details.performance}</span>
                                </div>
                                <div className="explanation-metric">
                                    <span className="label">Available Capacity</span>
                                    <span className="value">{explanation.details.capacity}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>
              )}
    
              {/* REJECTED REGIONS SECTION */}
              {rejected && rejected.length > 0 && (
                <section className="rejected-list-section">
                    <h2 className="panel-title" style={{ color: 'var(--danger)', marginBottom: '1rem' }}>
                        <AlertTriangle size={16} /> Rejected — over latency budget
                    </h2>
                    <div className="rejected-grid">
                        {rejected.map(r => (
                            <div key={r?.name || Math.random()} className="glass-panel rejected-card-small">
                                <span style={{ fontWeight: 600 }}>{r?.name}</span>
                                <span className="mono" style={{ color: 'var(--danger)', fontSize: '0.78rem' }}>{r?.reason}</span>
                            </div>
                        ))}
                    </div>
                </section>
              )}
    
              {/* RESULTS TABLE */}
              <section>
                 <div className="panel-title" style={{ marginBottom: '1rem', justifyContent: 'space-between', display: 'flex' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <TrendingDown size={16} color="var(--accent)" /> Region rankings
                    </span>
                    <button
                      onClick={exportCsv}
                      disabled={!results || results.length === 0}
                      className="export-btn"
                    >
                      <Download size={14} /> Export CSV
                    </button>
                  </div>
                  <div className="glass-panel no-padding">
                    <table className="results-table">
                      <thead>
                        <tr>
                          <th>Rank</th>
                          <th>Region</th>
                          <th>Carbon</th>
                          {debugMode && (
                            <>
                                <th>C_norm</th>
                                <th>L_norm</th>
                                <th>R_penalty</th>
                            </>
                          )}
                          <th>Score</th>
                          <th>Strengths</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(results || []).map((res) => (
                          <tr key={res?.region?.name} id={`region-${res?.region?.name}`} className={res?.rank === 1 ? 'rank-1' : ''}>
                            <td className="mono" style={{ fontWeight: 700, color: 'var(--text-dim)' }}>#{res?.rank}</td>
                            <td>{res?.region?.name}</td>
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <SpectrumTick carbon={res?.region?.carbon} />
                                <span className="mono" style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>{res?.region?.carbon}g</span>
                              </div>
                            </td>
                            {debugMode && res?.metadata && (
                                <>
                                    <td className="mono" style={{ color: 'var(--text-dim)' }}>{res.metadata.c_norm}</td>
                                    <td className="mono" style={{ color: 'var(--text-dim)' }}>{res.metadata.l_norm}</td>
                                    <td className="mono" style={{ color: 'var(--text-dim)' }}>{res.metadata.r_penalty}</td>
                                </>
                            )}
                            <td className="score-cell">{res?.score?.toFixed(4) || "0.0000"}</td>
                            <td>
                                <div style={{ display: 'flex', gap: '4px' }}>
                                    {(res?.metadata?.strengths || []).map(s => (
                                        <span key={s} className="mini-badge">{s}</span>
                                    ))}
                                </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
              </section>
            </div>
    
            {/* SIDEBAR */}
            <aside>
              <div className="glass-panel sidebar-sticky">
                <div className="panel-title" style={{ marginBottom: '1.25rem' }}>
                  <Settings size={15} color="var(--accent)" /> Scoring controls
                </div>

                <div className="weight-display mono">
                    <span>C {weights.carbon.toFixed(2)} · L {weights.latency.toFixed(2)} · R {weights.resources.toFixed(2)}</span>
                </div>

                <div className="control-group">
                  <label>Carbon weight</label>
                  <input type="range" min="0" max="1" step="0.05" value={weights.carbon} onChange={(e) => handleWeightChange('carbon', e.target.value)} />
                </div>

                <div className="control-group">
                  <label>Latency weight</label>
                  <input type="range" min="0" max="1" step="0.05" value={weights.latency} onChange={(e) => handleWeightChange('latency', e.target.value)} />
                </div>

                <div className="control-group">
                  <label>Resource weight</label>
                  <input type="range" min="0" max="1" step="0.05" value={weights.resources} onChange={(e) => handleWeightChange('resources', e.target.value)} />
                </div>

                <hr className="divider" />

                <div className="control-group">
                  <label>Max latency allowed</label>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>Budget</span>
                    <span className="mono" style={{ fontWeight: 700, color: 'var(--spectrum-mid)' }}>{maxLatency} ms</span>
                  </div>
                  <input type="range" min="20" max="400" step="10" value={maxLatency} onChange={(e) => setMaxLatency(parseInt(e.target.value))} />
                </div>

                <div className="info-panel">
                    <Info size={14} color="var(--accent)" />
                    <p>Scores are normalized only across regions inside the {maxLatency}ms budget.</p>
                </div>

                {bestRegion && (
                  <div className="best-region-box glass-panel best-region-glow">
                     <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                        <CheckCircle size={15} color="var(--accent)" />
                        <span className="mono" style={{ fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.05em', color: 'var(--accent)', textTransform: 'uppercase' }}>Selected region</span>
                     </div>
                     <div style={{ fontSize: '1.15rem', fontWeight: 700, fontFamily: "'Space Grotesk', sans-serif" }}>{bestRegion.name}</div>
                  </div>
                )}
              </div>
            </aside>
          </div>
          <style>{`
            .savings-counter { display: flex; align-items: center; gap: 8px; padding: 0.5rem 0.9rem; }
            .savings-value { font-size: 0.8rem; font-weight: 600; color: var(--spectrum-clean); white-space: nowrap; }
            .export-btn { display: flex; align-items: center; gap: 6px; background: var(--surface-raised); border: 1px solid var(--line); color: var(--text-dim); font-size: 0.72rem; font-weight: 600; padding: 0.45rem 0.8rem; border-radius: var(--radius-sm); cursor: pointer; }
            .export-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent-line); }
            .export-btn:disabled { opacity: 0.35; cursor: not-allowed; }
            .header-sep { width: 1px; background: var(--line); margin: 0 2px; }
            .toggle-group { display: flex; gap: 2px; background: var(--bg-deep); padding: 2px; border-radius: 6px; }
            .toggle-btn { background: transparent; border: none; font-size: 0.62rem; letter-spacing: 0.03em; padding: 5px 9px; border-radius: 4px; color: var(--text-faint); font-weight: 700; display: flex; align-items: center; gap: 4px; transition: all 0.15s; }
            .toggle-btn.on { background: var(--accent-dim); color: var(--accent); }
            .ghost-btn { display: flex; gap: 6px; align-items: center; background: transparent; border: 1px solid var(--line); color: var(--text-dim); font-size: 0.68rem; font-weight: 700; letter-spacing: 0.02em; padding: 6px 10px; }
            .ghost-btn-on { background: var(--accent-dim); border-color: var(--accent-line); color: var(--accent); }
            .live-btn { border-color: rgba(61, 220, 132, 0.3); color: var(--spectrum-clean); }
            .live-btn-on { background: rgba(61, 220, 132, 0.14); border-color: var(--spectrum-clean); color: var(--spectrum-clean); }
            .day-sim-btn { border-color: rgba(94, 230, 200, 0.3); }
            .day-sim-btn-on { background: var(--accent-dim); border-color: var(--accent); color: var(--accent); }
            .daysim-console { display: flex; align-items: center; gap: 0.9rem; padding: 0.6rem 1rem; margin-bottom: 0.9rem; }
            .daysim-playbtn { background: var(--accent); color: #06291F; border: none; border-radius: 50%; width: 30px; height: 30px; min-width: 30px; display: flex; align-items: center; justify-content: center; padding: 0; }
            .daysim-clock { font-size: 1rem; font-weight: 700; color: var(--text); min-width: 48px; }
            .daysim-scrub { flex: 1; margin: 0; }
            .daysim-label { font-size: 0.74rem; color: var(--text-faint); white-space: nowrap; }
            @media (max-width: 640px) { .daysim-label { display: none; } }
            .rejected-list-section { margin-top: 1.5rem; }
            .rejected-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
            .rejected-card-small { padding: 0.8rem; display: flex; flex-direction: column; gap: 2px; }
            .explainability-panel { margin: 0; padding: 1.4rem; }
            .explanation-metric { display: flex; flex-direction: column; }
            .explanation-metric .label { font-size: 0.66rem; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.06em; font-weight: 700; }
            .explanation-metric .value { font-size: 0.9rem; color: var(--text); font-weight: 600; font-family: 'IBM Plex Mono', monospace; }
            .results-table { width: 100%; border-collapse: collapse; }
            .rank-1 { background: var(--accent-dim); }
            .score-cell { font-family: 'IBM Plex Mono', monospace; font-weight: 700; color: var(--accent); }
            .mini-badge { padding: 2px 7px; border-radius: 4px; }
            .weight-display { margin-bottom: 1.1rem; background: var(--bg-deep); padding: 5px 9px; border-radius: var(--radius-sm); display: inline-block; font-size: 0.72rem; color: var(--text-dim); }
            .info-panel { margin-top: 1.25rem; padding: 0.75rem; background: var(--bg-deep); border-radius: var(--radius-sm); display: flex; gap: 8px; align-items: flex-start; }
            .info-panel p { margin: 0; font-size: 0.74rem; color: var(--text-dim); line-height: 1.45; }
            .divider { border: none; border-top: 1px solid var(--line); margin: 1.25rem 0; }
            @media (prefers-reduced-motion: no-preference) {
              .pulse { animation: pulse-anim 2.2s ease-in-out infinite; }
            }
            @keyframes pulse-anim {
              0%, 100% { opacity: 1; }
              50% { opacity: 0.5; }
            }
          `}</style>
        </div>
      );
  } catch (err) {
    setRenderError(err.message);
    return null;
  }
}

export default App;

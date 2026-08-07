import React from 'react';
import { Link } from 'react-router-dom';
import {
  Leaf, AlertTriangle, CheckCircle, RefreshCw, Globe, Activity, Play, Pause,
  Lock, Unlock, Shield, Clock, ArrowLeft
} from 'lucide-react';
import WorldMap from '../components/demo/WorldMap';
import { SpectrumDivider } from '../components/demo/SpectrumBar';
import ScoringControls from '../components/demo/ScoringControls';
import RegionRankingsTable from '../components/demo/RegionRankingsTable';
import RejectedRegionsPanel from '../components/demo/RejectedRegionsPanel';
import DaySimControls from '../components/demo/DaySimControls';
import { useLiveScheduler } from '../hooks/useLiveScheduler';
import '../styles/demo.css';

// The old fake-data sandbox (random drift / synthetic day simulation /
// live-fixed toggle), relocated off the main narrative page per the
// "the demo model has to work with the data it has" direction -- this is
// still a legitimate "play with the live scoring knobs" tool, just not the
// thing that represents "real data" on the main site.
export default function PlaygroundPage() {
  const s = useLiveScheduler();

  return (
    <div className="dashboard-container">
      <header>
        <div className="console-header">
          <div>
            <Link to="/" className="ghost-btn" style={{ marginBottom: '0.9rem', display: 'inline-flex' }}>
              <ArrowLeft size={13} /> Back to research site
            </Link>
            <div className="console-eyebrow">Carbon-aware placement engine · sandbox</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Shield size={22} color="var(--accent)" />
              <h1>Scoring Playground</h1>
            </div>
            <p className="console-sub">
              {s.bestRegion
                ? <>Routing to <strong style={{ color: 'var(--accent)' }}>{s.bestRegion.name}</strong>{s.daySimOn ? ` at hour ${String(s.simHour).padStart(2, '0')}:00` : ' right now'}</>
                : 'Awaiting region data…'}
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
            <div className="glass-panel savings-counter" title="Illustrative kg CO2 avoided vs. average eligible region, accrued per snapshot">
              <Leaf size={15} color="var(--spectrum-clean)" />
              <span className="savings-value mono">{s.cumulativeSavingsKg.toFixed(3)} kg CO₂ saved</span>
            </div>

            <div className="glass-panel header-controls" style={{ display: 'flex', gap: '0.6rem', padding: '0.4rem 0.6rem' }}>
              <div className="toggle-group">
                <button onClick={() => s.setDemoMode(!s.demoMode)} className={`toggle-btn ${s.demoMode ? 'on' : ''}`}>
                  {s.demoMode ? <Lock size={13} /> : <Unlock size={13} />}
                  DEMO {s.demoMode ? 'ON' : 'OFF'}
                </button>
                <button onClick={() => s.setDebugMode(!s.debugMode)} className={`toggle-btn ${s.debugMode ? 'on' : ''}`}>
                  {s.debugMode ? <Activity size={13} /> : <RefreshCw size={13} />}
                  DEBUG {s.debugMode ? 'ON' : 'OFF'}
                </button>
              </div>
              <div className="header-sep"></div>

              <button
                onClick={() => s.setIsAutoSimulating(!s.isAutoSimulating)}
                disabled={s.demoMode || s.daySimOn}
                className={`ghost-btn ${s.isAutoSimulating ? 'ghost-btn-on' : ''}`}
              >
                {s.isAutoSimulating ? <Pause size={13} /> : <Play size={13} />}
                {s.isAutoSimulating ? 'Stop drift' : 'Random drift'}
              </button>
              <div className="header-sep"></div>
              <button onClick={() => s.setMode('live')} disabled={s.daySimOn} className={`ghost-btn live-btn ${s.mode === 'live' ? 'live-btn-on' : ''}`}>
                <Activity size={13} /> Live maps
              </button>
              <div className="header-sep"></div>
              <button onClick={s.toggleDaySim} className={`ghost-btn day-sim-btn ${s.daySimOn ? 'day-sim-btn-on' : ''}`}>
                <Clock size={13} /> Day simulation
              </button>
            </div>
          </div>
        </div>

        {s.daySimOn && (
          <DaySimControls
            daySimPlaying={s.daySimPlaying}
            onTogglePlay={() => s.setDaySimPlaying(p => !p)}
            simHour={s.simHour}
            onScrub={(h) => { s.setDaySimPlaying(false); s.setSimHour(h); }}
            dailySeries={s.dailySeries}
          />
        )}

        <SpectrumDivider />
      </header>

      {s.error && (
        <div className="glass-panel status-fail" style={{ textAlign: 'center', margin: '0 0 1.25rem' }}>
          <AlertTriangle style={{ verticalAlign: 'middle', marginRight: '8px' }} />
          {s.error} (Check port 8001)
        </div>
      )}

      <div className="grid-layout">
        <div className="left-panel">
          <section className="glass-panel no-padding overflow-hidden" style={{ minHeight: '400px' }}>
            <div className="panel-header">
              <span className="panel-title">
                <Globe size={16} color="var(--accent)" /> Deployment Map
              </span>
              <div style={{ display: 'flex', gap: '8px' }}>
                {s.demoMode && <span className="status-badge" style={{ background: 'var(--accent-dim)', color: 'var(--accent)' }}>Simulation locked · seed 42</span>}
                {s.isAutoSimulating && <span className="status-badge pulse" style={{ background: 'var(--accent-dim)', color: 'var(--accent)' }}>Live drift active</span>}
              </div>
            </div>
            <WorldMap
              regions={s.regions || []}
              bestRegionName={s.bestRegion?.name}
              onRegionClick={(r) => {
                if (!r) return;
                const el = document.getElementById(`region-${r.name}`);
                if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
              }}
            />
          </section>

          {s.explanation && s.explanation.details && (
            <section className="glass-panel explainability-panel">
              <div style={{ display: 'flex', gap: '12px' }}>
                <div style={{ background: 'var(--spectrum-clean)', borderRadius: '50%', padding: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center', width: '32px', height: '32px', flexShrink: 0 }}>
                  <CheckCircle size={20} color="#06291F" />
                </div>
                <div style={{ flex: 1 }}>
                  <h3 style={{ fontSize: '1.05rem', margin: 0, fontFamily: "'Space Grotesk', sans-serif" }}>Recommended placement</h3>
                  <p style={{ color: 'var(--text)', fontSize: '0.92rem', marginTop: '0.4rem', fontWeight: 400 }}>
                    {s.explanation.summary || 'Recommended based on balance.'}
                  </p>
                  <div style={{ display: 'flex', gap: '1.5rem', marginTop: '1rem' }}>
                    <div className="explanation-metric">
                      <span className="label">Carbon Impact</span>
                      <span className="value">{s.explanation.details.carbon_impact}</span>
                    </div>
                    <div className="explanation-metric">
                      <span className="label">Performance</span>
                      <span className="value">{s.explanation.details.performance}</span>
                    </div>
                    <div className="explanation-metric">
                      <span className="label">Available Capacity</span>
                      <span className="value">{s.explanation.details.capacity}</span>
                    </div>
                  </div>
                </div>
              </div>
            </section>
          )}

          <RejectedRegionsPanel rejected={s.rejected} />
          <RegionRankingsTable results={s.results} debugMode={s.debugMode} onExportCsv={s.exportCsv} />
        </div>

        <aside>
          <ScoringControls
            weights={s.weights}
            onWeightChange={s.handleWeightChange}
            maxLatency={s.maxLatency}
            onMaxLatencyChange={s.setMaxLatency}
            bestRegion={s.bestRegion}
          />
        </aside>
      </div>
    </div>
  );
}

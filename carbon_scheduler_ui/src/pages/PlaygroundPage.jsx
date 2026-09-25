import React from 'react';
import { Link } from 'react-router-dom';
import {
  Leaf, AlertTriangle, Play, Pause,
  Lock, Unlock, Activity, Clock, FlaskConical, Sliders, Zap, Compass
} from 'lucide-react';
import TopNavbar from '../components/layout/TopNavbar';
import WorldMap from '../components/demo/WorldMap';
import ScoringControls from '../components/demo/ScoringControls';
import RegionRankingsTable from '../components/demo/RegionRankingsTable';
import RejectedRegionsPanel from '../components/demo/RejectedRegionsPanel';
import FleetPanel from '../components/demo/FleetPanel';
import TimelineMigrationPath from '../components/demo/TimelineMigrationPath';
import { useLiveScheduler } from '../hooks/useLiveScheduler';
import { useClientFleet } from '../hooks/useClientFleet';
import '../styles/demo.css';
import '../styles/console.css';

export default function PlaygroundPage() {
  const fleet = useClientFleet();
  const fleetRegions = React.useMemo(
    () => [...new Set((fleet.servers || []).map(sv => sv.zoneName))],
    [fleet.servers]
  );
  const s = useLiveScheduler({ allowedRegionNames: fleetRegions });
  const regionNames = (s.regions || []).map(r => r.name);

  // A scenario sets the whole situation at once: the regions you run in, the
  // latency budget and the weights. Setting only the budget used to leave
  // nothing eligible when the fleet sat outside it.
  const applyScenario = (regions, sla, weights) => {
    fleet.resetFleet();
    regions.forEach((r) => fleet.addServer(`server-${r.split(' ')[0]}`, r));
    s.setMaxLatency(sla);
    Object.entries(weights).forEach(([k, v]) => s.handleWeightChange(k, v));
    s.resetSelection();
  };

  return (
    <div className="app-layout">
      <TopNavbar />

      <main className="main-content">
        <div className="page-header">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1.5rem' }}>
            <div>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--primary)', letterSpacing: '0.08em', marginBottom: '0.4rem' }}>
                Interactive Simulation Sandbox
              </div>
              <h1 className="page-title">Policy & Spatial Migration Playground</h1>
              <p className="page-subtitle">
                {s.activeRegion
                  ? <>
                      {fleetRegions.length === 0
                        ? (s.isOverride ? 'Planned Placement (manual choice): ' : 'Planned Optimal Placement: ')
                        : (s.isOverride ? 'Active Placement (manual override): ' : 'Active Optimal Placement: ')}
                      <strong style={{ color: s.isOverride ? 'var(--primary)' : 'var(--clean)' }}>{s.activeRegion.name}</strong>
                      {s.isOverride ? ` · optimal is ${s.bestRegion.name}` : ''}
                      {s.daySimOn ? ` at simulation hour ${String(s.simHour).padStart(2, '0')}:00 UTC` : ''}
                    </>
                  : 'Awaiting candidate telemetry…'}
              </p>
            </div>

            {/* Sandbox Controls Bar */}
            <div id="tour-solar-trail" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
              <div className="card" style={{ padding: '0.6rem 1.25rem', marginBottom: 0, display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <Leaf size={18} color="var(--clean)" />
                <span className="mono" style={{ fontWeight: 700, color: 'var(--clean)', fontSize: '1rem' }}>
                  {s.cumulativeSavingsKg.toFixed(3)} kg CO₂ avoided
                </span>
              </div>

              <button
                onClick={() => s.setDemoMode(!s.demoMode)}
                className={`btn ${s.demoMode ? 'btn-primary' : 'btn-outline'}`}
                style={{ padding: '0.65rem 1rem', fontSize: '0.85rem' }}
                title="Locks the sandbox to a fixed reference scenario (seed 42)"
              >
                {s.demoMode ? <Lock size={15} /> : <Unlock size={15} />}
                {s.demoMode ? 'Seed-42 Locked' : 'Live Mode'}
              </button>

              <button
                onClick={s.toggleDaySim}
                className={`btn ${s.daySimOn ? 'btn-primary' : 'btn-outline'}`}
                style={{ padding: '0.65rem 1rem', fontSize: '0.85rem' }}
              >
                <Compass size={15} /> {s.daySimOn ? '24h Path Active' : 'Enable 24h Solar Path'}
              </button>
            </div>
          </div>
        </div>

        {/* 24-Hour Timeline Migration Path Visualizer (Visible when 24h Path is Active or Enabled) */}
        {s.daySimOn && (
          <div style={{ marginBottom: '2rem' }}>
            <TimelineMigrationPath
              daySimPlaying={s.daySimPlaying}
              onTogglePlay={() => s.setDaySimPlaying(p => !p)}
              simHour={s.simHour}
              onScrub={(h) => { s.setDaySimPlaying(false); s.setSimHour(h); }}
              dailySeries={s.dailySeries}
              regions={s.regions}
              bestRegion={s.bestRegion}
            />
          </div>
        )}

        {/* Presentation Presets Bar */}
        <div className="card" style={{ padding: '0.85rem 1.25rem', marginBottom: '1.5rem', background: 'var(--bg-subtle)', borderColor: 'var(--border-subtle)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--primary)', letterSpacing: '0.05em' }}>
                Scenario presets
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Each one sets a server fleet, a latency budget and the scoring weights together
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
              <button
                className="btn btn-outline"
                style={{ fontSize: '0.8rem', padding: '0.45rem 0.85rem', borderColor: 'rgba(59, 130, 246, 0.4)' }}
                onClick={() => applyScenario(
                  ['ap-south-1 (Mumbai)', 'ap-southeast-1 (Singapore)', 'ap-northeast-1 (Tokyo)'],
                  150,
                  { carbon: 0.5, latency: 0.3, resources: 0.2 }
                )}
              >
                <span>🌏</span> <strong>APAC sovereign (DPDP)</strong>
              </button>

              <button
                className="btn btn-outline"
                style={{ fontSize: '0.8rem', padding: '0.45rem 0.85rem', borderColor: 'rgba(16, 185, 129, 0.4)' }}
                onClick={() => applyScenario(
                  ['us-east-1 (N. Virginia)', 'us-east-2 (Ohio)', 'ca-central-1 (Canada)'],
                  250,
                  { carbon: 0.4, latency: 0.4, resources: 0.2 }
                )}
              >
                <span>🛡️</span> <strong>Americas (HIPAA)</strong>
              </button>

              <button
                className="btn btn-outline"
                style={{ fontSize: '0.8rem', padding: '0.45rem 0.85rem', borderColor: 'rgba(234, 179, 8, 0.4)' }}
                onClick={() => applyScenario([], 400, { carbon: 0.7, latency: 0.1, resources: 0.2 })}
              >
                <span>⚡</span> <strong>Global batch (any region)</strong>
              </button>
            </div>
          </div>
        </div>

        {s.error && (
          <div className="card" style={{ borderColor: 'var(--dirty-border)', background: 'var(--dirty-bg)', textAlign: 'center', padding: '1rem' }}>
            <AlertTriangle style={{ verticalAlign: 'middle', marginRight: '8px', color: 'var(--dirty)' }} />
            {s.error}
          </div>
        )}

        {/* 2-Column Main Workspace */}
        <div className="playground-grid">
          {/* Left Column: World Map, Rankings Table */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            <FleetPanel
              servers={fleet.servers || []}
              regionNames={regionNames}
              rejectedNames={(s.rejectedRegions || []).map(r => r.name)}
              onAdd={fleet.addServer}
              onRemove={fleet.removeServer}
              onChangeZone={fleet.changeServerZone}
              onLoadExample={fleet.loadDemoFleet}
              onClear={fleet.resetFleet}
            />

            <WorldMap
              regions={s.regions}
              bestRegionName={s.bestRegion ? s.bestRegion.name : undefined}
              activeRegionName={s.activeRegion ? s.activeRegion.name : undefined}
              onRegionClick={(region) => {
                // Only regions inside the SLA budget can become the placement.
                if (s.results.some(r => r.region?.name === region.name)) s.setSelectedRegion(region.name);
              }}
            />

            <RejectedRegionsPanel rejected={s.rejectedRegions} />

            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Multi-Criteria Candidate Rankings</h2>
                <button className="btn btn-outline" style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }} onClick={s.exportCsv}>
                  Export CSV
                </button>
              </div>

              {s.results.length === 0 && (
                <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', padding: '0.5rem 0 1rem' }}>
                  {fleetRegions.length > 0
                    ? `Every region in your fleet is above the ${s.maxLatency} ms latency budget, so nothing is eligible. Raise the budget, or add a server closer to your users.`
                    : 'No candidate regions yet — waiting for telemetry.'}
                </p>
              )}

              {fleetRegions.length === 0 && s.results.length > 0 && (
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', padding: '0 0 0.75rem' }}>
                  Planning mode: you have no servers yet, so these are candidate locations and the choice below is a
                  proposal. Add a server above to rank only the regions you actually run in.
                </p>
              )}

              <RegionRankingsTable
                hideHeader
                planningMode={fleetRegions.length === 0}
                results={s.results}
                debugMode={s.debugMode}
                activeRegionName={s.activeRegion ? s.activeRegion.name : undefined}
                onSelectRegion={(name) => s.setSelectedRegion(name)}
              />
            </div>
          </div>

          {/* Right Column: Scoring Sliders & Explanations */}
          <aside style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Policy Weights & SLA Limits</h2>
              </div>

              <ScoringControls
                weights={s.weights}
                onWeightChange={s.handleWeightChange}
                maxLatency={s.maxLatency}
                onMaxLatencyChange={s.setMaxLatency}
                bestRegion={s.bestRegion}
                activeRegion={s.activeRegion}
                isOverride={s.isOverride}
                overrideImpact={s.overrideImpact}
                onResetSelection={s.resetSelection}
                explanation={s.explanation}
              />
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}

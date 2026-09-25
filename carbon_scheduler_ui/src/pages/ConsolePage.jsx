import React, { useState, useEffect, useMemo } from 'react';
import TopNavbar from '../components/layout/TopNavbar';
import { useDataMode } from '../data/DataModeContext';
import { REGIONS } from '../sim/regions';
import { carbonAtHour, currentHour } from '../sim/carbonModel';
import { score } from '../sim/scoring';
import { JURISDICTIONS } from '../sim/jurisdictions';

const LIVE_REGIONS_URL = 'http://127.0.0.1:8001/regions/';

const REGION_GROUPS = {
  APAC: ['ap-south-1', 'ap-southeast-1', 'ap-northeast-1', 'ap-southeast-2'],
  AMERICAS: ['us-east-1', 'us-east-2', 'us-west-2', 'ca-central-1', 'sa-east-1'],
  EUROPE: ['eu-north-1', 'eu-west-1', 'eu-central-1'],
};

// Batch streams tolerate cross-continent latency (measured from India), so
// the dispatcher's SLA ceiling is wider than the interactive 200 ms default.
const DISPATCH_WEIGHTS = { carbon: 0.6, latency: 0.2, resources: 0.2 };
const DISPATCH_MAX_LATENCY_MS = 400;

const STREAMS = [
  {
    key: 'apac_sovereign',
    title: 'APAC Banking & Telemetry',
    badge: 'Data Sovereignty: India DPDP / APAC',
    blurb: 'Restricted to Asia-Pacific datacenters (Mumbai, Singapore, Tokyo, Sydney). Prohibited from leaving the continent.',
    baselineCode: 'ap-south-1',
  },
  {
    key: 'americas_sovereign',
    title: 'Americas Enterprise Job',
    badge: 'Compliance: US HIPAA / SOC-2',
    blurb: 'Restricted to North/South American data boundaries (Virginia, Ohio, Oregon, Canada, Sao Paulo).',
    baselineCode: 'us-east-1',
  },
  {
    key: 'global_unconstrained',
    title: 'Global Flexible Batch',
    badge: 'Policy: Deep Batch AI / Flexible',
    blurb: 'Unconstrained cross-continental placement. Routes to the cleanest region in the fleet.',
    baselineCode: 'us-east-1',
  },
];

const regionCode = (name) => String(name).split(' ')[0];

function simulatedFleet() {
  const hour = currentHour();
  return REGIONS.map((r) => ({
    name: r.name,
    zone: r.zone,
    carbon: Math.round(carbonAtHour(r, hour, 0) * 10) / 10,
    latency: r.latencyFromIndia,
    resources: 80,
  }));
}

// Real scoring (src/sim/scoring.js, a port of services/scheduler.py) over the
// regions this jurisdiction is legally allowed to use.
function planStream(stream, fleet) {
  const allowed = JURISDICTIONS[stream.key].allowed;
  const pool = fleet.filter((r) => !allowed || allowed.some((a) => regionCode(a) === regionCode(r.name)));
  const baseline = fleet.find((r) => regionCode(r.name) === stream.baselineCode);
  const result = score(
    pool.map((r) => ({ name: r.name, carbon: r.carbon, latency: r.latency, resources: r.resources ?? 80 })),
    DISPATCH_WEIGHTS,
    DISPATCH_MAX_LATENCY_MS
  );
  if (!result.success || !baseline) return null;
  const best = result.eligible[0];
  const cutPct = baseline.carbon > 0 ? ((baseline.carbon - best.region.carbon) / baseline.carbon) * 100 : 0;
  return { baseline, best, cutPct, poolSize: pool.length, summary: result.explanation.summary };
}

export default function ConsolePage() {
  const { mode } = useDataMode();
  const [fleet, setFleet] = useState([]);
  const [loading, setLoading] = useState(true);
  const [liveError, setLiveError] = useState(false);
  const [jurisdictionFilter, setJurisdictionFilter] = useState('ALL');
  const [dispatchStatus, setDispatchStatus] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setDispatchStatus(null);
    if (mode !== 'live') {
      setFleet(simulatedFleet());
      setLiveError(false);
      setLoading(false);
      return undefined;
    }
    setLoading(true);
    (async () => {
      try {
        const res = await fetch(LIVE_REGIONS_URL);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) {
          setFleet(Array.isArray(data) ? data : []);
          setLiveError(false);
        }
      } catch (e) {
        if (!cancelled) {
          setFleet([]);
          setLiveError(true);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [mode]);

  const plans = useMemo(() => Object.fromEntries(STREAMS.map((s) => [s.key, planStream(s, fleet)])), [fleet]);

  const extremes = useMemo(() => {
    if (fleet.length === 0) return null;
    const sorted = [...fleet].sort((a, b) => a.carbon - b.carbon);
    return { cleanest: sorted[0], dirtiest: sorted[sorted.length - 1] };
  }, [fleet]);

  const sourceLabel = mode === 'live' ? 'Live backend' : 'Simulated grid model';

  const handleDispatch = (stream) => {
    const plan = plans[stream.key];
    if (!plan) return;
    setDispatchStatus({
      stream: stream.title,
      region: plan.best.region.name,
      score: plan.best.score,
      summary: plan.summary,
      time: new Date().toLocaleTimeString(),
    });
  };

  const filteredFleet = fleet.filter((r) => {
    const codes = REGION_GROUPS[jurisdictionFilter];
    return !codes || codes.includes(regionCode(r.name));
  });

  const getCarbonBadge = (ci) => {
    if (typeof ci !== 'number') return <span style={{ color: 'var(--text-faint)' }}>—</span>;
    if (ci <= 100) return <span className="badge-clean">{ci.toFixed(0)} gCO2/kWh</span>;
    if (ci <= 400) return <span className="badge-moderate">{ci.toFixed(0)} gCO2/kWh</span>;
    return <span className="badge-dirty">{ci.toFixed(0)} gCO2/kWh</span>;
  };

  const globalPlan = plans.global_unconstrained;

  return (
    <div className="app-layout">
      <TopNavbar />

      <main className="main-content">
        <div className="page-header">
          <h1 className="page-title">Fleet & Workload Console</h1>
          <p className="page-subtitle">Carbon-aware multi-jurisdiction scheduling across the region fleet · {sourceLabel}</p>
        </div>

        {liveError && (
          <div className="card" style={{ borderColor: 'var(--dirty-border)', background: 'var(--dirty-bg)', padding: '1rem 1.5rem' }}>
            <strong style={{ color: 'var(--dirty)' }}>Live backend unreachable.</strong>{' '}
            Start the API on port 8001, or switch back to Simulated data in Dev Options.
          </div>
        )}

        {/* KPI Ribbon */}
        <div id="tour-kpis" className="kpi-ribbon">
          <div className="kpi-card">
            <div className="kpi-label">Regions reporting</div>
            <div className="kpi-val mono">{fleet.length || '—'}</div>
            <div className="kpi-meta">{sourceLabel}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Cleanest region now</div>
            <div className="kpi-val mono" style={{ color: 'var(--clean)' }}>
              {extremes ? `${extremes.cleanest.carbon.toFixed(0)} g` : '—'}
            </div>
            <div className="kpi-meta">{extremes ? extremes.cleanest.name : 'No data'}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Dirtiest region now</div>
            <div className="kpi-val mono" style={{ color: 'var(--dirty)' }}>
              {extremes ? `${extremes.dirtiest.carbon.toFixed(0)} g` : '—'}
            </div>
            <div className="kpi-meta">{extremes ? extremes.dirtiest.name : 'No data'}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Best spatial cut (global)</div>
            <div className="kpi-val mono" style={{ color: 'var(--primary)' }}>
              {globalPlan ? `${globalPlan.cutPct.toFixed(1)}%` : '—'}
            </div>
            <div className="kpi-meta">
              {globalPlan ? `${regionCode(globalPlan.best.region.name)} vs ${globalPlan.baseline.name} baseline` : 'No data'}
            </div>
          </div>
        </div>

        {/* Multi-Jurisdiction Workload Cards */}
        <div id="tour-dispatcher" className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Multi-Jurisdiction Workload Dispatcher</h2>
              <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
                Each stream is scored only over the regions its data-residency rules allow
              </p>
            </div>
          </div>

          <div className="jurisdiction-grid">
            {STREAMS.map((stream) => {
              const plan = plans[stream.key];
              return (
                <div key={stream.key} className="jurisdiction-card">
                  <div>
                    <span className="jurisdiction-badge">{stream.badge}</span>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem' }}>{stream.title}</h3>
                    <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)', marginBottom: '1.25rem', lineHeight: 1.6 }}>
                      {stream.blurb}
                    </p>
                    <div style={{ background: 'var(--bg-subtle)', padding: '1.1rem 1.25rem', borderRadius: 'var(--radius-sm)', marginBottom: '1.25rem', border: '1px solid var(--border)' }}>
                      {plan ? (
                        <>
                          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', fontSize: '0.95rem', marginBottom: '0.45rem' }}>
                            <span style={{ color: 'var(--text-faint)' }}>Baseline ({regionCode(plan.baseline.name)}):</span>
                            <span className="mono" style={{ color: 'var(--dirty)', fontWeight: 600 }}>{plan.baseline.carbon.toFixed(1)} gCO2</span>
                          </div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', fontSize: '0.95rem', marginBottom: '0.45rem' }}>
                            <span style={{ color: 'var(--text-faint)' }}>Best allowed ({regionCode(plan.best.region.name)}):</span>
                            <span className="mono" style={{ color: 'var(--clean)', fontWeight: 600 }}>{plan.best.region.carbon.toFixed(1)} gCO2</span>
                          </div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', fontSize: '1.05rem', fontWeight: 700, paddingTop: '0.35rem', borderTop: '1px solid var(--border)' }}>
                            <span style={{ color: 'var(--clean)' }}>Spatial carbon cut:</span>
                            <span className="mono" style={{ color: 'var(--clean)' }}>{plan.cutPct.toFixed(1)}%</span>
                          </div>
                          <div style={{ fontSize: '0.78rem', color: 'var(--text-faint)', marginTop: '0.5rem' }}>
                            {plan.poolSize} allowed regions · SLA ≤{DISPATCH_MAX_LATENCY_MS} ms
                          </div>
                        </>
                      ) : (
                        <span style={{ color: 'var(--text-faint)', fontSize: '0.9rem' }}>
                          {loading ? 'Loading fleet…' : 'No eligible region in this jurisdiction.'}
                        </span>
                      )}
                    </div>
                  </div>
                  <div>
                    <button
                      className="btn btn-primary"
                      style={{ width: '100%', justifyContent: 'center', fontSize: '1rem', padding: '0.85rem' }}
                      onClick={() => handleDispatch(stream)}
                      disabled={!plan}
                    >
                      Dispatch {stream.title.split(' ')[0]} Workload
                    </button>
                    {/* Result sits under the button that was pressed, so it's always in view. */}
                    {dispatchStatus?.stream === stream.title && (
                      <div
                        role="status"
                        style={{ marginTop: '0.9rem', padding: '0.85rem 1rem', background: 'var(--clean-bg)', border: '1px solid var(--clean-border)', borderRadius: 'var(--radius-sm)', fontSize: '0.88rem' }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '0.75rem', flexWrap: 'wrap' }}>
                          <strong style={{ color: 'var(--clean)' }}>Simulated dispatch → {dispatchStatus.region}</strong>
                          <button
                            onClick={() => setDispatchStatus(null)}
                            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', font: 'inherit', fontSize: '0.8rem', textDecoration: 'underline', padding: 0 }}
                          >
                            Dismiss
                          </button>
                        </div>
                        <div className="mono" style={{ color: 'var(--text-main)', marginTop: '0.3rem', fontSize: '0.8rem' }}>
                          score {dispatchStatus.score} · {dispatchStatus.time}
                        </div>
                        <div style={{ color: 'var(--text-muted)', marginTop: '0.3rem', lineHeight: 1.5 }}>
                          {dispatchStatus.summary} No cloud command was sent.
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Fleet Table */}
        <div id="tour-fleet-table" className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Region Fleet Telemetry</h2>
              <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
                Grid carbon intensity and network latency (measured from India) per region
              </p>
            </div>

            <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
              {['ALL', 'APAC', 'AMERICAS', 'EUROPE'].map((filter) => (
                <button
                  key={filter}
                  className={`btn ${jurisdictionFilter === filter ? 'btn-primary' : 'btn-outline'}`}
                  style={{ fontSize: '0.9rem', padding: '0.45rem 0.95rem' }}
                  onClick={() => setJurisdictionFilter(filter)}
                >
                  {filter}
                </button>
              ))}
            </div>
          </div>

          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Region / Datacenter</th>
                  <th>Grid Zone</th>
                  <th>Latency</th>
                  <th>Current Carbon Intensity</th>
                  <th>Data Source</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan="5" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                      Connecting to CADSS backend...
                    </td>
                  </tr>
                ) : filteredFleet.length === 0 ? (
                  <tr>
                    <td colSpan="5" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                      {liveError ? 'No live data — backend unreachable.' : 'No regions in this group.'}
                    </td>
                  </tr>
                ) : filteredFleet.map((r) => (
                  <tr key={r.name}>
                    <td>
                      <strong style={{ fontSize: '1.05rem' }}>{r.name}</strong>
                    </td>
                    <td><span className="mono" style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>{r.zone || '—'}</span></td>
                    <td className="mono" style={{ fontSize: '0.95rem' }}>{typeof r.latency === 'number' ? `${r.latency} ms` : '—'}</td>
                    <td>{getCarbonBadge(r.carbon ?? r.carbon_intensity)}</td>
                    <td>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.45rem', color: mode === 'live' ? 'var(--clean)' : 'var(--text-muted)', fontSize: '0.95rem', fontWeight: 600 }}>
                        {mode === 'live' && <span className="status-dot"></span>}
                        {mode === 'live' ? 'Live' : 'Simulated'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}

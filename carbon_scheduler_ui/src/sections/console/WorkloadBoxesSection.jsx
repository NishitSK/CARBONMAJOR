import React, { useState } from 'react';
import { Box, Plus, Trash2, CheckCircle, Zap, ArrowRight, Globe, Hand, Wand2, Cpu } from 'lucide-react';

export default function WorkloadBoxesSection({
  workloads = [],
  servers = [],
  zones = [],
  workloadResults = {},
  zoneCarbon = {},
  onAddWorkload,
  onRemoveWorkload,
  onUpdateWorkload,
  onSelectActiveServer,
  onSwitchRegion,
  onSetSwitchingMode
}) {
  const [newName, setNewName] = useState('');
  const [newType, setNewType] = useState('latency-sensitive');
  const [newSla, setNewSla] = useState(200);

  const handleAdd = (e) => {
    e.preventDefault();
    if (!newName.trim()) return;
    onAddWorkload(newName.trim(), newType, parseFloat(newSla));
    setNewName('');
  };

  const serverById = Object.fromEntries(servers.map(s => [s.id, s]));

  return (
    <section style={{ marginBottom: '1.5rem' }}>
      <div className="panel-title" style={{ marginBottom: '1rem', justifyContent: 'space-between', display: 'flex', alignItems: 'center' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Box size={18} color="var(--accent)" /> Active Workloads & Load Boxes
        </span>
        <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
          {workloads.length} workload{workloads.length === 1 ? '' : 's'} running
        </span>
      </div>

      {/* Add New Workload Form */}
      <form onSubmit={handleAdd} className="glass-panel" style={{ padding: '1rem', marginBottom: '1rem', display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
        <div style={{ flex: 1, minWidth: '180px' }}>
          <input
            type="text"
            placeholder="New load name (e.g. Payment Gateway)"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="fleet-input"
            style={{ width: '100%' }}
          />
        </div>
        <select
          value={newType}
          onChange={(e) => setNewType(e.target.value)}
          className="fleet-select"
          style={{ fontSize: '0.78rem' }}
        >
          <option value="latency-sensitive">Latency-Sensitive</option>
          <option value="delay-tolerant">Delay-Tolerant</option>
        </select>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>SLA:</span>
          <input
            type="number"
            value={newSla}
            onChange={(e) => setNewSla(e.target.value)}
            min={20}
            max={500}
            className="fleet-input"
            style={{ width: '70px', padding: '4px 6px' }}
          />
          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>ms</span>
        </div>
        <button type="submit" className="ghost-btn ghost-btn-on" disabled={!newName.trim()}>
          <Plus size={13} /> Add Load Box
        </button>
      </form>

      {/* Workload Cards / Separate Boxes Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.2rem' }}>
        {workloads.map(w => {
          const activeServer = serverById[w.activeServerId] || servers[0] || null;
          const wResult = workloadResults[w.id] || {};
          const recommendedServerId = wResult.recommendedServerId;
          const recommendedServer = serverById[recommendedServerId] || null;
          const currentCi = activeServer ? zoneCarbon[activeServer.zoneName] : null;

          const showRecommendation =
            (w.switchingMode || 'manual') === 'manual' &&
            recommendedServer &&
            recommendedServer.id !== activeServer?.id;

          return (
            <div key={w.id} className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '12px', border: '1px solid rgba(94, 230, 200, 0.25)', position: 'relative' }}>
              {/* Workload Box Header */}
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '8px' }}>
                <div>
                  <div style={{ fontSize: '1.05rem', fontWeight: 700, fontFamily: "'Space Grotesk', sans-serif" }}>
                    {w.name}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px' }}>
                    <span className="mini-badge" style={{ background: w.type === 'latency-sensitive' ? 'rgba(94, 230, 200, 0.15)' : 'rgba(255, 180, 50, 0.15)', color: w.type === 'latency-sensitive' ? 'var(--accent)' : '#ffb432', borderColor: 'transparent' }}>
                      {w.type}
                    </span>
                    <span className="mono" style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                      SLA: {w.maxLatency}ms
                    </span>
                  </div>
                </div>
                {workloads.length > 1 && (
                  <button className="icon-btn icon-btn-danger" onClick={() => onRemoveWorkload(w.id)} title="Delete load box">
                    <Trash2 size={13} />
                  </button>
                )}
              </div>

              {/* Recommendation Banner if lower carbon server available */}
              {showRecommendation && (
                <div className="recommendation-banner" style={{ margin: 0, padding: '8px 10px', fontSize: '0.8rem' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Zap size={14} color="var(--accent)" />
                    Move to <strong>{recommendedServer.label}</strong>
                  </span>
                  <button
                    className="ghost-btn ghost-btn-on"
                    style={{ padding: '2px 8px', fontSize: '0.72rem' }}
                    onClick={() => onSelectActiveServer(w.id, recommendedServer.id)}
                  >
                    Apply Switch
                  </button>
                </div>
              )}

              {/* Current Active Server Details Box */}
              <div style={{ background: 'rgba(0, 0, 0, 0.25)', padding: '10px 12px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <CheckCircle size={14} color="var(--accent)" />
                    <span className="mono" style={{ fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.05em', color: 'var(--accent)', textTransform: 'uppercase' }}>
                      Active Location
                    </span>
                  </div>
                  {currentCi !== undefined && currentCi !== null && (
                    <span className="mono" style={{ fontSize: '0.78rem', color: '#5EE6C8', fontWeight: 700 }}>
                      {currentCi} gCO₂/kWh
                    </span>
                  )}
                </div>

                {activeServer ? (
                  <>
                    <div style={{ fontSize: '0.98rem', fontWeight: 600 }}>{activeServer.label}</div>
                    <div style={{ fontSize: '0.76rem', color: 'var(--text-dim)', marginTop: '2px' }}>{activeServer.zoneName}</div>
                  </>
                ) : (
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-faint)' }}>
                    No server assigned -- select a server or region below.
                  </div>
                )}
              </div>

              {/* Manual Switching & Region Controls */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px' }}>
                  <span style={{ fontSize: '0.74rem', color: 'var(--text-dim)' }}>Switch Server:</span>
                  <select
                    value={activeServer?.id || ''}
                    onChange={(e) => onSelectActiveServer(w.id, e.target.value)}
                    className="fleet-select"
                    style={{ fontSize: '0.75rem', padding: '2px 6px', height: '26px', width: '180px' }}
                    disabled={servers.length === 0}
                  >
                    {servers.map(s => (
                      <option key={s.id} value={s.id}>
                        {s.label} ({s.zoneName})
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Globe size={13} color="var(--accent)" />
                    <span style={{ fontSize: '0.74rem', color: 'var(--text-dim)' }}>Switch Region:</span>
                  </div>
                  <select
                    value={activeServer?.zoneName || ''}
                    onChange={(e) => onSwitchRegion(w.id, e.target.value)}
                    className="fleet-select"
                    style={{ fontSize: '0.75rem', padding: '2px 6px', height: '26px', width: '180px' }}
                    disabled={zones.length === 0}
                  >
                    <option value="" disabled>Select region...</option>
                    {zones.map(z => (
                      <option key={z.name} value={z.name}>
                        {z.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '4px' }}>
                  <span style={{ fontSize: '0.74rem', color: 'var(--text-dim)' }}>Switching Mode:</span>
                  <div className="toggle-group">
                    <button
                      onClick={() => onSetSwitchingMode(w.id, 'manual')}
                      className={`toggle-btn ${ (w.switchingMode || 'manual') === 'manual' ? 'on' : ''}`}
                      style={{ padding: '2px 8px', fontSize: '0.72rem' }}
                    >
                      <Hand size={11} /> Manual
                    </button>
                    <button
                      onClick={() => onSetSwitchingMode(w.id, 'auto')}
                      className={`toggle-btn ${ (w.switchingMode || 'manual') === 'auto' ? 'on' : ''}`}
                      style={{ padding: '2px 8px', fontSize: '0.72rem' }}
                    >
                      <Wand2 size={11} /> Auto
                    </button>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

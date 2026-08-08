import React, { useState } from 'react';
import { FolderKanban, Plus, Trash2, CheckCircle, Zap, Globe, Hand, Wand2, Shield, Lock, AlertTriangle, Sliders, Activity } from 'lucide-react';
import { GEO_SCOPES, isZoneInScope } from '../../hooks/useConsoleClock';

export default function ProgramBoxesSection({
  programs = [],
  workloads = [],
  servers = [],
  zones = [],
  workloadResults = {},
  zoneCarbon = {},
  onAddProgram,
  onRemoveProgram,
  onUpdateProgram,
  onAddWorkloadToProgram,
  onRemoveWorkload,
  onUpdateWorkload,
  onSelectActiveServer,
  onSwitchRegion,
  onSetSwitchingMode
}) {
  const [newProgramName, setNewProgramName] = useState('');
  const [newProgramScope, setNewProgramScope] = useState('World');

  const [newLoadNameByProgram, setNewLoadNameByProgram] = useState({});
  const [newLoadTypeByProgram, setNewLoadTypeByProgram] = useState({});
  const [newLoadSlaByProgram, setNewLoadSlaByProgram] = useState({});
  const [showControlsMap, setShowControlsMap] = useState({});

  const handleAddProgram = (e) => {
    e.preventDefault();
    if (!newProgramName.trim()) return;
    onAddProgram(newProgramName.trim(), newProgramScope);
    setNewProgramName('');
  };

  const handleAddLoad = (e, programId) => {
    e.preventDefault();
    const name = newLoadNameByProgram[programId] || '';
    const type = newLoadTypeByProgram[programId] || 'latency-sensitive';
    const sla = newLoadSlaByProgram[programId] || 200;
    if (!name.trim()) return;

    onAddWorkloadToProgram(programId, name.trim(), type, parseFloat(sla), { carbon: 0.4, latency: 0.3, resources: 0.3 });
    setNewLoadNameByProgram({ ...newLoadNameByProgram, [programId]: '' });
  };

  const toggleControls = (workloadId) => {
    setShowControlsMap(prev => ({ ...prev, [workloadId]: !prev[workloadId] }));
  };

  const serverById = Object.fromEntries(servers.map(s => [s.id, s]));

  return (
    <section style={{ marginBottom: '1.8rem' }}>
      <div className="panel-title" style={{ marginBottom: '1rem', justifyContent: 'space-between', display: 'flex', alignItems: 'center' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <FolderKanban size={20} color="var(--accent)" /> Projects & Program Boxes (Geographic Scope & Score Controlled)
        </span>
        <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
          {programs.length} Program Box{programs.length === 1 ? '' : 'es'}
        </span>
      </div>

      {/* Add New Program Box Form */}
      <form onSubmit={handleAddProgram} className="glass-panel" style={{ padding: '1rem', marginBottom: '1.2rem', display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', background: 'rgba(20, 28, 43, 0.65)' }}>
        <div style={{ flex: 1, minWidth: '200px' }}>
          <input
            type="text"
            placeholder="New project name (e.g. EU Banking Gateway)"
            value={newProgramName}
            onChange={(e) => setNewProgramName(e.target.value)}
            className="fleet-input"
            style={{ width: '100%' }}
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Globe size={14} color="var(--accent)" />
          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Geo Scope:</span>
          <select
            value={newProgramScope}
            onChange={(e) => setNewProgramScope(e.target.value)}
            className="fleet-select"
            style={{ fontSize: '0.78rem' }}
          >
            {Object.entries(GEO_SCOPES).map(([key, def]) => (
              <option key={key} value={key}>
                {def.icon} {def.label}
              </option>
            ))}
          </select>
        </div>
        <button type="submit" className="ghost-btn ghost-btn-on" disabled={!newProgramName.trim()}>
          <Plus size={13} /> Create Project Box
        </button>
      </form>

      {/* Render Program Boxes */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {programs.map(program => {
          const programWorkloads = workloads.filter(w => w.programId === program.id);
          const scopeDef = GEO_SCOPES[program.geoScope] || GEO_SCOPES['World'];

          // STRICT FILTERING: Only zones and servers belonging to THIS geographic scope
          const scopedZones = zones.filter(z => isZoneInScope(z.name, program.geoScope));
          const scopedServers = servers.filter(s => isZoneInScope(s.zoneName, program.geoScope));

          return (
            <div
              key={program.id}
              className="glass-panel"
              style={{
                padding: '1.25rem',
                border: '1px solid rgba(94, 230, 200, 0.3)',
                background: 'rgba(15, 22, 35, 0.75)',
                boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.37)'
              }}
            >
              {/* Program Box Header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid rgba(255, 255, 255, 0.1)', paddingBottom: '0.9rem', marginBottom: '1rem', flexWrap: 'wrap', gap: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Shield size={20} color="var(--accent)" />
                  <div>
                    <div style={{ fontSize: '1.2rem', fontWeight: 700, fontFamily: "'Space Grotesk', sans-serif" }}>
                      {program.name}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
                      <span>Belonging workloads: {programWorkloads.length}</span>
                    </div>
                  </div>
                </div>

                {/* Geographic Scope Selector for this Program Box */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(0, 0, 0, 0.3)', padding: '4px 10px', borderRadius: '6px', border: '1px solid rgba(94, 230, 200, 0.2)' }}>
                    <Lock size={13} color="var(--accent)" />
                    <span style={{ fontSize: '0.74rem', color: 'var(--text-dim)' }}>Allowed Region Scope:</span>
                    <select
                      value={program.geoScope || 'World'}
                      onChange={(e) => onUpdateProgram(program.id, { geoScope: e.target.value })}
                      className="fleet-select"
                      style={{ fontSize: '0.78rem', padding: '2px 6px', fontWeight: 600, color: 'var(--accent)' }}
                    >
                      {Object.entries(GEO_SCOPES).map(([key, def]) => (
                        <option key={key} value={key}>
                          {def.icon} {key}
                        </option>
                      ))}
                    </select>
                  </div>

                  {programs.length > 1 && (
                    <button className="icon-btn icon-btn-danger" onClick={() => onRemoveProgram(program.id)} title="Delete Project Box">
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              </div>

              {/* Add Load to this Program Form */}
              <form onSubmit={(e) => handleAddLoad(e, program.id)} style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '1rem', alignItems: 'center', background: 'rgba(0, 0, 0, 0.2)', padding: '8px 12px', borderRadius: '8px' }}>
                <input
                  type="text"
                  placeholder="Add workload to project (e.g. Auth Service)"
                  value={newLoadNameByProgram[program.id] || ''}
                  onChange={(e) => setNewLoadNameByProgram({ ...newLoadNameByProgram, [program.id]: e.target.value })}
                  className="fleet-input"
                  style={{ flex: 1, minWidth: '160px', fontSize: '0.8rem' }}
                />
                <select
                  value={newLoadTypeByProgram[program.id] || 'latency-sensitive'}
                  onChange={(e) => setNewLoadTypeByProgram({ ...newLoadTypeByProgram, [program.id]: e.target.value })}
                  className="fleet-select"
                  style={{ fontSize: '0.75rem' }}
                >
                  <option value="latency-sensitive">Latency-Sensitive</option>
                  <option value="delay-tolerant">Delay-Tolerant</option>
                </select>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>SLA:</span>
                  <input
                    type="number"
                    value={newLoadSlaByProgram[program.id] || 200}
                    onChange={(e) => setNewLoadSlaByProgram({ ...newLoadSlaByProgram, [program.id]: e.target.value })}
                    min={20}
                    max={500}
                    className="fleet-input"
                    style={{ width: '65px', padding: '2px 4px', fontSize: '0.78rem' }}
                  />
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>ms</span>
                </div>
                <button type="submit" className="ghost-btn ghost-btn-on" style={{ padding: '4px 10px', fontSize: '0.75rem' }} disabled={!(newLoadNameByProgram[program.id] || '').trim()}>
                  <Plus size={12} /> Add Load
                </button>
              </form>

              {/* Workload Cards inside this Program Box */}
              {programWorkloads.length === 0 ? (
                <p style={{ color: 'var(--text-faint)', fontSize: '0.82rem', margin: '0.5rem 0' }}>
                  No workloads in this project yet -- add one above.
                </p>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.2rem' }}>
                  {programWorkloads.map(w => {
                    const activeServer = serverById[w.activeServerId] || scopedServers[0] || servers[0] || null;
                    const wResult = workloadResults[w.id] || {};
                    const recommendedServerId = wResult.recommendedServerId;
                    const recommendedServer = serverById[recommendedServerId] || null;
                    const topZoneName = wResult.recommendedZoneName;
                    const currentCi = activeServer ? zoneCarbon[activeServer.zoneName] : null;

                    const rawWeights = w.weights || {};
                    const wWeights = {
                      carbon: typeof rawWeights.carbon === 'number' ? rawWeights.carbon : 0.4,
                      latency: typeof rawWeights.latency === 'number' ? rawWeights.latency : 0.3,
                      resources: typeof rawWeights.resources === 'number' ? rawWeights.resources : 0.3,
                    };

                    const activeScore = wResult.activeServerScore;
                    const activeMeta = wResult.activeServerMeta || {};
                    const isControlsOpen = !!showControlsMap[w.id];

                    const showRecommendation =
                      (w.switchingMode || 'manual') === 'manual' &&
                      recommendedServer &&
                      recommendedServer.id !== activeServer?.id;

                    const isCurrentServerInScope = activeServer ? isZoneInScope(activeServer.zoneName, program.geoScope) : true;

                    return (
                      <div key={w.id} className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '10px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
                        {/* Workload Card Title */}
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <div>
                            <div style={{ fontSize: '0.98rem', fontWeight: 700, fontFamily: "'Space Grotesk', sans-serif" }}>
                              {w.name}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '3px' }}>
                              <span className="mini-badge" style={{ background: w.type === 'latency-sensitive' ? 'rgba(94, 230, 200, 0.15)' : 'rgba(255, 180, 50, 0.15)', color: w.type === 'latency-sensitive' ? 'var(--accent)' : '#ffb432', borderColor: 'transparent' }}>
                                {w.type}
                              </span>
                              <span className="mono" style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>
                                SLA: {w.maxLatency}ms
                              </span>
                            </div>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <button
                              className={`icon-btn ${isControlsOpen ? 'icon-btn-active' : ''}`}
                              onClick={() => toggleControls(w.id)}
                              title="Toggle Scoring Controls for this load"
                            >
                              <Sliders size={13} color={isControlsOpen ? 'var(--accent)' : 'currentColor'} />
                            </button>
                            <button className="icon-btn icon-btn-danger" onClick={() => onRemoveWorkload(w.id)} title="Delete workload">
                              <Trash2 size={12} />
                            </button>
                          </div>
                        </div>

                        {/* Geo Scope Constraint Badge */}
                        <div style={{ fontSize: '0.7rem', color: 'var(--accent)', background: 'rgba(94, 230, 200, 0.08)', padding: '3px 8px', borderRadius: '4px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          <span>{scopeDef.icon}</span> Restricted to <strong>{program.geoScope}</strong>
                        </div>

                        {/* Expandable Per-Load Scoring Controls Slider Settings */}
                        {isControlsOpen && (
                          <div style={{ background: 'rgba(0, 0, 0, 0.4)', padding: '10px', borderRadius: '8px', border: '1px solid rgba(94, 230, 200, 0.2)', marginTop: '2px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            <div style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <Sliders size={12} /> Customize Score Controls for "{w.name}"
                            </div>
                            
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem' }}>
                                <span>Carbon Weight:</span>
                                <span className="mono" style={{ color: 'var(--accent)' }}>{(wWeights.carbon * 100).toFixed(0)}%</span>
                              </div>
                              <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.05"
                                value={wWeights.carbon}
                                onChange={(e) => onUpdateWorkload(w.id, { weights: { ...wWeights, carbon: parseFloat(e.target.value) } })}
                              />
                            </div>

                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem' }}>
                                <span>Latency Weight:</span>
                                <span className="mono" style={{ color: 'var(--accent)' }}>{(wWeights.latency * 100).toFixed(0)}%</span>
                              </div>
                              <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.05"
                                value={wWeights.latency}
                                onChange={(e) => onUpdateWorkload(w.id, { weights: { ...wWeights, latency: parseFloat(e.target.value) } })}
                              />
                            </div>

                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem' }}>
                                <span>Resource Weight:</span>
                                <span className="mono" style={{ color: 'var(--accent)' }}>{(wWeights.resources * 100).toFixed(0)}%</span>
                              </div>
                              <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.05"
                                value={wWeights.resources}
                                onChange={(e) => onUpdateWorkload(w.id, { weights: { ...wWeights, resources: parseFloat(e.target.value) } })}
                              />
                            </div>

                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem' }}>
                                <span>SLA Max Latency:</span>
                                <span className="mono" style={{ color: 'var(--accent)' }}>{w.maxLatency} ms</span>
                              </div>
                              <input
                                type="range"
                                min="20"
                                max="400"
                                step="10"
                                value={w.maxLatency}
                                onChange={(e) => onUpdateWorkload(w.id, { maxLatency: parseInt(e.target.value) })}
                              />
                            </div>
                          </div>
                        )}

                        {/* Alert if current location is out of scope */}
                        {!isCurrentServerInScope && (
                          <div style={{ background: 'rgba(255, 107, 107, 0.15)', border: '1px solid #ff6b6b', borderRadius: '6px', padding: '6px 8px', fontSize: '0.74rem', color: '#ff6b6b', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <AlertTriangle size={13} />
                              <span>Outside {program.geoScope} scope</span>
                            </div>
                            {topZoneName && (
                              <button
                                className="ghost-btn ghost-btn-on"
                                style={{ padding: '2px 6px', fontSize: '0.7rem' }}
                                onClick={() => onSwitchRegion(w.id, topZoneName)}
                              >
                                Switch to {program.geoScope}
                              </button>
                            )}
                          </div>
                        )}

                        {/* Recommendation Banner within Scope */}
                        {showRecommendation && isCurrentServerInScope && (
                          <div className="recommendation-banner" style={{ margin: 0, padding: '6px 8px', fontSize: '0.78rem' }}>
                            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <Zap size={13} color="var(--accent)" />
                              Move to <strong>{recommendedServer.label}</strong>
                            </span>
                            <button
                              className="ghost-btn ghost-btn-on"
                              style={{ padding: '2px 6px', fontSize: '0.7rem' }}
                              onClick={() => onSelectActiveServer(w.id, recommendedServer.id)}
                            >
                              Apply Switch
                            </button>
                          </div>
                        )}

                        {/* Active Location Info & Real-Time Simulation Score Monitor */}
                        <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '10px', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <CheckCircle size={12} color="var(--accent)" />
                              <span className="mono" style={{ fontSize: '0.65rem', fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase' }}>
                                Active Location
                              </span>
                            </div>
                            {currentCi !== undefined && currentCi !== null && (
                              <span className="mono" style={{ fontSize: '0.75rem', color: '#5EE6C8', fontWeight: 700 }}>
                                {currentCi} gCO₂/kWh
                              </span>
                            )}
                          </div>

                          {activeServer ? (
                            <>
                              <div style={{ fontSize: '0.9rem', fontWeight: 600 }}>{activeServer.label}</div>
                              <div style={{ fontSize: '0.72rem', color: isCurrentServerInScope ? 'var(--text-dim)' : '#ff6b6b' }}>
                                {activeServer.zoneName} {!isCurrentServerInScope && '(Out of Scope)'}
                              </div>
                            </>
                          ) : (
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-faint)' }}>
                              No server assigned yet.
                            </div>
                          )}

                          {/* SIMULATION REAL-TIME SCORE READOUT */}
                          <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px dashed rgba(255, 255, 255, 0.1)', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.72rem' }}>
                              <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-dim)' }}>
                                <Activity size={11} color="var(--accent)" /> Configured Score Weights:
                              </span>
                              <span className="mono" style={{ fontSize: '0.68rem', color: 'var(--accent)' }}>
                                C:{(wWeights.carbon*100).toFixed(0)}% · L:{(wWeights.latency*100).toFixed(0)}% · R:{(wWeights.resources*100).toFixed(0)}%
                              </span>
                            </div>

                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.72rem' }}>
                              <span style={{ color: 'var(--text-dim)' }}>Simulated Composite Score:</span>
                              <span className="mono" style={{ fontWeight: 700, color: (typeof activeScore === 'number') ? '#5EE6C8' : 'var(--text-faint)' }}>
                                {(typeof activeScore === 'number') ? activeScore.toFixed(4) : (wResult.activeServerRejected ? `Rejected (${wResult.rejectReason || 'SLA'})` : 'Evaluating...')}
                              </span>
                            </div>

                            {/* Detailed Normalized Score Components */}
                            {activeMeta && (
                              <div style={{ background: 'rgba(0, 0, 0, 0.25)', padding: '6px', borderRadius: '4px', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '4px', fontSize: '0.68rem', textAlign: 'center' }}>
                                <div>
                                  <div style={{ color: 'var(--text-dim)' }}>Carbon (C)</div>
                                  <div className="mono" style={{ fontWeight: 600, color: 'var(--accent)' }}>
                                    {typeof activeMeta.c_norm === 'number' ? activeMeta.c_norm.toFixed(2) : '-'}
                                  </div>
                                </div>
                                <div>
                                  <div style={{ color: 'var(--text-dim)' }}>Latency (L)</div>
                                  <div className="mono" style={{ fontWeight: 600, color: 'var(--accent)' }}>
                                    {typeof activeMeta.l_norm === 'number' ? activeMeta.l_norm.toFixed(2) : '-'}
                                  </div>
                                </div>
                                <div>
                                  <div style={{ color: 'var(--text-dim)' }}>Resource (R)</div>
                                  <div className="mono" style={{ fontWeight: 600, color: 'var(--accent)' }}>
                                    {typeof activeMeta.r_penalty === 'number' ? activeMeta.r_penalty.toFixed(2) : '-'}
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Controls (Outside regions and servers strictly excluded from dropdowns!) */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.73rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <span style={{ color: 'var(--text-dim)' }}>Switch Server:</span>
                            <select
                              value={activeServer?.id || ''}
                              onChange={(e) => onSelectActiveServer(w.id, e.target.value)}
                              className="fleet-select"
                              style={{ fontSize: '0.72rem', padding: '2px 4px', height: '24px', width: '165px' }}
                              disabled={scopedServers.length === 0}
                            >
                              {scopedServers.length === 0 ? (
                                <option value="" disabled>No servers in {program.geoScope}</option>
                              ) : (
                                scopedServers.map(s => (
                                  <option key={s.id} value={s.id}>
                                    {s.label} ({s.zoneName})
                                  </option>
                                ))
                              )}
                            </select>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <Globe size={11} color="var(--accent)" />
                              <span style={{ color: 'var(--text-dim)' }}>Switch Region ({program.geoScope}):</span>
                            </div>
                            <select
                              value={activeServer?.zoneName || ''}
                              onChange={(e) => onSwitchRegion(w.id, e.target.value)}
                              className="fleet-select"
                              style={{ fontSize: '0.72rem', padding: '2px 4px', height: '24px', width: '165px' }}
                            >
                              <option value="" disabled>Select {program.geoScope} region...</option>
                              {scopedZones.map(z => (
                                <option key={z.name} value={z.name}>
                                  {z.name}
                                </option>
                              ))}
                            </select>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '2px' }}>
                            <span style={{ color: 'var(--text-dim)' }}>Switching Mode:</span>
                            <div className="toggle-group">
                              <button
                                onClick={() => onSetSwitchingMode(w.id, 'manual')}
                                className={`toggle-btn ${ (w.switchingMode || 'manual') === 'manual' ? 'on' : ''}`}
                                style={{ padding: '1px 6px', fontSize: '0.7rem' }}
                              >
                                <Hand size={10} /> Manual
                              </button>
                              <button
                                onClick={() => onSetSwitchingMode(w.id, 'auto')}
                                className={`toggle-btn ${ (w.switchingMode || 'manual') === 'auto' ? 'on' : ''}`}
                                style={{ padding: '1px 6px', fontSize: '0.7rem' }}
                              >
                                <Wand2 size={10} /> Auto
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

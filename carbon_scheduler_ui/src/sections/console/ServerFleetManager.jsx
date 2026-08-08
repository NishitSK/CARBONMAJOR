import React, { useState } from 'react';
import { Server, Plus, Trash2, Pencil, Check, X } from 'lucide-react';

// Add/remove/rename rows for the client's own server fleet. Each server is
// a { label, zoneName } pair -- the zone picker only offers real electricity
// zones (from GET /regions/zones) so carbon data for it stays real.
export default function ServerFleetManager({ servers, zones, zonesLoading, activeServerId, onSelectActive, onAdd, onRemove, onRename }) {
  const [label, setLabel] = useState('');
  const [zoneName, setZoneName] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editLabel, setEditLabel] = useState('');

  const effectiveZone = zoneName || zones[0]?.name || '';

  const handleAdd = (e) => {
    e.preventDefault();
    if (!label.trim() || !effectiveZone) return;
    onAdd(label.trim(), effectiveZone);
    setLabel('');
  };

  const startEdit = (sv) => {
    setEditingId(sv.id);
    setEditLabel(sv.label);
  };

  const commitEdit = (id) => {
    if (editLabel.trim()) onRename(id, editLabel.trim());
    setEditingId(null);
  };

  return (
    <section className="glass-panel">
      <div className="panel-title" style={{ marginBottom: '1rem' }}>
        <Server size={16} color="var(--accent)" /> Your servers
      </div>

      <form onSubmit={handleAdd} className="fleet-add-row">
        <input
          type="text"
          placeholder="Server label (e.g. prod-api-1)"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className="fleet-input"
        />
        <select
          value={effectiveZone}
          onChange={(e) => setZoneName(e.target.value)}
          disabled={zonesLoading || zones.length === 0}
          className="fleet-select"
        >
          {zones.map(z => (
            <option key={z.name} value={z.name}>{z.name}</option>
          ))}
        </select>
        <button type="submit" className="ghost-btn ghost-btn-on" disabled={!label.trim() || zonesLoading}>
          <Plus size={13} /> Add server
        </button>
      </form>

      {servers.length === 0 ? (
        <p style={{ color: 'var(--text-faint)', fontSize: '0.82rem', marginTop: '1rem' }}>
          No servers yet -- add one above to start building your fleet.
        </p>
      ) : (
        <div className="fleet-list">
          {servers.map(sv => (
            <div key={sv.id} className="fleet-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              {editingId === sv.id ? (
                <>
                  <input
                    type="text"
                    value={editLabel}
                    onChange={(e) => setEditLabel(e.target.value)}
                    className="fleet-input"
                    autoFocus
                  />
                  <button className="icon-btn" onClick={() => commitEdit(sv.id)} title="Save"><Check size={14} /></button>
                  <button className="icon-btn" onClick={() => setEditingId(null)} title="Cancel"><X size={14} /></button>
                </>
              ) : (
                <>
                  <div className="fleet-row-label">
                    <span className="fleet-row-name">{sv.label}</span>
                    <span className="fleet-row-zone mono">{sv.zoneName}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {sv.id === activeServerId ? (
                      <span className="mini-badge" style={{ background: 'rgba(94, 230, 200, 0.15)', color: 'var(--accent)', border: '1px solid var(--accent)' }}>Active</span>
                    ) : (
                      <button className="ghost-btn" style={{ padding: '2px 8px', fontSize: '0.72rem' }} onClick={() => onSelectActive(sv.id)}>Switch to</button>
                    )}
                    <button className="icon-btn" onClick={() => startEdit(sv)} title="Rename"><Pencil size={13} /></button>
                    <button className="icon-btn icon-btn-danger" onClick={() => onRemove(sv.id)} title="Remove"><Trash2 size={13} /></button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

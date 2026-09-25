import React, { useEffect, useState } from 'react';
import { Server, Plus, Trash2 } from 'lucide-react';

// The user's own servers. Whichever regions they sit in become the candidate
// pool for scoring; an empty fleet leaves every region in play.
export default function FleetPanel({ servers, regionNames, rejectedNames = [], onAdd, onRemove, onChangeZone, onLoadExample, onClear }) {
  const [label, setLabel] = useState('');
  const [zone, setZone] = useState('');

  useEffect(() => {
    if (!zone && regionNames.length > 0) setZone(regionNames[0]);
  }, [regionNames, zone]);

  const submit = (e) => {
    e.preventDefault();
    if (!zone) return;
    onAdd(label.trim() || `server-${zone.split(' ')[0]}`, zone);
    setLabel('');
  };

  const regionsUsed = new Set(servers.map((s) => s.zoneName));

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Server size={18} /> Your server fleet
          </h2>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
            {servers.length === 0
              ? 'No servers yet — planning mode: every region counts as a possible location, and placements are proposals. Add servers to rank only the regions you actually run in.'
              : `${servers.length} server${servers.length === 1 ? '' : 's'} across ${regionsUsed.size} region${regionsUsed.size === 1 ? '' : 's'} — only these regions are scored.`}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {servers.length === 0 ? (
            <button className="btn btn-outline" style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }} onClick={onLoadExample}>
              Load example fleet
            </button>
          ) : (
            <button className="btn btn-outline" style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }} onClick={onClear}>
              Remove all
            </button>
          )}
        </div>
      </div>

      <form onSubmit={submit} style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', alignItems: 'center', marginBottom: servers.length ? '1rem' : 0 }}>
        <input
          id="fleet-new-name"
          className="fleet-input"
          placeholder="Server name (optional)"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
        />
        <select id="fleet-new-region" className="fleet-select" value={zone} onChange={(e) => setZone(e.target.value)}>
          {regionNames.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
        <button type="submit" className="btn btn-primary" style={{ fontSize: '0.85rem' }} disabled={!zone}>
          <Plus size={14} /> Add server
        </button>
      </form>

      {servers.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {servers.map((sv) => (
            <div key={sv.id} className="fleet-row">
              <div className="fleet-row-label">
                <span className="fleet-row-name">
                  {sv.label}
                  {rejectedNames.includes(sv.zoneName) && (
                    <span style={{ marginLeft: '0.5rem', fontSize: '0.68rem', fontWeight: 700, color: 'var(--dirty)' }}>over SLA</span>
                  )}
                </span>
                <span className="fleet-row-zone">{sv.zoneName}</span>
              </div>
              <select
                className="fleet-select"
                value={sv.zoneName}
                onChange={(e) => onChangeZone(sv.id, e.target.value)}
                aria-label={`Region for ${sv.label}`}
              >
                {regionNames.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
              <button
                className="btn btn-outline"
                style={{ fontSize: '0.78rem', padding: '0.35rem 0.7rem', color: 'var(--dirty)', borderColor: 'var(--dirty-border)' }}
                onClick={() => onRemove(sv.id)}
                title={`Remove ${sv.label}`}
                aria-label={`Remove ${sv.label}`}
              >
                <Trash2 size={14} /> Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

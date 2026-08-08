import React from 'react';
import { CheckCircle, ArrowRight, Zap, Globe } from 'lucide-react';

// Shows which of the client's own servers is currently active. In manual
// mode, when the scheduler's real-time recommendation differs from the
// active server, a banner offers to apply the switch -- nothing moves until
// the client clicks it. In auto mode the switch has already happened by the
// time this renders, so there's nothing to approve.
export default function ActiveServerPanel({
  activeServer,
  recommendedServer,
  switchingMode,
  servers = [],
  zones = [],
  onApply,
  onSelectActive,
  onChangeRegion
}) {
  const showRecommendation =
    switchingMode === 'manual' &&
    recommendedServer &&
    recommendedServer.id !== activeServer?.id;

  return (
    <>
      {showRecommendation && (
        <div className="recommendation-banner">
          <span style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.86rem' }}>
            <Zap size={15} color="var(--accent)" />
            Move to <strong>{recommendedServer.label}</strong> <ArrowRight size={13} /> lower carbon right now
          </span>
          <button className="ghost-btn ghost-btn-on" onClick={onApply}>Apply switch</button>
        </div>
      )}

      <section className="glass-panel active-server-panel">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircle size={15} color="var(--accent)" />
            <span className="mono" style={{ fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.05em', color: 'var(--accent)', textTransform: 'uppercase' }}>
              Active server
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            {servers.length > 1 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Server:</span>
                <select
                  value={activeServer?.id || ''}
                  onChange={(e) => onSelectActive && onSelectActive(e.target.value)}
                  className="fleet-select"
                  style={{ fontSize: '0.75rem', padding: '2px 6px', height: '26px' }}
                >
                  {servers.map(s => (
                    <option key={s.id} value={s.id}>
                      {s.label} ({s.zoneName})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {zones.length > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Globe size={13} color="var(--accent)" />
                <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Switch region:</span>
                <select
                  value={activeServer?.zoneName || ''}
                  onChange={(e) => onChangeRegion && onChangeRegion(e.target.value)}
                  className="fleet-select"
                  style={{ fontSize: '0.75rem', padding: '2px 6px', height: '26px' }}
                >
                  <option value="" disabled>Select region...</option>
                  {zones.map(z => (
                    <option key={z.name} value={z.name}>
                      {z.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>

        {activeServer ? (
          <>
            <div style={{ fontSize: '1.15rem', fontWeight: 700, fontFamily: "'Space Grotesk', sans-serif" }}>{activeServer.label}</div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)', marginTop: '2px' }}>
              Current region: <strong style={{ color: 'var(--text-bright)' }}>{activeServer.zoneName}</strong>
            </div>
          </>
        ) : (
          <p style={{ color: 'var(--text-faint)', fontSize: '0.85rem', margin: 0 }}>
            No active server yet -- add servers or select a region above to start.
          </p>
        )}
      </section>
    </>
  );
}

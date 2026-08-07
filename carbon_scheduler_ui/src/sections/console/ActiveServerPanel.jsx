import React from 'react';
import { CheckCircle, ArrowRight, Zap } from 'lucide-react';

// Shows which of the client's own servers is currently active. In manual
// mode, when the scheduler's real-time recommendation differs from the
// active server, a banner offers to apply the switch -- nothing moves until
// the client clicks it. In auto mode the switch has already happened by the
// time this renders, so there's nothing to approve.
export default function ActiveServerPanel({ activeServer, recommendedServer, switchingMode, onApply }) {
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <CheckCircle size={15} color="var(--accent)" />
          <span className="mono" style={{ fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.05em', color: 'var(--accent)', textTransform: 'uppercase' }}>
            Active server
          </span>
        </div>
        {activeServer ? (
          <>
            <div style={{ fontSize: '1.15rem', fontWeight: 700, fontFamily: "'Space Grotesk', sans-serif" }}>{activeServer.label}</div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)', marginTop: '2px' }}>{activeServer.zoneName}</div>
          </>
        ) : (
          <p style={{ color: 'var(--text-faint)', fontSize: '0.85rem', margin: 0 }}>
            No active server yet -- add servers and play the clock to get a recommendation.
          </p>
        )}
      </section>
    </>
  );
}

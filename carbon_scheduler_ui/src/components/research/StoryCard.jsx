import React from 'react';
import { CheckCircle } from 'lucide-react';

// Narrative callout for a single real event (e.g. one real workload
// migration) that doesn't have enough structure for a chart -- the point
// IS the story, not a distribution.
export default function StoryCard({ title, children }) {
  return (
    <div className="glass-panel explainability-panel" style={{ marginBottom: '0.75rem' }}>
      <div style={{ display: 'flex', gap: '12px' }}>
        <div style={{ background: 'var(--spectrum-clean)', borderRadius: '50%', padding: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center', width: '32px', height: '32px', flexShrink: 0 }}>
          <CheckCircle size={18} color="#06291F" />
        </div>
        <div style={{ flex: 1 }}>
          <h3 style={{ fontSize: '0.95rem', margin: 0, fontFamily: "'Space Grotesk', sans-serif" }}>{title}</h3>
          <div style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: 'var(--text-dim)', lineHeight: 1.6 }}>{children}</div>
        </div>
      </div>
    </div>
  );
}

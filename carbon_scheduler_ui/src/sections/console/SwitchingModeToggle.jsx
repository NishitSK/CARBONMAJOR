import React from 'react';
import { Wand2, Hand } from 'lucide-react';

// Manual = client must click "Apply switch" on a recommendation.
// Auto = system re-scores each clock tick and switches on its own.
export default function SwitchingModeToggle({ mode, onChange }) {
  return (
    <div className="glass-panel switching-mode-toggle">
      <div className="panel-title" style={{ marginBottom: '0.9rem' }}>Switching mode</div>
      <div className="toggle-group" style={{ width: '100%' }}>
        <button
          onClick={() => onChange('manual')}
          className={`toggle-btn ${mode === 'manual' ? 'on' : ''}`}
          style={{ flex: 1, justifyContent: 'center', padding: '8px 10px' }}
        >
          <Hand size={13} /> Manual
        </button>
        <button
          onClick={() => onChange('auto')}
          className={`toggle-btn ${mode === 'auto' ? 'on' : ''}`}
          style={{ flex: 1, justifyContent: 'center', padding: '8px 10px' }}
        >
          <Wand2 size={13} /> Auto
        </button>
      </div>
      <p style={{ fontSize: '0.74rem', color: 'var(--text-dim)', marginTop: '0.8rem', lineHeight: 1.45 }}>
        {mode === 'manual'
          ? 'The system recommends a switch; you approve it before it applies.'
          : 'The system switches your active server on its own as real conditions change.'}
      </p>
    </div>
  );
}

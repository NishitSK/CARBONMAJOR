import React from 'react';
import { Settings, Info, CheckCircle } from 'lucide-react';

export default function ScoringControls({ weights, onWeightChange, maxLatency, onMaxLatencyChange, bestRegion }) {
  return (
    <div className="glass-panel sidebar-sticky">
      <div className="panel-title" style={{ marginBottom: '1.25rem' }}>
        <Settings size={15} color="var(--accent)" /> Scoring controls
      </div>

      <div className="weight-display mono">
        <span>C {weights.carbon.toFixed(2)} · L {weights.latency.toFixed(2)} · R {weights.resources.toFixed(2)}</span>
      </div>

      <div className="control-group">
        <label>Carbon weight</label>
        <input type="range" min="0" max="1" step="0.05" value={weights.carbon} onChange={(e) => onWeightChange('carbon', e.target.value)} />
      </div>

      <div className="control-group">
        <label>Latency weight</label>
        <input type="range" min="0" max="1" step="0.05" value={weights.latency} onChange={(e) => onWeightChange('latency', e.target.value)} />
      </div>

      <div className="control-group">
        <label>Resource weight</label>
        <input type="range" min="0" max="1" step="0.05" value={weights.resources} onChange={(e) => onWeightChange('resources', e.target.value)} />
      </div>

      <hr className="divider" />

      <div className="control-group">
        <label>Max latency allowed</label>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>Budget</span>
          <span className="mono" style={{ fontWeight: 700, color: 'var(--spectrum-mid)' }}>{maxLatency} ms</span>
        </div>
        <input type="range" min="20" max="400" step="10" value={maxLatency} onChange={(e) => onMaxLatencyChange(parseInt(e.target.value))} />
      </div>

      <div className="info-panel">
        <Info size={14} color="var(--accent)" />
        <p>Scores are normalized only across regions inside the {maxLatency}ms budget.</p>
      </div>

      {bestRegion && (
        <div className="best-region-box glass-panel best-region-glow">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <CheckCircle size={15} color="var(--accent)" />
            <span className="mono" style={{ fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.05em', color: 'var(--accent)', textTransform: 'uppercase' }}>Selected region</span>
          </div>
          <div style={{ fontSize: '1.15rem', fontWeight: 700, fontFamily: "'Space Grotesk', sans-serif" }}>{bestRegion.name}</div>
        </div>
      )}
    </div>
  );
}

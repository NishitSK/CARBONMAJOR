import React from 'react';
import { Settings, Info, CheckCircle, RotateCcw } from 'lucide-react';

// activeRegion / isOverride / overrideImpact / onResetSelection are optional:
// when a region has been switched to manually, the box shows what that
// choice costs relative to the optimal placement.
export default function ScoringControls({
  weights, onWeightChange, maxLatency, onMaxLatencyChange, bestRegion,
  activeRegion, isOverride, overrideImpact, onResetSelection,
}) {
  const shown = activeRegion || bestRegion;
  const signed = (v, unit) => `${v > 0 ? '+' : v < 0 ? '−' : '±'}${Math.abs(Math.round(v))} ${unit}`;

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

      {shown && (
        <div className="best-region-box glass-panel best-region-glow" role="status">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <CheckCircle size={15} color={isOverride ? 'var(--primary)' : 'var(--clean)'} />
            <span className="mono" style={{ fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.05em', color: isOverride ? 'var(--primary)' : 'var(--clean)', textTransform: 'uppercase' }}>
              {isOverride ? 'Manual override' : 'Optimal region'}
            </span>
          </div>
          <div style={{ fontSize: '1.15rem', fontWeight: 700 }}>{shown.name}</div>
          <div className="mono" style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
            {Math.round(shown.carbon)} gCO₂/kWh · {Math.round(shown.latency)} ms
          </div>

          {isOverride && overrideImpact && bestRegion && (
            <>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.75rem', lineHeight: 1.5 }}>
                Compared with the optimal <strong style={{ color: 'var(--text-main)' }}>{bestRegion.name}</strong>:{' '}
                <span className="mono" style={{ color: overrideImpact.carbonDelta > 0 ? 'var(--dirty)' : 'var(--clean)', fontWeight: 700 }}>
                  {signed(overrideImpact.carbonDelta, 'gCO₂/kWh')}
                </span>
                {' · '}
                <span className="mono" style={{ color: overrideImpact.latencyDelta < 0 ? 'var(--clean)' : 'var(--text-main)', fontWeight: 700 }}>
                  {signed(overrideImpact.latencyDelta, 'ms')}
                </span>
                {' · score '}
                <span className="mono">+{overrideImpact.scoreDelta.toFixed(4)}</span>
              </p>
              {onResetSelection && (
                <button
                  className="btn btn-outline"
                  style={{ marginTop: '0.75rem', width: '100%', justifyContent: 'center', fontSize: '0.85rem', padding: '0.5rem' }}
                  onClick={onResetSelection}
                >
                  <RotateCcw size={14} /> Reset to optimal
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

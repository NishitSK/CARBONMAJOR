import React from 'react';
import { TrendingDown, Download } from 'lucide-react';
import { SpectrumTick } from './SpectrumBar';

// Short on-row labels for the scheduler's strength names; the full name
// stays available as a tooltip.
const STRENGTH_LABELS = {
  'Low Carbon': 'Clean',
  'Clean Power Grid': 'Clean',
  'Low Latency': 'Fast',
  'High Resource Availability': 'Capacity',
};

// activeRegionName (optional) marks the placement currently in force; when it
// differs from rank #1, that row is highlighted instead and #1 keeps an
// "Optimal" tag. hideHeader lets a parent card supply its own title/export.
// Strengths sit under the region name rather than in their own column so the
// table fits the Playground's left column without scrolling.
export default function RegionRankingsTable({ results, debugMode, onExportCsv, onSelectRegion, activeRegionName, hideHeader, planningMode }) {
  const activeName = activeRegionName || results?.[0]?.region?.name;

  return (
    <section>
      {!hideHeader && (
        <div className="panel-title" style={{ marginBottom: '1rem', justifyContent: 'space-between', display: 'flex' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TrendingDown size={16} color="var(--accent)" /> Region rankings
          </span>
          <button onClick={onExportCsv} disabled={!results || results.length === 0} className="export-btn">
            <Download size={14} /> Export CSV
          </button>
        </div>
      )}
      <div className="table-wrap" style={{ overflowX: 'auto', maxWidth: '100%' }}>
        <table className="data-table results-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Region &amp; strengths</th>
              <th>Carbon</th>
              <th className="num">Latency</th>
              {debugMode && (
                <>
                  <th className="num">C_norm</th>
                  <th className="num">L_norm</th>
                  <th className="num">R_penalty</th>
                </>
              )}
              <th className="num">Score</th>
              {onSelectRegion && <th className="num">Placement</th>}
            </tr>
          </thead>
          <tbody>
            {(results || []).map((res) => {
              const region = res?.region || {};
              const isActive = region.name === activeName;
              const isOptimal = res?.rank === 1;
              const strengths = res?.metadata?.strengths || [];
              return (
                <tr key={region.name} id={`region-${region.name}`} className={isActive ? 'rank-1' : ''}>
                  <td className="mono" style={{ fontWeight: 700, color: isOptimal ? 'var(--clean)' : 'var(--text-faint)', whiteSpace: 'nowrap' }}>
                    #{res?.rank}
                  </td>
                  <td>
                    <div style={{ whiteSpace: 'nowrap', fontWeight: 500 }}>{region.name}</div>
                    {(isOptimal || strengths.length > 0) && (
                      <div className="strength-tags">
                        {isOptimal && <span className="optimal-tag">Optimal</span>}
                        {strengths.map((s) => (
                          <span key={s} className="strength-tag" title={s}>{STRENGTH_LABELS[s] || s}</span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <div style={{ width: '44px', flexShrink: 0 }}>
                        <SpectrumTick carbon={region.carbon} />
                      </div>
                      <span className="mono" style={{ fontSize: '0.8rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                        {Math.round(region.carbon ?? 0)} g
                      </span>
                    </div>
                  </td>
                  <td className="num" style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    {typeof region.latency === 'number' ? `${Math.round(region.latency)} ms` : '—'}
                  </td>
                  {debugMode && res?.metadata && (
                    <>
                      <td className="num" style={{ color: 'var(--text-muted)' }}>{res.metadata.c_norm}</td>
                      <td className="num" style={{ color: 'var(--text-muted)' }}>{res.metadata.l_norm}</td>
                      <td className="num" style={{ color: 'var(--text-muted)' }}>{res.metadata.r_penalty}</td>
                    </>
                  )}
                  <td className="num score-cell">{res?.score?.toFixed(4) || '0.0000'}</td>
                  {onSelectRegion && (
                    <td className="num">
                      {isActive ? (
                        <span className="placement-active">{planningMode ? 'Planned' : 'Active'}</span>
                      ) : (
                        <button
                          className="btn btn-outline"
                          style={{ padding: '0.3rem 0.75rem', fontSize: '0.75rem' }}
                          onClick={() => onSelectRegion(region.name)}
                          aria-label={`${planningMode ? 'Plan placement in' : 'Switch placement to'} ${region.name}`}
                        >
                          {planningMode ? 'Place here' : 'Switch'}
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

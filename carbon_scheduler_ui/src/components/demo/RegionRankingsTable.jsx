import React from 'react';
import { TrendingDown, Download } from 'lucide-react';
import { SpectrumTick } from './SpectrumBar';

export default function RegionRankingsTable({ results, debugMode, onExportCsv, onSelectRegion }) {
  return (
    <section>
      <div className="panel-title" style={{ marginBottom: '1rem', justifyContent: 'space-between', display: 'flex' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <TrendingDown size={16} color="var(--accent)" /> Region rankings
        </span>
        <button onClick={onExportCsv} disabled={!results || results.length === 0} className="export-btn">
          <Download size={14} /> Export CSV
        </button>
      </div>
      <div className="glass-panel no-padding" style={{ overflowX: 'auto', maxWidth: '100%' }}>
        <table className="results-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Region</th>
              <th>Carbon</th>
              {debugMode && (
                <>
                  <th>C_norm</th>
                  <th>L_norm</th>
                  <th>R_penalty</th>
                </>
              )}
              <th>Score</th>
              <th>Strengths</th>
              {onSelectRegion && <th>Action</th>}
            </tr>
          </thead>
          <tbody>
            {(results || []).map((res) => (
              <tr key={res?.region?.name} id={`region-${res?.region?.name}`} className={res?.rank === 1 ? 'rank-1' : ''}>
                <td className="mono" style={{ fontWeight: 700, color: 'var(--text-dim)' }}>#{res?.rank}</td>
                <td>{res?.region?.name}</td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <SpectrumTick carbon={res?.region?.carbon} />
                    <span className="mono" style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>{res?.region?.carbon}g</span>
                  </div>
                </td>
                {debugMode && res?.metadata && (
                  <>
                    <td className="mono" style={{ color: 'var(--text-dim)' }}>{res.metadata.c_norm}</td>
                    <td className="mono" style={{ color: 'var(--text-dim)' }}>{res.metadata.l_norm}</td>
                    <td className="mono" style={{ color: 'var(--text-dim)' }}>{res.metadata.r_penalty}</td>
                  </>
                )}
                <td className="score-cell">{res?.score?.toFixed(4) || '0.0000'}</td>
                <td>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    {(res?.metadata?.strengths || []).map(s => (
                      <span key={s} className="mini-badge">{s}</span>
                    ))}
                  </div>
                </td>
                {onSelectRegion && (
                  <td>
                    <button
                      className="ghost-btn"
                      style={{ padding: '2px 8px', fontSize: '0.72rem' }}
                      onClick={() => onSelectRegion(res?.region?.name)}
                    >
                      Switch
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

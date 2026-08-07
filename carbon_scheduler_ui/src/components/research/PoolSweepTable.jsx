import React from 'react';

// Bespoke small table for pool_generalization_sweep.json's nested
// pool_sweeps dict -- generic enough shape (region-pool name -> stats) that
// a bar/compact-row treatment would lose the "does removing this specific
// region change the story" comparison that's the point of this result.
export default function PoolSweepTable({ poolSweeps }) {
  const rows = Object.entries(poolSweeps).map(([name, r]) => ({ name, ...r }));
  return (
    <div className="glass-panel no-padding" style={{ overflowX: 'auto' }}>
      <table className="results-table">
        <thead>
          <tr>
            <th>Pool variant</th>
            <th>Scheduler vs. static lookup</th>
            <th>Dominant region</th>
            <th>Share</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.name}>
              <td style={{ fontSize: '0.78rem' }}>{r.name.replace(/^leave_out__/, 'without ').replace(/_/g, ' ')}</td>
              <td className="mono" style={{ color: r.scheduler_vs_static_lookup_pct > 10 ? 'var(--accent)' : 'var(--text-dim)' }}>
                {r.scheduler_vs_static_lookup_pct > 0 ? '+' : ''}{r.scheduler_vs_static_lookup_pct.toFixed(2)}%
              </td>
              <td style={{ fontSize: '0.78rem' }}>{r.top_region}</td>
              <td className="mono" style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>{r.top_region_share_pct.toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

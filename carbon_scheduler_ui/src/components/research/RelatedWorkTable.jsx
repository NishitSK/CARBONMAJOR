import React from 'react';

// Sourced directly from the paper's own "Comparison with Related Work"
// table -- these are each prior system's OWN self-reported numbers, read
// from their respective publications, not re-measured under a shared
// protocol here. Kept as a static, literature-cited table (not a
// research_api.py result) for exactly that reason: it isn't this
// project's output, it's a citation.
const ROWS = [
  { system: 'Radovanovic 2022 (Google)', reduction: '29%', eval: 'Production', rt: true, sla: true, spatial: true, temporal: true },
  { system: 'CarbonScaler (Hanafy et al.)', reduction: '34%', eval: 'Real AWS', rt: true, sla: false, spatial: false, temporal: false },
  { system: 'PCAPS', reduction: '32.9%', eval: '100-node Spark', rt: 'partial', sla: true, spatial: false, temporal: 'partial' },
  { system: 'GreenScale', reduction: '35.2%', eval: 'Edge simulation', rt: false, sla: 'partial', spatial: true, temporal: true },
  { system: 'Danach 2026', reduction: '25%', eval: 'UK grid + MILP', rt: 'partial', sla: true, spatial: true, temporal: true },
  { system: 'Phutane 2022', reduction: '44%', eval: 'Simulation only', rt: false, sla: true, spatial: false, temporal: true },
];

const THIS_WORK_ROWS = [
  { system: 'This work (Phase I)', reduction: '31.5%', eval: '50 sim. workloads', rt: true, sla: true, spatial: true, temporal: true },
  { system: 'This work (live pilot)', reduction: '+94.7%*', eval: 'Real 12-region AWS', rt: true, sla: true, spatial: true, temporal: true },
];

function StatusMark({ value }) {
  if (value === true) return <span style={{ color: 'var(--spectrum-clean)' }}>✓</span>;
  if (value === false) return <span style={{ color: 'var(--text-faint)' }}>✗</span>;
  return <span style={{ color: 'var(--spectrum-mid)' }}>~</span>;
}

export default function RelatedWorkTable() {
  return (
    <div className="research-chart-block glass-panel">
      <h3 className="research-chart-title">How this compares to six published carbon-aware schedulers</h3>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-dim)', lineHeight: 1.55, marginBottom: '1rem' }}>
        Figures for the six prior systems are taken directly from their own publications, evaluated under their
        own protocols, region pools, carbon-data sources, workload types, and time periods — not replicated here
        under a shared experimental harness. Read as context, not a settled ranking.
      </p>

      <div style={{ overflowX: 'auto' }}>
        <table className="results-table">
          <thead>
            <tr>
              <th>System</th>
              <th>CO₂ reduction</th>
              <th>Evaluation</th>
              <th title="Real-time decision-making">RT</th>
              <th title="SLA-aware">SLA</th>
              <th title="Spatial shifting">Sp.</th>
              <th title="Temporal shifting">Temp.</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map(r => (
              <tr key={r.system}>
                <td>{r.system}</td>
                <td className="mono">{r.reduction}</td>
                <td style={{ color: 'var(--text-dim)' }}>{r.eval}</td>
                <td><StatusMark value={r.rt} /></td>
                <td><StatusMark value={r.sla} /></td>
                <td><StatusMark value={r.spatial} /></td>
                <td><StatusMark value={r.temporal} /></td>
              </tr>
            ))}
            {THIS_WORK_ROWS.map(r => (
              <tr key={r.system} className="rank-1">
                <td style={{ fontWeight: 700 }}>{r.system}</td>
                <td className="mono score-cell">{r.reduction}</td>
                <td style={{ color: 'var(--text)' }}>{r.eval}</td>
                <td><StatusMark value={r.rt} /></td>
                <td><StatusMark value={r.sla} /></td>
                <td><StatusMark value={r.spatial} /></td>
                <td><StatusMark value={r.temporal} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p style={{ fontSize: '0.76rem', color: 'var(--text-faint)', marginTop: '0.75rem', lineHeight: 1.5 }}>
        * vs. a carbon-blind fixed-region baseline — only <strong style={{ color: 'var(--text-dim)' }}>+6.5%</strong> vs.
        a naive static-lookup baseline (the number that actually isolates real-time adaptivity's contribution;
        see the decomposition above). The one claim made without qualification: this is the only system in the
        table that reports a decomposition splitting the value of adaptivity from the value of region selection.
      </p>
    </div>
  );
}

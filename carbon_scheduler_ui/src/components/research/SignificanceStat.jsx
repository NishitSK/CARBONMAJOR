import React from 'react';
import { CheckCircle } from 'lucide-react';

function formatP(p) {
  if (p === null || p === undefined) return '—';
  if (p < 0.001) return 'p < 0.001';
  return `p = ${p.toFixed(3)}`;
}

// A row of small significance callouts (t-stat, p-value, sample size).
// `significant` drives the badge; pass explicitly rather than inferring
// from p alone, since some results (e.g. a null finding) are "significant
// but the wrong direction" and that distinction matters here.
export default function SignificanceStat({ tStat, pValue, n, significant = true, note }) {
  return (
    <div className="significance-stat">
      <span className={`status-badge ${significant ? 'status-pass' : 'status-fail'}`} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
        <CheckCircle size={12} /> {significant ? 'Statistically significant' : 'Not significant'}
      </span>
      <span className="mono significance-detail">
        {tStat !== undefined && `t = ${tStat.toFixed(2)}, `}{formatP(pValue)}{n !== undefined && `, n = ${n.toLocaleString()}`}
      </span>
      {note && <p className="significance-note">{note}</p>}
    </div>
  );
}

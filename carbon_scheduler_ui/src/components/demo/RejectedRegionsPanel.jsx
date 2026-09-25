import React from 'react';
import { AlertTriangle } from 'lucide-react';

// Rejections arrive as {name, reason} from the API, or with the full region
// (incl. latency) from the offline fallback — pull the numbers out of the
// reason text when they aren't on the object.
function parseLatency(r) {
  const m = /Latency\s*\(?([\d.]+)\s*ms\)?.*?SLA(?:\s*ceiling)?\s*\(?([\d.]+)\s*ms/i.exec(r?.reason || '');
  const latency = typeof r?.latency === 'number' ? r.latency : m ? parseFloat(m[1]) : null;
  const budget = m ? parseFloat(m[2]) : null;
  return { latency, budget };
}

function splitName(name = '') {
  const m = /^(\S+)\s*\((.+)\)$/.exec(name);
  return m ? { code: m[1], city: m[2] } : { code: '', city: name };
}

export default function RejectedRegionsPanel({ rejected }) {
  if (!rejected || rejected.length === 0) return null;

  const rows = rejected
    .map((r) => ({ ...r, ...parseLatency(r), ...splitName(r?.name) }))
    .sort((a, b) => (a.latency ?? Infinity) - (b.latency ?? Infinity));
  const budget = rows.find((r) => r.budget != null)?.budget;

  return (
    <section className="rejected-list-section">
      <div className="rejected-head">
        <h2><AlertTriangle size={16} color="var(--dirty)" /> Rejected: over latency budget</h2>
        <p>
          {rows.length} region{rows.length === 1 ? '' : 's'} excluded{budget != null ? ` by the ${Math.round(budget)} ms SLA` : ''}, closest to budget first
        </p>
      </div>
      <div className="rejected-grid">
        {rows.map((r) => (
          <div key={r.name} className="rejected-card-small" title={r.reason}>
            <div className="rej-name">
              <span className="rej-city">{r.city}</span>
              {r.code && <span className="rej-code">{r.code}</span>}
            </div>
            {r.latency != null ? (
              <div className="rej-lat">
                <b>{Math.round(r.latency)} ms</b>
                {r.budget != null && <span>+{Math.round(r.latency - r.budget)} over</span>}
              </div>
            ) : (
              <div className="rej-lat"><span>{r.reason}</span></div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

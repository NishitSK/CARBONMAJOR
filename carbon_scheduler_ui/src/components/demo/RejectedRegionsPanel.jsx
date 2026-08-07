import React from 'react';
import { AlertTriangle } from 'lucide-react';

export default function RejectedRegionsPanel({ rejected }) {
  if (!rejected || rejected.length === 0) return null;
  return (
    <section className="rejected-list-section">
      <h2 className="panel-title" style={{ color: 'var(--danger)', marginBottom: '1rem' }}>
        <AlertTriangle size={16} /> Rejected — over latency budget
      </h2>
      <div className="rejected-grid">
        {rejected.map(r => (
          <div key={r?.name || Math.random()} className="glass-panel rejected-card-small">
            <span style={{ fontWeight: 600 }}>{r?.name}</span>
            <span className="mono" style={{ color: 'var(--danger)', fontSize: '0.78rem' }}>{r?.reason}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

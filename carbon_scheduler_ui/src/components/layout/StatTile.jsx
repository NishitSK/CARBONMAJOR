import React from 'react';

// Reusable big-number callout, used in the Hero and throughout the
// research sections. tone: 'neutral' | 'accent' | 'warn'. size: 'md' | 'lg'.
export default function StatTile({ value, label, tone = 'neutral', size = 'md' }) {
  return (
    <div className={`stat-tile stat-tile-${tone} stat-tile-${size}`}>
      <div className="stat-tile-value mono">{value}</div>
      <div className="stat-tile-label">{label}</div>
    </div>
  );
}

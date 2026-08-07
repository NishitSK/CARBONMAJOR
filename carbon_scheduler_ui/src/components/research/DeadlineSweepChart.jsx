import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from 'recharts';

// The single most important chart on the site: for each deadline (1h/4h/
// 8h/24h), compares no-shift vs. the current fake-forecast system vs. the
// real-AI-forecast-driven system vs. a perfect-hindsight oracle. Built for
// temporal_shift_benchmark.json specifically -- this is the result that
// earns "AI" in the project's title.
export default function DeadlineSweepChart({ deadlines, resultsByDeadline, height = 320 }) {
  const data = deadlines.map(d => {
    const r = resultsByDeadline[String(d)];
    return {
      deadline: `${d}h`,
      'No shift': r.no_shift_mean_ci,
      'Fake forecast (today)': r.synthetic_mean_ci,
      'Real AI forecast': r.real_ai_mean_ci,
      'Perfect oracle': r.oracle_mean_ci,
    };
  });

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--line-soft)" vertical={false} />
        <XAxis dataKey="deadline" tick={{ fill: 'var(--text-dim)', fontSize: 12 }} axisLine={{ stroke: 'var(--line)' }} tickLine={false} />
        <YAxis tick={{ fill: 'var(--text-dim)', fontSize: 11 }} axisLine={false} tickLine={false} label={{ value: 'Avg. CI (g)', angle: -90, position: 'insideLeft', fill: 'var(--text-faint)', fontSize: 11 }} />
        <Tooltip
          formatter={(v) => [`${Number(v).toFixed(2)}g`, '']}
          contentStyle={{ background: 'var(--surface-raised)', border: '1px solid var(--line)', borderRadius: 6, fontSize: 12 }}
          labelStyle={{ color: 'var(--text)' }}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: 'var(--text-dim)' }} />
        <Bar dataKey="No shift" fill="var(--text-faint)" radius={[3, 3, 0, 0]} />
        <Bar dataKey="Fake forecast (today)" fill="var(--spectrum-dirty)" radius={[3, 3, 0, 0]} />
        <Bar dataKey="Real AI forecast" fill="var(--accent)" radius={[3, 3, 0, 0]} />
        <Bar dataKey="Perfect oracle" fill="var(--spectrum-clean)" radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

import React from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const COLORS = ['var(--accent)', 'var(--spectrum-mid)', 'var(--spectrum-warm)', 'var(--spectrum-dirty)', 'var(--text-faint)'];

// Region win-share donut, e.g. {"eu-north-1 (Sweden)": 2741, "ca-central-1 (Canada)": 179, ...}
export default function WinnerDistributionDonut({ winnerCounts, height = 220 }) {
  const total = Object.values(winnerCounts).reduce((a, b) => a + b, 0);
  const data = Object.entries(winnerCounts)
    .sort((a, b) => b[1] - a[1])
    .map(([name, count]) => ({ name, value: count, pct: (100 * count / total).toFixed(1) }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="80%" paddingAngle={2}>
          {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Pie>
        <Tooltip
          formatter={(value, name, props) => [`${value} decisions (${props.payload.pct}%)`, name]}
          contentStyle={{ background: 'var(--surface-raised)', border: '1px solid var(--line)', borderRadius: 6, fontSize: 12 }}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: 'var(--text-dim)' }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

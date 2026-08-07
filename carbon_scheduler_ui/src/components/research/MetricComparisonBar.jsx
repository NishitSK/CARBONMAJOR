import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LabelList } from 'recharts';

// Generic N-system comparison bar chart (e.g. scheduler vs. static lookup
// vs. fixed baseline). `items` = [{ label, value, tone }], tone one of
// 'accent' | 'neutral' | 'danger' picks the bar color from the existing
// design tokens so every chart on the site shares one palette.
const TONE_COLOR = {
  accent: 'var(--accent)',
  neutral: 'var(--spectrum-mid)',
  danger: 'var(--spectrum-dirty)',
  clean: 'var(--spectrum-clean)',
};

export default function MetricComparisonBar({ items, unit = 'g', height = 220 }) {
  const data = items.map(it => ({ name: it.label, value: it.value }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 8, right: 40, left: 8, bottom: 8 }}>
        <XAxis type="number" hide />
        <YAxis type="category" dataKey="name" width={170} tick={{ fill: 'var(--text-dim)', fontSize: 12 }} axisLine={false} tickLine={false} />
        <Tooltip
          formatter={(v) => [`${v}${unit}`, 'Avg. CI']}
          contentStyle={{ background: 'var(--surface-raised)', border: '1px solid var(--line)', borderRadius: 6, fontSize: 12 }}
          labelStyle={{ color: 'var(--text)' }}
        />
        <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={22}>
          {data.map((_, i) => (
            <Cell key={i} fill={TONE_COLOR[items[i].tone] || TONE_COLOR.neutral} />
          ))}
          <LabelList dataKey="value" position="right" formatter={(v) => `${v}${unit}`} fill="var(--text-dim)" fontSize={12} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

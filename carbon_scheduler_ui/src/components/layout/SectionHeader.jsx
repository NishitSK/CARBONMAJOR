import React from 'react';

// Consistent section intro: a small eyebrow label, the section title, and
// one plain-language sentence stating the finding before any stats/jargon
// (design principle: write for a reader with zero background).
export default function SectionHeader({ eyebrow, icon, title, lede }) {
  return (
    <div className="section-header">
      <span className="console-eyebrow">
        {icon && <span style={{ marginRight: '6px', verticalAlign: '-2px' }}>{icon}</span>}
        {eyebrow}
      </span>
      <h2>{title}</h2>
      {lede && <p className="section-lede">{lede}</p>}
    </div>
  );
}

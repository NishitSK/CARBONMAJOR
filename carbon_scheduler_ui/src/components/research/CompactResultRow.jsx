import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

// Collapsed-by-default: a plain-language line + a small stat, expanding
// into whatever `children` detail is passed. This is what lets "surface
// everything" not mean a wall of always-open cards (design principle 3).
export default function CompactResultRow({ title, plainLanguage, stat, children }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="compact-result-row">
      <button className="compact-result-header" onClick={() => setOpen(o => !o)}>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="compact-result-title">{title}</span>
        {stat && <span className="compact-result-stat mono">{stat}</span>}
      </button>
      {plainLanguage && <p className="compact-result-lede">{plainLanguage}</p>}
      {open && <div className="compact-result-detail">{children}</div>}
    </div>
  );
}

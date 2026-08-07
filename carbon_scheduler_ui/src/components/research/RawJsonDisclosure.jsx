import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

// Honest fallback for any result not worth a bespoke chart -- keeps the
// "surface everything" promise true without pretending every file has a
// polished visualization. Collapsed by default (design principle 3).
export default function RawJsonDisclosure({ title, data }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="raw-json-disclosure">
      <button className="raw-json-toggle" onClick={() => setOpen(o => !o)}>
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        {title ? `View raw data: ${title}` : 'View raw data'}
      </button>
      {open && <pre className="raw-json-pre mono">{JSON.stringify(data, null, 2)}</pre>}
    </div>
  );
}

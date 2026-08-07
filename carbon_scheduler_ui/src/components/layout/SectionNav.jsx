import React from 'react';
import { Link } from 'react-router-dom';
import { Shield } from 'lucide-react';
import { useScrollSpy } from '../../hooks/useScrollSpy';

const LINKS = [
  { id: 'model-showcase', label: 'Showcase' },
  { id: 'decomposition', label: 'Decomposition' },
  { id: 'forecasting', label: 'Forecasting' },
  { id: 'supporting-evidence', label: 'Evidence' },
];

export default function SectionNav() {
  const activeId = useScrollSpy(LINKS.map(l => l.id));

  const scrollTo = (id) => (e) => {
    e.preventDefault();
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <nav className="section-nav">
      <div className="section-nav-inner">
        <span className="section-nav-brand">
          <Shield size={15} color="var(--accent)" /> Carbon-Aware Scheduler
        </span>
        <div className="section-nav-links">
          {LINKS.map(l => (
            <a
              key={l.id}
              href={`#${l.id}`}
              onClick={scrollTo(l.id)}
              className={`section-nav-link ${activeId === l.id ? 'active' : ''}`}
            >
              {l.label}
            </a>
          ))}
          <Link to="/console" className="section-nav-link section-nav-cta">Console →</Link>
          <Link to="/playground" className="section-nav-link">Sandbox</Link>
        </div>
      </div>
    </nav>
  );
}

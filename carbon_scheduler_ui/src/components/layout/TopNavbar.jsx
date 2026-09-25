import React, { useEffect, useRef, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Play, Sun, Moon, ChevronDown, Settings, Database } from 'lucide-react';
import { useTour } from '../../context/TourContext';
import { useDataMode } from '../../data/DataModeContext';

const UNDER_THE_HOOD = [
  { to: '/console', label: 'Console' },
  { to: '/forecasting', label: 'Forecasting' },
  { to: '/pilot', label: 'Pilot Telemetry' },
  { to: '/playground', label: 'Playground' },
  { to: '/about', label: 'About & Help' },
];

function getInitialTheme() {
  try {
    const saved = localStorage.getItem('cadss-theme');
    if (saved === 'light' || saved === 'dark') return saved;
  } catch (e) { /* storage blocked */ }
  return 'light';
}

export default function TopNavbar() {
  const { startTour } = useTour();
  const { mode, unlock, lock } = useDataMode();
  const [theme, setTheme] = useState(getInitialTheme);
  const [hoodOpen, setHoodOpen] = useState(false);
  const [devOpen, setDevOpen] = useState(false);
  const [pinInput, setPinInput] = useState('');
  const [pinError, setPinError] = useState(false);
  const hoodRef = useRef(null);
  const devRef = useRef(null);
  const location = useLocation();
  const onUnderTheHood = UNDER_THE_HOOD.some((r) => r.to === location.pathname);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try { localStorage.setItem('cadss-theme', theme); } catch (e) { /* ignore */ }
  }, [theme]);

  useEffect(() => {
    function onClickOutside(e) {
      if (hoodRef.current && !hoodRef.current.contains(e.target)) setHoodOpen(false);
      if (devRef.current && !devRef.current.contains(e.target)) setDevOpen(false);
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  const toggleTheme = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'));

  const submitPin = () => {
    if (unlock(pinInput)) {
      setPinError(false);
      setPinInput('');
      setDevOpen(false);
    } else {
      setPinError(true);
    }
  };

  return (
    <header className="navbar">
      <div className="nav-brand">
        <span className="nav-logo-badge">CADSS</span>
        <span className="nav-title">Carbon-Aware Scheduler</span>
      </div>

      <nav className="nav-links">
        <NavLink
          to="/"
          end
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          Placement Audit
        </NavLink>

        <div ref={hoodRef} style={{ position: 'relative' }}>
          <button
            className={`nav-link ${onUnderTheHood ? 'active' : ''}`}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', background: 'transparent', border: 'none', cursor: 'pointer', font: 'inherit' }}
            onClick={() => setHoodOpen((o) => !o)}
          >
            Under the hood <ChevronDown size={14} />
          </button>
          {hoodOpen && (
            <div
              style={{
                position: 'absolute', top: 'calc(100% + 6px)', left: 0, minWidth: '190px',
                background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)',
                boxShadow: 'var(--shadow-md)', padding: '0.4rem', zIndex: 60,
              }}
            >
              {UNDER_THE_HOOD.map((r) => (
                <NavLink
                  key={r.to}
                  to={r.to}
                  onClick={() => setHoodOpen(false)}
                  className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                  style={{ display: 'block', width: '100%', padding: '0.55rem 0.8rem' }}
                >
                  {r.label}
                </NavLink>
              ))}
            </div>
          )}
        </div>
      </nav>

      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '0.6rem' }}>
        <button
          className="btn btn-outline"
          style={{ padding: '0.5rem', fontSize: '0.85rem' }}
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          aria-label="Toggle color theme"
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>

        <button
          className="btn btn-outline"
          style={{ padding: '0.45rem 0.95rem', fontSize: '0.85rem' }}
          onClick={() => startTour(0)}
          title="Launch Guided Tour"
        >
          <Play size={14} fill="var(--primary)" color="var(--primary)" /> Guided Tour
        </button>

        <div ref={devRef} style={{ position: 'relative' }}>
          <button
            className="simulated-chip"
            style={{ cursor: 'pointer', border: mode === 'live' ? '1px solid var(--clean-border)' : undefined, background: mode === 'live' ? 'var(--clean-bg)' : undefined, color: mode === 'live' ? 'var(--clean)' : undefined }}
            onClick={() => setDevOpen((o) => !o)}
            title="Dev Options — data source"
          >
            <Database size={13} />
            {mode === 'live' ? 'Live data' : 'Simulated data'}
            <Settings size={12} />
          </button>

          {devOpen && (
            <div
              style={{
                position: 'absolute', top: 'calc(100% + 6px)', right: 0, width: '260px',
                background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)',
                boxShadow: 'var(--shadow-md)', padding: '1rem', zIndex: 60,
              }}
            >
              <div style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: '0.4rem' }}>Dev Options</div>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.8rem', lineHeight: 1.5 }}>
                By default everything here runs on locally simulated data — no backend, no AWS, no licensed data
                required. Live mode connects to a running backend for real telemetry.
              </p>
              {mode === 'live' ? (
                <button className="btn btn-outline" style={{ width: '100%', justifyContent: 'center' }} onClick={lock}>
                  Switch back to Simulated
                </button>
              ) : (
                <>
                  <input
                    type="password"
                    className="fleet-input"
                    style={{ width: '100%', marginBottom: '0.5rem' }}
                    placeholder="PIN to unlock Live data"
                    value={pinInput}
                    onChange={(e) => { setPinInput(e.target.value); setPinError(false); }}
                    onKeyDown={(e) => e.key === 'Enter' && submitPin()}
                  />
                  {pinError && <div style={{ color: 'var(--dirty)', fontSize: '0.75rem', marginBottom: '0.5rem' }}>Incorrect PIN.</div>}
                  <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} onClick={submitPin}>
                    Unlock Live data
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

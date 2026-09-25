import React, { createContext, useContext, useEffect, useState } from 'react';

// Simulated by default everywhere in the app. Live mode (real backend / AWS
// pilot data) is opt-in via a PIN, meant to keep a customer-facing demo from
// ever silently depending on a running Python backend, licensed data, or AWS
// credentials. NOTE: this PIN only hides the toggle from casual clicks in a
// demo setting — it is not access control. Real protection is that the
// backend itself is not publicly deployed with live credentials.
const DataModeContext = createContext(null);
const STORAGE_KEY = 'cadss-data-mode';
const DEV_PIN = import.meta.env.VITE_DEV_PIN || '2468';

export function DataModeProvider({ children }) {
  const [mode, setMode] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'live' ? 'live' : 'simulated';
    } catch (e) {
      return 'simulated';
    }
  });

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, mode); } catch (e) { /* ignore */ }
  }, [mode]);

  const unlock = (pin) => {
    if (pin === DEV_PIN) {
      setMode('live');
      return true;
    }
    return false;
  };
  const lock = () => setMode('simulated');

  return (
    <DataModeContext.Provider value={{ mode, unlock, lock }}>
      {children}
    </DataModeContext.Provider>
  );
}

export function useDataMode() {
  const ctx = useContext(DataModeContext);
  if (!ctx) throw new Error('useDataMode must be used within a DataModeProvider');
  return ctx;
}

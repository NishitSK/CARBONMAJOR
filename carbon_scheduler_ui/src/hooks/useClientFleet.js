import { useState, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'carbon_console_fleet_v1';

const DEFAULT_STATE = {
  servers: [],                 // [{ id, label, zoneName }]
  weights: { carbon: 0.4, latency: 0.3, resources: 0.3 },
  maxLatency: 200,
  switchingMode: 'manual',     // 'manual' | 'auto'
  activeServerId: null,
};

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_STATE;
    return { ...DEFAULT_STATE, ...JSON.parse(raw) };
  } catch (err) {
    console.error('Failed to load saved console fleet, starting fresh:', err);
    return DEFAULT_STATE;
  }
}

// A demo client's own server fleet + settings, persisted to localStorage
// (no login/backend needed -- this is a demo, not a real account system).
// Every server is a { label, zoneName } pair: the label is whatever the
// client calls it, zoneName is one of the real electricity zones this
// system already has real carbon data for (see GET /regions/zones).
export function useClientFleet() {
  const [state, setState] = useState(loadState);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  const addServer = useCallback((label, zoneName) => {
    setState(s => ({
      ...s,
      servers: [...s.servers, { id: crypto.randomUUID(), label, zoneName }],
    }));
  }, []);

  const removeServer = useCallback((id) => {
    setState(s => ({
      ...s,
      servers: s.servers.filter(sv => sv.id !== id),
      activeServerId: s.activeServerId === id ? null : s.activeServerId,
    }));
  }, []);

  const renameServer = useCallback((id, label) => {
    setState(s => ({
      ...s,
      servers: s.servers.map(sv => (sv.id === id ? { ...sv, label } : sv)),
    }));
  }, []);

  const setWeights = useCallback((weights) => setState(s => ({ ...s, weights })), []);
  const setMaxLatency = useCallback((maxLatency) => setState(s => ({ ...s, maxLatency })), []);
  const setSwitchingMode = useCallback((switchingMode) => setState(s => ({ ...s, switchingMode })), []);
  const setActiveServerId = useCallback((activeServerId) => setState(s => ({ ...s, activeServerId })), []);

  return {
    ...state,
    addServer, removeServer, renameServer,
    setWeights, setMaxLatency, setSwitchingMode, setActiveServerId,
  };
}

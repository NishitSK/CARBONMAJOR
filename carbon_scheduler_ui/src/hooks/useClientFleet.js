import { useState, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'carbon_console_fleet_v1';

const DEFAULT_PROGRAMS = [
  {
    id: 'p-1',
    name: 'Global E-Commerce Platform',
    geoScope: 'World',
  },
  {
    id: 'p-2',
    name: 'EU Compliance & Financial Services',
    geoScope: 'Europe',
  },
  {
    id: 'p-3',
    name: 'APAC Regional Data Engine',
    geoScope: 'South East Asia',
  },
];

const DEFAULT_WORKLOADS = [
  {
    id: 'w-1',
    programId: 'p-1',
    name: 'Primary API Gateway',
    type: 'latency-sensitive',
    maxLatency: 150,
    weights: { carbon: 0.4, latency: 0.4, resources: 0.2 },
    activeServerId: null,
    switchingMode: 'manual',
  },
  {
    id: 'w-2',
    programId: 'p-1',
    name: 'Order Processing Queue',
    type: 'delay-tolerant',
    maxLatency: 250,
    weights: { carbon: 0.7, latency: 0.1, resources: 0.2 },
    activeServerId: null,
    switchingMode: 'manual',
  },
  {
    id: 'w-3',
    programId: 'p-2',
    name: 'EU Ledger Service',
    type: 'latency-sensitive',
    maxLatency: 180,
    weights: { carbon: 0.5, latency: 0.3, resources: 0.2 },
    activeServerId: null,
    switchingMode: 'manual',
  },
  {
    id: 'w-4',
    programId: 'p-3',
    name: 'APAC Realtime Analytics',
    type: 'delay-tolerant',
    maxLatency: 220,
    weights: { carbon: 0.6, latency: 0.2, resources: 0.2 },
    activeServerId: null,
    switchingMode: 'manual',
  },
];

const DEFAULT_STATE = {
  servers: [],                 // [{ id, label, zoneName }]
  programs: DEFAULT_PROGRAMS,  // [{ id, name, geoScope }]
  workloads: DEFAULT_WORKLOADS,// [{ id, programId, name, type, maxLatency, weights, activeServerId, switchingMode }]
  weights: { carbon: 0.4, latency: 0.3, resources: 0.3 },
  maxLatency: 200,
  switchingMode: 'manual',     // 'manual' | 'auto'
  activeServerId: null,
};

function sanitizeWorkloads(workloads, defaultProgramId = 'p-1') {
  if (!Array.isArray(workloads) || workloads.length === 0) return DEFAULT_WORKLOADS;
  return workloads.map(w => ({
    id: w.id || crypto.randomUUID(),
    programId: w.programId || defaultProgramId,
    name: w.name || 'Workload',
    type: w.type || 'latency-sensitive',
    maxLatency: typeof w.maxLatency === 'number' ? w.maxLatency : 200,
    weights: {
      carbon: (w.weights && typeof w.weights.carbon === 'number') ? w.weights.carbon : 0.4,
      latency: (w.weights && typeof w.weights.latency === 'number') ? w.weights.latency : 0.3,
      resources: (w.weights && typeof w.weights.resources === 'number') ? w.weights.resources : 0.3,
    },
    activeServerId: w.activeServerId || null,
    switchingMode: w.switchingMode || 'manual',
  }));
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_STATE;
    const parsed = JSON.parse(raw);
    const validPrograms = parsed.programs && parsed.programs.length > 0 ? parsed.programs : DEFAULT_PROGRAMS;
    const defaultProgId = validPrograms[0]?.id || 'p-1';
    return {
      ...DEFAULT_STATE,
      ...parsed,
      programs: validPrograms,
      workloads: sanitizeWorkloads(parsed.workloads, defaultProgId),
    };
  } catch (err) {
    console.error('Failed to load saved console fleet, starting fresh:', err);
    return DEFAULT_STATE;
  }
}

export function useClientFleet() {
  const [state, setState] = useState(loadState);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  const addServer = useCallback((label, zoneName) => {
    setState(s => {
      const newId = crypto.randomUUID();
      const updatedWorkloads = (s.workloads || []).map(w => ({
        ...w,
        activeServerId: w.activeServerId || newId,
      }));
      return {
        ...s,
        servers: [...s.servers, { id: newId, label, zoneName }],
        activeServerId: s.activeServerId || newId,
        workloads: updatedWorkloads,
      };
    });
  }, []);

  const removeServer = useCallback((id) => {
    setState(s => {
      const newServers = s.servers.filter(sv => sv.id !== id);
      const nextActive = newServers[0]?.id || null;
      const updatedWorkloads = (s.workloads || []).map(w => ({
        ...w,
        activeServerId: w.activeServerId === id ? nextActive : w.activeServerId,
      }));
      return {
        ...s,
        servers: newServers,
        activeServerId: s.activeServerId === id ? nextActive : s.activeServerId,
        workloads: updatedWorkloads,
      };
    });
  }, []);

  const renameServer = useCallback((id, label) => {
    setState(s => ({
      ...s,
      servers: s.servers.map(sv => (sv.id === id ? { ...sv, label } : sv)),
    }));
  }, []);

  const changeServerZone = useCallback((id, zoneName) => {
    setState(s => ({
      ...s,
      servers: s.servers.map(sv => (sv.id === id ? { ...sv, zoneName } : sv)),
    }));
  }, []);

  const switchActiveRegion = useCallback((zoneName) => {
    setState(s => {
      if (!s.activeServerId && s.servers.length === 0) {
        const newId = crypto.randomUUID();
        const newServers = [{ id: newId, label: `server-${zoneName}`, zoneName }];
        const updatedWorkloads = (s.workloads || []).map(w => ({ ...w, activeServerId: newId }));
        return {
          ...s,
          servers: newServers,
          activeServerId: newId,
          workloads: updatedWorkloads,
        };
      }
      if (s.activeServerId) {
        return {
          ...s,
          servers: s.servers.map(sv => (sv.id === s.activeServerId ? { ...sv, zoneName } : sv)),
        };
      }
      return s;
    });
  }, []);

  // Program Management
  const addProgram = useCallback((name, geoScope = 'World') => {
    setState(s => {
      const newP = {
        id: crypto.randomUUID(),
        name,
        geoScope,
      };
      return {
        ...s,
        programs: [...(s.programs || []), newP],
      };
    });
  }, []);

  const removeProgram = useCallback((id) => {
    setState(s => ({
      ...s,
      programs: (s.programs || []).filter(p => p.id !== id),
      workloads: (s.workloads || []).filter(w => w.programId !== id),
    }));
  }, []);

  const updateProgram = useCallback((id, updates) => {
    setState(s => ({
      ...s,
      programs: (s.programs || []).map(p => (p.id === id ? { ...p, ...updates } : p)),
    }));
  }, []);

  // Workload Management
  const addWorkloadToProgram = useCallback((programId, name, type = 'latency-sensitive', maxLatency = 200, weights = { carbon: 0.4, latency: 0.3, resources: 0.3 }) => {
    setState(s => {
      const newW = {
        id: crypto.randomUUID(),
        programId,
        name,
        type,
        maxLatency,
        weights: weights || { carbon: 0.4, latency: 0.3, resources: 0.3 },
        activeServerId: s.servers[0]?.id || null,
        switchingMode: s.switchingMode || 'manual',
      };
      return {
        ...s,
        workloads: [...(s.workloads || []), newW],
      };
    });
  }, []);

  const removeWorkload = useCallback((id) => {
    setState(s => ({
      ...s,
      workloads: (s.workloads || []).filter(w => w.id !== id),
    }));
  }, []);

  const updateWorkload = useCallback((id, updates) => {
    setState(s => ({
      ...s,
      workloads: (s.workloads || []).map(w => (w.id === id ? { ...w, ...updates } : w)),
    }));
  }, []);

  const setWorkloadActiveServer = useCallback((workloadId, activeServerId) => {
    updateWorkload(workloadId, { activeServerId });
  }, [updateWorkload]);

  const setWorkloadSwitchingMode = useCallback((workloadId, switchingMode) => {
    updateWorkload(workloadId, { switchingMode });
  }, [updateWorkload]);

  const switchWorkloadRegion = useCallback((workloadId, zoneName) => {
    setState(s => {
      const w = (s.workloads || []).find(item => item.id === workloadId);
      if (!w) return s;

      if (w.activeServerId && s.servers.some(sv => sv.id === w.activeServerId)) {
        return {
          ...s,
          servers: s.servers.map(sv => (sv.id === w.activeServerId ? { ...sv, zoneName } : sv)),
        };
      }

      const newId = crypto.randomUUID();
      const newServer = { id: newId, label: `server-${zoneName}`, zoneName };
      return {
        ...s,
        servers: [...s.servers, newServer],
        activeServerId: s.activeServerId || newId,
        workloads: s.workloads.map(item => item.id === workloadId ? { ...item, activeServerId: newId } : item),
      };
    });
  }, []);

  const setWeights = useCallback((weights) => setState(s => ({ ...s, weights })), []);
  const setMaxLatency = useCallback((maxLatency) => setState(s => ({ ...s, maxLatency })), []);
  const setSwitchingMode = useCallback((switchingMode) => setState(s => ({
    ...s,
    switchingMode,
    workloads: (s.workloads || []).map(w => ({ ...w, switchingMode })),
  })), []);
  const setActiveServerId = useCallback((activeServerId) => setState(s => ({ ...s, activeServerId })), []);

  return {
    ...state,
    addServer, removeServer, renameServer, changeServerZone, switchActiveRegion,
    addProgram, removeProgram, updateProgram, addWorkloadToProgram,
    removeWorkload, updateWorkload, setWorkloadActiveServer, setWorkloadSwitchingMode, switchWorkloadRegion,
    setWeights, setMaxLatency, setSwitchingMode, setActiveServerId,
  };
}

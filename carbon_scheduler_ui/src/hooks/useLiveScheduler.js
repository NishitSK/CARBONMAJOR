import { useState, useEffect, useRef } from 'react';

const API_BASE = '/api';
// Notional energy draw per scheduling decision, used only to turn a
// gCO2/kWh delta into an illustrative kg-CO2-avoided counter.
const ASSUMED_KWH_PER_DECISION = 0.5;
const SIM_HOUR_MS = 1000;

// All state/fetch/timer logic for the fake-data sandbox (today's live
// simulator: random drift, day simulation, live/fixed mode). Extracted
// unchanged from the original App.jsx so /playground behaves identically
// to the pre-revamp app.
export function useLiveScheduler() {
  const [regions, setRegions] = useState([]);
  const [results, setResults] = useState([]);
  const [rejected, setRejected] = useState([]);
  const [maxLatency, setMaxLatency] = useState(200);
  const [mode, setMode] = useState('fixed');
  const [weights, setWeights] = useState({ carbon: 0.4, latency: 0.3, resources: 0.3 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [isAutoSimulating, setIsAutoSimulating] = useState(false);
  const [demoMode, setDemoMode] = useState(false);
  const [debugMode, setDebugMode] = useState(false);
  const [explanation, setExplanation] = useState(null);
  const [cumulativeSavingsKg, setCumulativeSavingsKg] = useState(0);

  const [daySimOn, setDaySimOn] = useState(false);
  const [daySimPlaying, setDaySimPlaying] = useState(true);
  const [simHour, setSimHour] = useState(0);
  const [dailySeries, setDailySeries] = useState(null);

  const timerRef = useRef(null);
  const simTimerRef = useRef(null);
  const lastScoredKeyRef = useRef(null);

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, demoMode]);

  useEffect(() => {
    if (regions && regions.length > 0) {
      calculateScores();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [weights, maxLatency, regions, demoMode]);

  useEffect(() => {
    if (isAutoSimulating && !demoMode && !daySimOn) {
      timerRef.current = setInterval(() => {
        fetchDrift();
      }, 5000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAutoSimulating, regions, demoMode, daySimOn]);

  useEffect(() => {
    if (!daySimOn) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/regions/daily-series?mode=fixed`);
        const data = await res.json();
        if (!cancelled) {
          setDailySeries(data);
          setSimHour(0);
          setDaySimPlaying(true);
        }
      } catch (err) {
        console.error('Daily series fetch error:', err);
        setError('Failed to load day-simulation data.');
      }
    })();
    return () => { cancelled = true; };
  }, [daySimOn]);

  useEffect(() => {
    if (daySimOn && daySimPlaying && dailySeries) {
      simTimerRef.current = setInterval(() => {
        setSimHour(h => (h + 1) % 24);
      }, SIM_HOUR_MS);
    } else if (simTimerRef.current) {
      clearInterval(simTimerRef.current);
    }
    return () => {
      if (simTimerRef.current) clearInterval(simTimerRef.current);
    };
  }, [daySimOn, daySimPlaying, dailySeries]);

  useEffect(() => {
    if (!daySimOn || !dailySeries) return;
    const snapshot = dailySeries.regions.map(r => ({
      ...r,
      carbon: (dailySeries.series[r.name] || [])[simHour] ?? r.carbon
    }));
    setRegions(snapshot);
  }, [daySimOn, dailySeries, simHour]);

  const toggleDaySim = () => {
    const turningOn = !daySimOn;
    setDaySimOn(turningOn);
    if (turningOn) {
      setIsAutoSimulating(false);
      if (mode === 'live') setMode('fixed');
    } else {
      setDailySeries(null);
      fetchData();
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/regions?mode=${mode}&demo_mode=${demoMode}`);
      const data = await res.json();
      setRegions(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err) {
      setError('Failed to connect to backend API.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchDrift = async () => {
    if (!regions || regions.length === 0 || demoMode) return;
    try {
      const res = await fetch(`${API_BASE}/regions/drift`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ regions, demo_mode: demoMode })
      });
      const data = await res.json();
      setRegions(Array.isArray(data) ? data : regions);
    } catch (err) {
      console.error('Drift fetch error:', err);
    }
  };

  const calculateScores = async () => {
    try {
      const res = await fetch(`${API_BASE}/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ regions, weights, max_latency: maxLatency, demo_mode: demoMode })
      });
      const data = await res.json();
      if (data && data.success) {
        setResults(data.eligible || []);
        setRejected(data.rejected || []);
        setExplanation(data.explanation || null);

        const eligible = data.eligible || [];
        if (eligible.length > 0) {
          const best = eligible[0].region;
          const avgCarbon = eligible.reduce((sum, r) => sum + r.region.carbon, 0) / eligible.length;
          const savingsKg = Math.max(0, (avgCarbon - best.carbon) / 1000 * ASSUMED_KWH_PER_DECISION);

          const snapshotKey = JSON.stringify(regions.map(r => [r.name, r.carbon]));
          if (snapshotKey !== lastScoredKeyRef.current) {
            lastScoredKeyRef.current = snapshotKey;
            setCumulativeSavingsKg(prev => prev + savingsKg);
          }
        }
      } else {
        setResults([]);
        setRejected((data && data.rejected) || []);
        setExplanation(null);
      }
    } catch (err) {
      console.error('Scoring error:', err);
    }
  };

  const handleWeightChange = (key, val) => {
    setWeights(prev => ({ ...prev, [key]: parseFloat(val) }));
  };

  const exportCsv = () => {
    if (!results || results.length === 0) return;
    const headers = ['rank', 'region', 'carbon_g_per_kwh', 'latency_ms', 'resources_pct', 'score', 'strengths'];
    const rows = results.map(r => [
      r.rank, r.region.name, r.region.carbon, r.region.latency, r.region.resources, r.score,
      (r.metadata?.strengths || []).join('; ')
    ]);
    const rejectedRows = (rejected || []).map(r => ['-', r.name, '-', '-', '-', 'REJECTED', r.reason]);
    const csv = [headers, ...rows, ...rejectedRows]
      .map(row => row.map(v => `"${String(v).replace(/"/g, '""')}"`).join(','))
      .join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `carbon_scheduler_report_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const bestResult = results && results.length > 0 ? results[0] : null;
  const bestRegion = bestResult?.region;

  return {
    regions, results, rejected, maxLatency, setMaxLatency, mode, setMode, weights, handleWeightChange,
    loading, error,
    isAutoSimulating, setIsAutoSimulating, demoMode, setDemoMode, debugMode, setDebugMode,
    explanation, cumulativeSavingsKg,
    daySimOn, daySimPlaying, setDaySimPlaying, simHour, setSimHour, dailySeries, toggleDaySim,
    exportCsv, bestRegion,
  };
}

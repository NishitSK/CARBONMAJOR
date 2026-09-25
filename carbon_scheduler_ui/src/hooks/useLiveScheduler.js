import { useState, useEffect, useRef } from 'react';
import { FALLBACK_REGIONS } from '../data/fallbackTelemetry';

const API_BASE = '/api';
// Notional energy draw per scheduling decision, used only to turn a
// gCO2/kWh delta into an illustrative kg-CO2-avoided counter.
const ASSUMED_KWH_PER_DECISION = 0.5;
const SIM_HOUR_MS = 1000;

// All state/fetch/timer logic for the fake-data sandbox (today's live
// simulator: random drift, day simulation, live/fixed mode). Extracted
// unchanged from the original App.jsx so /playground behaves identically
// to the pre-revamp app.
export function useLiveScheduler(options = {}) {
  // allowedRegionNames: the regions the user actually has servers in. Empty or
  // absent means every region stays a candidate.
  const allowedRegionNames = options.allowedRegionNames;
  const [regions, setRegions] = useState([]);
  const [results, setResults] = useState([]);
  const [rejected, setRejected] = useState([]);
  const [selectedRegion, setSelectedRegion] = useState(null);
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

  const allowedKey = (allowedRegionNames || []).join('|');
  const candidateRegions = allowedRegionNames && allowedRegionNames.length > 0
    ? regions.filter(r => allowedRegionNames.includes(r.name))
    : regions;

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, demoMode]);

  useEffect(() => {
    if (candidateRegions && candidateRegions.length > 0) {
      calculateScores();
    } else {
      setResults([]);
      setRejected([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [weights, maxLatency, regions, demoMode, allowedKey]);

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
      if (res.ok) {
        const data = await res.json();
        setRegions(Array.isArray(data) ? data : FALLBACK_REGIONS);
        setError(null);
      } else {
        setRegions(FALLBACK_REGIONS);
      }
    } catch (err) {
      // Offline fallback: Use verified fallback regions
      setRegions(FALLBACK_REGIONS);
      setError(null);
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
        body: JSON.stringify({ regions: candidateRegions, weights, max_latency: maxLatency, demo_mode: demoMode })
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

          const snapshotKey = JSON.stringify(candidateRegions.map(r => [r.name, r.carbon]));
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
      // Offline fallback: Compute CADSS scores client-side
      const eligible = [];
      const rej = [];
      candidateRegions.forEach(r => {
        if (r.latency > maxLatency) {
          rej.push({ ...r, reason: `Latency (${r.latency}ms) exceeds SLA ceiling (${maxLatency}ms)` });
        } else {
          eligible.push(r);
        }
      });
      if (eligible.length > 0) {
        const minC = Math.min(...eligible.map(r => r.carbon));
        const maxC = Math.max(...eligible.map(r => r.carbon));
        const minL = Math.min(...eligible.map(r => r.latency));
        const maxL = Math.max(...eligible.map(r => r.latency));

        const scored = eligible.map(r => {
          const normC = maxC > minC ? (r.carbon - minC) / (maxC - minC) : 0;
          const normL = maxL > minL ? (r.latency - minL) / (maxL - minL) : 0;
          const score = (weights.carbon * normC) + (weights.latency * normL);
          return {
            region: r,
            score: parseFloat(score.toFixed(3)),
            metadata: { strengths: r.carbon < 100 ? ['Clean Power Grid'] : ['Low Latency'] }
          };
        }).sort((a, b) => a.score - b.score).map((item, idx) => ({ ...item, rank: idx + 1 }));

        setResults(scored);
        setRejected(rej);
        setExplanation(`Selected ${scored[0].region.name} as optimal with score ${scored[0].score}.`);
      }
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

  // Manual override from the rankings "Switch" button or a map click. Holds a
  // region name; the active placement falls back to the optimal region
  // whenever the chosen one is no longer eligible (e.g. SLA tightened).
  const selectRegion = (r) => setSelectedRegion(typeof r === 'string' ? r : r?.name ?? null);
  const resetSelection = () => setSelectedRegion(null);
  const activeResult = (selectedRegion && (results || []).find(r => r.region?.name === selectedRegion)) || bestResult;
  const activeRegion = activeResult?.region;
  const isOverride = !!(activeRegion && bestRegion && activeRegion.name !== bestRegion.name);
  const overrideImpact = isOverride
    ? {
        carbonDelta: activeRegion.carbon - bestRegion.carbon,
        latencyDelta: activeRegion.latency - bestRegion.latency,
        scoreDelta: activeResult.score - bestResult.score,
      }
    : null;

  useEffect(() => {
    if (selectedRegion && results.length > 0 && !results.some(r => r.region?.name === selectedRegion)) {
      setSelectedRegion(null);
    }
  }, [results, selectedRegion]);

  return {
    regions, results, rejected, rejectedRegions: rejected, selectedRegion, setSelectedRegion: selectRegion,
    activeRegion, activeResult, isOverride, overrideImpact, resetSelection,
    maxLatency, setMaxLatency, mode, setMode, weights, handleWeightChange,
    loading, error,
    isAutoSimulating, setIsAutoSimulating, demoMode, setDemoMode, debugMode, setDebugMode,
    explanation, cumulativeSavingsKg,
    daySimOn, daySimPlaying, setDaySimPlaying, simHour, setSimHour, dailySeries, toggleDaySim,
    exportCsv, bestRegion,
  };
}

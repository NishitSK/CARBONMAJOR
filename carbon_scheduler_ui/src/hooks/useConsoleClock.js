import { useState, useEffect, useRef, useCallback } from 'react';

const API_BASE = '/api';
const PLAY_INTERVAL_MS = 400;

export const GEO_SCOPES = {
  'World': { label: 'World (Global / All Regions)', icon: '🌍', zones: null },
  'Europe': { label: 'Europe', icon: '🇪🇺', zones: ['eu-west-1 (Ireland)', 'eu-central-1 (Frankfurt)', 'eu-north-1 (Sweden)', 'IE', 'DE', 'SE'] },
  'North America': { label: 'North America', icon: '🇺🇸', zones: ['us-east-1 (N. Virginia)', 'us-west-2 (Oregon)', 'us-east-2 (Ohio)', 'ca-central-1 (Canada)', 'US-MIDA-PJM', 'US-NW-PACW', 'US-MIDW-MISO', 'CA-QC'] },
  'South America': { label: 'South America', icon: '🇧🇷', zones: ['sa-east-1 (Sao Paulo)', 'BR'] },
  'South Asia': { label: 'South Asia', icon: '🇮🇳', zones: ['ap-south-1 (Mumbai)', 'IN-WE'] },
  'South East Asia': { label: 'South East Asia', icon: '🇸🇬', zones: ['ap-southeast-1 (Singapore)', 'SG'] },
  'East Asia': { label: 'East Asia', icon: '🇯🇵', zones: ['ap-northeast-1 (Tokyo)', 'JP'] },
  'Africa': { label: 'Africa', icon: '🇿🇦', zones: ['af-south-1 (Cape Town)', 'ZA'] },
  'Australia / Oceania': { label: 'Australia / Oceania', icon: '🇦🇺', zones: ['ap-southeast-2 (Sydney)', 'AU-NSW'] },
};

export function isZoneInScope(zoneName, geoScope) {
  if (!geoScope || geoScope === 'World') return true;
  const scopeDef = GEO_SCOPES[geoScope];
  if (!scopeDef || !scopeDef.zones) return true;
  const lowerName = zoneName.toLowerCase();
  return scopeDef.zones.some(z => lowerName.includes(z.toLowerCase()));
}

function sanitizeForApi(regions) {
  return (regions || []).map(r => ({
    name: r.name,
    carbon: r.carbon,
    latency: r.latency,
    resources: r.resources,
    lat: r.lat || 0.0,
    lng: r.lng || 0.0,
  }));
}

export function useConsoleClock(servers, weights, maxLatency, switchingMode, activeServerId, setActiveServerId, workloads = [], setWorkloadActiveServer = null, programs = []) {
  const [rangeStart, setRangeStart] = useState(null);
  const [nHours, setNHours] = useState(0);
  const [hourIndex, setHourIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [scoreResult, setScoreResult] = useState(null);
  const [recommendedServerId, setRecommendedServerId] = useState(null);
  const [workloadResults, setWorkloadResults] = useState({});
  const [zoneCarbon, setZoneCarbon] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const playTimerRef = useRef(null);
  const serversRef = useRef(servers);
  serversRef.current = servers;
  const workloadsRef = useRef(workloads);
  workloadsRef.current = workloads;
  const programsRef = useRef(programs);
  programsRef.current = programs;

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/regions/history/range`);
        const data = await res.json();
        setRangeStart(data.start);
        setNHours(data.n_hours);
        setHourIndex(0);
      } catch (err) {
        setError('Failed to load the real historical dataset range.');
        console.error(err);
      }
    })();
  }, []);

  useEffect(() => {
    if (!rangeStart || nHours === 0) return;
    const fleet = serversRef.current;
    const currentWorkloads = workloadsRef.current;
    const currentPrograms = programsRef.current;

    if (!fleet || fleet.length === 0) {
      setScoreResult(null);
      setRecommendedServerId(null);
      setWorkloadResults({});
      setZoneCarbon({});
      return;
    }
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const pad = (n) => String(n).padStart(2, '0');
        const start = new Date(rangeStart.slice(0, 19) + 'Z');
        const d = new Date(start.getTime() + hourIndex * 3600 * 1000);
        const ts = `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}.000000`;

        const histRes = await fetch(`${API_BASE}/regions/history/at?timestamp=${encodeURIComponent(ts)}`);
        if (!histRes.ok) throw new Error('No real data at this hour');
        const histData = await histRes.json();
        if (cancelled) return;

        const byZone = {};
        const ciMap = {};
        for (const r of histData.regions) {
          byZone[r.name] = r;
          ciMap[r.name] = r.carbon;
        }
        setZoneCarbon(ciMap);

        const serverRegions = fleet
          .filter(sv => byZone[sv.zoneName])
          .map(sv => ({ ...byZone[sv.zoneName], name: sv.id, zoneName: sv.zoneName }));

        if (serverRegions.length === 0) {
          setScoreResult(null);
          setRecommendedServerId(null);
          setWorkloadResults({});
          setLoading(false);
          return;
        }

        // 1. Global fleet scoring
        const scoreRes = await fetch(`${API_BASE}/score`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            regions: sanitizeForApi(serverRegions),
            weights,
            max_latency: maxLatency,
            demo_mode: false,
          }),
        });
        const scoreData = await scoreRes.json();
        if (cancelled) return;

        setScoreResult(scoreData);
        setError(null);

        if (scoreData.success) {
          const topServerId = scoreData.eligible[0]?.region?.name;
          setRecommendedServerId(topServerId || null);
          if (switchingMode === 'auto' && topServerId && topServerId !== activeServerId && setActiveServerId) {
            setActiveServerId(topServerId);
          }
        } else {
          setRecommendedServerId(null);
        }

        // 2. Per-workload & Per-Program geo-scoped scoring & simulation metrics
        if (currentWorkloads && currentWorkloads.length > 0) {
          const newWResults = {};
          const programMap = Object.fromEntries((currentPrograms || []).map(p => [p.id, p]));

          for (const w of currentWorkloads) {
            const parentProgram = programMap[w.programId];
            const geoScope = parentProgram?.geoScope || 'World';
            const wMaxLat = w.maxLatency || maxLatency;
            const wWeights = w.weights || weights;
            const wMode = w.switchingMode || switchingMode;

            const activeSv = fleet.find(s => s.id === w.activeServerId) || fleet[0];

            // Candidate pool for this program box
            const scopedFleetRegions = serverRegions.filter(sv => isZoneInScope(sv.zoneName, geoScope));
            const scopedAllZones = (histData.regions || [])
              .filter(r => isZoneInScope(r.name, geoScope))
              .map(r => ({ ...r, name: r.name, zoneName: r.name }));

            const candidatePool = scopedFleetRegions.length > 0 ? scopedFleetRegions : scopedAllZones;

            let wScoreData = { success: false, eligible: [], rejected: [] };
            if (candidatePool.length > 0) {
              const wScoreRes = await fetch(`${API_BASE}/score`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  regions: sanitizeForApi(candidatePool),
                  weights: wWeights,
                  max_latency: wMaxLat,
                  demo_mode: false,
                }),
              });
              wScoreData = await wScoreRes.json();
            }

            const wRecId = wScoreData.success && wScoreData.eligible.length > 0 ? wScoreData.eligible[0]?.region?.name : null;
            const topZoneName = wScoreData.success && wScoreData.eligible.length > 0 ? (wScoreData.eligible[0]?.region?.zoneName || wScoreData.eligible[0]?.region?.name) : null;

            // Find active server result in eligible list
            let activeItem = (wScoreData.eligible || []).find(
              item => item.region?.name === w.activeServerId ||
                      (activeSv && item.region?.name === activeSv.id) ||
                      (activeSv && item.region?.zoneName === activeSv.zoneName)
            );

            if (!activeItem && wScoreData.eligible && wScoreData.eligible.length > 0) {
              activeItem = wScoreData.eligible[0];
            }

            const activeReject = (wScoreData.rejected || []).find(
              r => r.name === w.activeServerId || (activeSv && (r.name === activeSv.id || r.name === activeSv.zoneName))
            );

            newWResults[w.id] = {
              scoreResult: wScoreData,
              recommendedServerId: wRecId,
              recommendedZoneName: topZoneName,
              geoScope,
              activeServerScore: activeItem ? activeItem.score : null,
              activeServerMeta: activeItem ? activeItem.metadata : null,
              activeServerLatency: activeItem ? (activeItem.region?.latency_ms || activeItem.region?.latency) : null,
              activeServerRejected: !!activeReject,
              rejectReason: activeReject ? activeReject.reason : null,
            };

            // In Auto Mode: Automatically change region to cleanest data center region in that part of the world
            if (wMode === 'auto' && setWorkloadActiveServer) {
              if (wRecId && wRecId !== w.activeServerId) {
                setWorkloadActiveServer(w.id, wRecId);
              }
            }
          }
          if (!cancelled) setWorkloadResults(newWResults);
        }
      } catch (err) {
        if (!cancelled) {
          setError('Failed to load the real decision for this hour.');
          console.error(err);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rangeStart, hourIndex, nHours, servers, weights.carbon, weights.latency, weights.resources, maxLatency, switchingMode, JSON.stringify(workloads), JSON.stringify(programs)]);

  useEffect(() => {
    if (playing && nHours > 0) {
      playTimerRef.current = setInterval(() => {
        setHourIndex(h => (h + 1 >= nHours ? 0 : h + 1));
      }, PLAY_INTERVAL_MS);
    } else if (playTimerRef.current) {
      clearInterval(playTimerRef.current);
    }
    return () => { if (playTimerRef.current) clearInterval(playTimerRef.current); };
  }, [playing, nHours]);

  const stepHour = useCallback((delta) => {
    setPlaying(false);
    setHourIndex(h => Math.min(Math.max(h + delta, 0), Math.max(nHours - 1, 0)));
  }, [nHours]);

  const scrubTo = useCallback((index) => {
    setPlaying(false);
    setHourIndex(Math.min(Math.max(index, 0), Math.max(nHours - 1, 0)));
  }, [nHours]);

  const applyRecommendation = useCallback(() => {
    if (recommendedServerId && setActiveServerId) setActiveServerId(recommendedServerId);
  }, [recommendedServerId, setActiveServerId]);

  const pad = (n) => String(n).padStart(2, '0');
  let currentTimestamp = null;
  if (rangeStart && nHours > 0) {
    const start = new Date(rangeStart.slice(0, 19) + 'Z');
    const d = new Date(start.getTime() + hourIndex * 3600 * 1000);
    currentTimestamp = `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}.000000`;
  }

  return {
    nHours, hourIndex, currentTimestamp,
    playing, setPlaying, stepHour, scrubTo,
    scoreResult, recommendedServerId, applyRecommendation,
    workloadResults, zoneCarbon,
    loading, error,
  };
}

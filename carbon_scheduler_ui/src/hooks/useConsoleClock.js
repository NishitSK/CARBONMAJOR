import { useState, useEffect, useRef, useCallback } from 'react';

const API_BASE = '/api';
const PLAY_INTERVAL_MS = 400;

function isoAtHour(rangeStartIso, hourOffset) {
  const start = new Date(rangeStartIso.slice(0, 19) + 'Z');
  const d = new Date(start.getTime() + hourOffset * 3600 * 1000);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}.000000`;
}

// Generalizes useHistoricalReplay's play/step/scrub pattern to score the
// CLIENT'S OWN fleet instead of the fixed pool: each server's carbon
// intensity is pulled from whichever real zone the client assigned it to
// (via /regions/history/at, same real data, no fabrication), each server
// scored as a Region named after its own label, then fed through the
// unmodified /score endpoint. Auto mode applies the top pick immediately;
// manual mode only surfaces it as a pending recommendation.
export function useConsoleClock(servers, weights, maxLatency, switchingMode, activeServerId, setActiveServerId) {
  const [rangeStart, setRangeStart] = useState(null);
  const [nHours, setNHours] = useState(0);
  const [hourIndex, setHourIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [scoreResult, setScoreResult] = useState(null);
  const [recommendedServerId, setRecommendedServerId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const playTimerRef = useRef(null);
  const serversRef = useRef(servers);
  serversRef.current = servers;

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
    if (!fleet || fleet.length === 0) {
      setScoreResult(null);
      setRecommendedServerId(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const ts = isoAtHour(rangeStart, hourIndex);
        const histRes = await fetch(`${API_BASE}/regions/history/at?timestamp=${encodeURIComponent(ts)}`);
        if (!histRes.ok) throw new Error('No real data at this hour');
        const histData = await histRes.json();
        if (cancelled) return;

        const byZone = {};
        for (const r of histData.regions) byZone[r.name] = r;

        const serverRegions = fleet
          .filter(sv => byZone[sv.zoneName])
          .map(sv => ({ ...byZone[sv.zoneName], name: sv.id }));

        if (serverRegions.length === 0) {
          setScoreResult(null);
          setRecommendedServerId(null);
          setLoading(false);
          return;
        }

        const scoreRes = await fetch(`${API_BASE}/score`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            regions: serverRegions,
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
          if (switchingMode === 'auto' && topServerId && topServerId !== activeServerId) {
            setActiveServerId(topServerId);
          }
        } else {
          setRecommendedServerId(null);
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
  }, [rangeStart, hourIndex, nHours, servers, weights.carbon, weights.latency, weights.resources, maxLatency, switchingMode]);

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
    if (recommendedServerId) setActiveServerId(recommendedServerId);
  }, [recommendedServerId, setActiveServerId]);

  const currentTimestamp = rangeStart ? isoAtHour(rangeStart, hourIndex) : null;

  return {
    nHours, hourIndex, currentTimestamp,
    playing, setPlaying, stepHour, scrubTo,
    scoreResult, recommendedServerId, applyRecommendation,
    loading, error,
  };
}

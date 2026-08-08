import { useState, useEffect, useRef, useCallback } from 'react';

const API_BASE = '/api';
const PLAY_INTERVAL_MS = 400;
// A real "Canada wins" decision cycle documented in the paper's own
// Methodology section (Table I) -- a more interesting default starting
// point for a first-time visitor than hour zero of the dataset.
const DEFAULT_START_ISO = '2021-01-04T12:00:00.000000';

function isoAtHour(rangeStartIso, hourOffset) {
  if (!rangeStartIso) return '';
  const start = new Date(rangeStartIso.slice(0, 19) + 'Z');
  const d = new Date(start.getTime() + hourOffset * 3600 * 1000);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}.000000`;
}

function hourOffsetOf(rangeStartIso, targetIso) {
  if (!rangeStartIso || !targetIso) return 0;
  const start = new Date(rangeStartIso.slice(0, 19) + 'Z').getTime();
  const target = new Date(targetIso.slice(0, 19) + 'Z').getTime();
  return Math.round((target - start) / 3600000);
}

// Real 2021-2025 historical-replay model showcase: fetches the REAL
// carbon-intensity data for whatever hour the scrubber is on
// (/regions/history/at) and feeds it into the same, unmodified /score
// endpoint every other part of this app uses. Nothing here is synthetic.
export function useHistoricalReplay() {
  const [rangeStart, setRangeStart] = useState(null);
  const [nHours, setNHours] = useState(0);
  const [hourIndex, setHourIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [regions, setRegions] = useState([]);
  const [scoreResult, setScoreResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const playTimerRef = useRef(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/regions/history/range`);
        const data = await res.json();
        setRangeStart(data.start);
        setNHours(data.n_hours);
        const defaultOffset = hourOffsetOf(data.start, DEFAULT_START_ISO);
        setHourIndex(Math.min(Math.max(defaultOffset, 0), data.n_hours - 1));
      } catch (err) {
        setError('Failed to load the real historical dataset range.');
        console.error(err);
      }
    })();
  }, []);

  useEffect(() => {
    if (!rangeStart || nHours === 0) return;
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const ts = isoAtHour(rangeStart, hourIndex);
        const histRes = await fetch(`${API_BASE}/regions/history/at?timestamp=${encodeURIComponent(ts)}`);
        if (!histRes.ok) throw new Error('No real data at this hour');
        const histData = await histRes.json();
        if (cancelled) return;
        setRegions(histData.regions);

        const scoreRes = await fetch(`${API_BASE}/score`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            regions: histData.regions,
            weights: { carbon: 0.4, latency: 0.3, resources: 0.3 },
            max_latency: 200,
            demo_mode: false,
          }),
        });
        const scoreData = await scoreRes.json();
        if (!cancelled) {
          setScoreResult(scoreData);
          setError(null);
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
  }, [rangeStart, hourIndex, nHours]);

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

  const currentTimestamp = rangeStart ? isoAtHour(rangeStart, hourIndex) : null;
  const bestRegion = scoreResult?.success ? scoreResult.eligible[0]?.region : null;

  return {
    nHours, hourIndex, currentTimestamp,
    playing, setPlaying, stepHour, scrubTo,
    regions, scoreResult, bestRegion, loading, error,
  };
}

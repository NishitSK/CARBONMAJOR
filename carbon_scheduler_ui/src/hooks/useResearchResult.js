import { useState, useEffect } from 'react';
import { fetchResearchResult } from '../api/researchApi';

// Fetches one research result JSON by id, with loading/error state.
// Every research chart/stat on the site is ultimately backed by this --
// no hardcoded numbers, everything traces to the actual file on disk.
export function useResearchResult(resultId) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchResearchResult(resultId)
      .then(d => { if (!cancelled) { setData(d); setError(null); } })
      .catch(err => { if (!cancelled) { setError(err.message); console.error(err); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [resultId]);

  return { data, loading, error };
}

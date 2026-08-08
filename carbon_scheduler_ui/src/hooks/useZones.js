import { useState, useEffect } from 'react';

// Real electricity zones this system has real carbon data for -- powers the
// Client Console's "add a server" zone picker (see GET /regions/zones).
export function useZones() {
  const [zones, setZones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('/api/regions/zones')
      .then(r => {
        if (!r.ok) throw new Error(`Zone list request failed (${r.status})`);
        return r.json();
      })
      .then(setZones)
      .catch(err => {
        console.error('Failed to load zones', err);
        setError('Could not load the zone list (check the API on port 8001).');
      })
      .finally(() => setLoading(false));
  }, []);

  return { zones, loading, error };
}

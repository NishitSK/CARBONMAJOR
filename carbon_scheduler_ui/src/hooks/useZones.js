import { useState, useEffect } from 'react';

// Real electricity zones this system has real carbon data for -- powers the
// Client Console's "add a server" zone picker (see GET /regions/zones).
export function useZones() {
  const [zones, setZones] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/regions/zones')
      .then(r => r.json())
      .then(setZones)
      .catch(err => console.error('Failed to load zones', err))
      .finally(() => setLoading(false));
  }, []);

  return { zones, loading };
}

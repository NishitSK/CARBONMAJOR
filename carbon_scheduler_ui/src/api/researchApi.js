const API_BASE = '/api';

const _cache = new Map();

export async function fetchManifest() {
  const res = await fetch(`${API_BASE}/research/manifest`);
  if (!res.ok) throw new Error('Failed to load research manifest');
  return res.json();
}

export async function fetchResearchResult(resultId) {
  if (_cache.has(resultId)) return _cache.get(resultId);
  const res = await fetch(`${API_BASE}/research/${resultId}`);
  if (!res.ok) throw new Error(`Failed to load research result: ${resultId}`);
  const data = await res.json();
  _cache.set(resultId, data);
  return data;
}

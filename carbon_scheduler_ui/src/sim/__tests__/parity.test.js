// Golden parity check: the in-browser scoring port must reproduce the real
// Python Scheduler (services/scheduler.py). Regenerate the fixture with
// `python scripts/export_scoring_fixture.py` from carbon_scheduler/.
import { describe, it, expect } from 'vitest';
import { score } from '../scoring';
import fixture from './fixtures/scoring_parity.json';

describe('scoring.js matches services/scheduler.py', () => {
  for (const c of fixture.cases) {
    it(c.id, () => {
      const js = score(fixture.regions, c.weights, c.max_latency);
      const py = c.expected;

      expect(js.success).toBe(py.success);
      expect(js.rejected.map((r) => r.name)).toEqual(py.rejected);
      expect(js.eligible.map((e) => e.region.name)).toEqual(py.eligible.map((e) => e.name));

      js.eligible.forEach((e, i) => {
        const p = py.eligible[i];
        expect(e.score).toBeCloseTo(p.score, 3);
        expect(e.metadata.c_norm).toBeCloseTo(p.c_norm, 3);
        expect(e.metadata.l_norm).toBeCloseTo(p.l_norm, 3);
        expect(e.metadata.r_penalty).toBeCloseTo(p.r_penalty, 3);
        expect(e.metadata.strengths).toEqual(p.strengths);
      });

      if (py.success) expect(js.explanation.summary).toBe(py.summary);
    });
  }
});

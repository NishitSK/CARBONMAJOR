import { describe, it, expect } from 'vitest';
import { filterRegions, calculateScores, score } from '../scoring';

const WEIGHTS = { carbon: 0.4, latency: 0.3, resources: 0.3 };

describe('filterRegions', () => {
  it('keeps regions at or under the latency ceiling', () => {
    const regions = [
      { name: 'a', carbon: 10, latency: 100, resources: 50 },
      { name: 'b', carbon: 10, latency: 200, resources: 50 },
      { name: 'c', carbon: 10, latency: 201, resources: 50 },
    ];
    expect(filterRegions(regions, 200).map((r) => r.name)).toEqual(['a', 'b']);
  });
});

describe('calculateScores', () => {
  it('does not penalise latency at or below the 200 ms indifference threshold', () => {
    const scored = calculateScores(
      [
        { name: 'near', carbon: 100, latency: 10, resources: 80 },
        { name: 'far', carbon: 100, latency: 199, resources: 80 },
      ],
      WEIGHTS
    );
    expect(scored.every((s) => s.metadata.l_norm === 0)).toBe(true);
  });

  it('ranks lower carbon first when everything else is equal', () => {
    const scored = calculateScores(
      [
        { name: 'dirty', carbon: 600, latency: 50, resources: 80 },
        { name: 'clean', carbon: 30, latency: 50, resources: 80 },
      ],
      WEIGHTS
    );
    expect(scored[0].region.name).toBe('clean');
    expect(scored.map((s) => s.rank)).toEqual([1, 2]);
  });

  it('breaks exact score ties by higher resources', () => {
    const scored = calculateScores(
      [
        { name: 'low-res', carbon: 100, latency: 50, resources: 40 },
        { name: 'high-res', carbon: 100, latency: 50, resources: 90 },
      ],
      { carbon: 0.5, latency: 0.5, resources: 0 }
    );
    expect(scored[0].region.name).toBe('high-res');
  });

  it('returns an empty list for no regions', () => {
    expect(calculateScores([], WEIGHTS)).toEqual([]);
  });
});

describe('score', () => {
  it('reports failure with every region rejected when none meet the SLA', () => {
    const result = score([{ name: 'a', carbon: 10, latency: 300, resources: 50 }], WEIGHTS, 100);
    expect(result.success).toBe(false);
    expect(result.rejected.map((r) => r.name)).toEqual(['a']);
  });
});

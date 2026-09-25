import { describe, it, expect } from 'vitest';
import { runAudit, auditWorkload } from '../audit';
import { PRESETS, findPreset } from '../presets';
import { JURISDICTIONS } from '../jurisdictions';

// Fixed clock so results don't depend on when the suite runs.
const OPTS = { hour: 14, dayIndex: 0 };

function withCeiling(preset) {
  return preset.workloads.map((w) => ({ ...w, maxInrPerTonne: preset.maxInrPerTonne }));
}

function verdictsByName(preset, opts = OPTS) {
  const { decisions } = runAudit(withCeiling(preset), opts);
  return Object.fromEntries(decisions.map((d) => [d.workload.name, d]));
}

describe('QuickBite audit', () => {
  const byName = verdictsByName(findPreset('quickbite'));

  it('never moves customer-facing personal-data workloads, citing DPDP', () => {
    for (const name of ['Order & Dispatch API', 'Rider Live Tracking', 'Payments Gateway']) {
      expect(byName[name].verdict).toBe('never_move');
      expect(byName[name].reason).toMatch(/DPDP/);
    }
  });

  it('blocks the egress-heavy log archive on cost', () => {
    expect(byName['Log Archive & Compaction'].verdict).toBe('blocked_by_cost');
  });

  it('moves anonymised ML training to a cleaner region', () => {
    const d = byName['Recommendation Model Training'];
    expect(d.verdict).toBe('move');
    expect(d.recommendedRegion).not.toBe(d.currentRegion);
    expect(d.tonnesCo2PerYear).toBeGreaterThan(0);
  });

  it('produces a mix of verdicts rather than one answer for everything', () => {
    const { summary } = runAudit(withCeiling(findPreset('quickbite')), OPTS);
    expect(Object.keys(summary.counts).length).toBeGreaterThanOrEqual(3);
  });
});

describe('audit invariants (all presets)', () => {
  const EU = JURISDICTIONS.eu_gdpr.allowed;
  const INDIA = JURISDICTIONS.india_dpdp.allowed;

  for (const preset of PRESETS) {
    it(`${preset.name}: recommendations respect residency rules`, () => {
      const { decisions } = runAudit(withCeiling(preset), OPTS);
      for (const d of decisions) {
        const permitted = [...d.allowedRegions, d.currentRegion];
        expect(permitted).toContain(d.recommendedRegion);
        if (d.workload.dataClass === 'personal_india') {
          d.allowedRegions.forEach((r) => expect(INDIA).toContain(r));
        }
        if (d.workload.dataClass === 'personal_eu') {
          d.allowedRegions.forEach((r) => expect(EU).toContain(r));
        }
      }
    });

    it(`${preset.name}: deterministic for the same clock`, () => {
      expect(runAudit(withCeiling(preset), OPTS)).toEqual(runAudit(withCeiling(preset), OPTS));
    });
  }
});

describe('workload already outside its own rules', () => {
  // Singapore + a 50ms SLA: only Mumbai is reachable in time, so the workload
  // is breaching its own SLA today. It must not be told to stay put.
  const stranded = {
    name: 'Singapore Checkout API',
    kind: 'customer-facing',
    dataClass: 'anonymised',
    jurisdiction: 'apac_sovereign',
    latencySlaMs: 50,
    currentRegion: 'ap-southeast-1 (Singapore)',
    vcpus: 32,
    hoursPerMonth: 730,
    dataOutGbPerMonth: 100,
  };

  it('flags it instead of recommending it stays', () => {
    const d = auditWorkload(stranded, OPTS);
    expect(d.verdict).toBe('non_compliant');
    expect(d.recommendedRegion).toBe('ap-south-1 (Mumbai)');
    expect(d.recommendedRegion).not.toBe(d.currentRegion);
    expect(d.reason).toMatch(/which its own rules exclude/);
    expect(d.allowedRegions).not.toContain('ap-southeast-1 (Singapore)');
  });

  it('does not claim a carbon saving for a workload out of compliance', () => {
    expect(auditWorkload(stranded, OPTS).tonnesCo2PerYear).toBeNull();
  });

  it('names latency, not residency, when the region is legal but too far away', () => {
    expect(auditWorkload(stranded, OPTS).reason).toMatch(/over its 50ms SLA/);
  });

  it('says no region qualifies when residency and SLA cannot both be met', () => {
    // EU personal data with a 120ms SLA, latency measured from India: every EU
    // region is legal but none is close enough.
    const eu = { ...stranded, name: 'EU API', dataClass: 'personal_eu', latencySlaMs: 120, currentRegion: 'eu-west-1 (Ireland)' };
    const d = auditWorkload(eu, OPTS);
    expect(d.verdict).toBe('non_compliant');
    expect(d.reason).toMatch(/No region satisfies both/);
    expect(d.reason).not.toMatch(/must stay in the EU/);
  });
});

describe('shift in time', () => {
  // Deferrable workload already in the cleanest allowed region: the only
  // possible improvement is waiting for a cleaner hour.
  const workload = {
    name: 'Nightly batch (Canada)',
    kind: 'deferrable',
    dataClass: 'anonymised',
    jurisdiction: 'americas_sovereign',
    latencySlaMs: 5000,
    currentRegion: 'ca-central-1 (Canada)',
    vcpus: 32,
    hoursPerMonth: 300,
    dataOutGbPerMonth: 10,
    deadlineFlexHours: 12,
  };

  it('only ever stays or shifts, and a shift always waits a positive number of hours', () => {
    const decisions = Array.from({ length: 24 }, (_, hour) => auditWorkload(workload, { hour, dayIndex: 0 }));
    for (const d of decisions) {
      expect(['stay', 'shift_time']).toContain(d.verdict);
      if (d.verdict === 'shift_time') {
        expect(d.shiftHours).toBeGreaterThan(0);
        expect(d.tonnesCo2PerYear).toBeGreaterThanOrEqual(0);
      }
    }
  });
});

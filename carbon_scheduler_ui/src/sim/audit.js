// The Workload Placement Audit — CADSS's customer-facing product logic.
//
// Per the project's own finding (static region selection captures ~97% of
// achievable carbon savings; real-time adaptivity only +2.7% held-out), the
// valuable decision is WHERE to place each workload, made once — not a live
// scheduler ticking every few seconds. This module answers, per workload:
// can it move, should it, and if not, why not (named rule, not a black box).
import { REGIONS, findRegion } from './regions';
import { allowedRegionsFor } from './jurisdictions';
import { calculateScores } from './scoring';
import { carbonAtHour, currentHour } from './carbonModel';
import { bestDelayedHour } from './forecast';

// Illustrative constants for the energy/cost model. All clearly estimates —
// surfaced in the report's methodology section, never presented as billing-grade.
const WATTS_PER_VCPU = 25; // typical cloud vCPU average draw under load
const PUE = 1.15; // datacenter power-usage effectiveness
// Policy ceiling: max INR willing to pay per tonne CO2 avoided. ~₹12,000/t
// (~$140/t) sits inside the range of real corporate internal carbon prices
// (roughly $40-200/t across published corporate figures).
const DEFAULT_MAX_INR_PER_TONNE = 12000;

function annualEnergyKwh(vcpus, hoursPerMonth) {
  return (vcpus * WATTS_PER_VCPU * hoursPerMonth * 12 * PUE) / 1000;
}

function annualComputeInr(region, vcpus, hoursPerMonth) {
  return region.computeInrPerVcpuHr * vcpus * hoursPerMonth * 12;
}

function annualEgressInr(region, dataOutGbPerMonth) {
  return region.egressInrPerGb * dataOutGbPerMonth * 12;
}

function reasonForRestriction(workload, allowedNames) {
  if (workload.dataClass === 'personal_india') {
    return 'Personal data — must stay in India under the DPDP Act';
  }
  if (workload.dataClass === 'personal_eu') {
    return 'Personal data — must stay in the EU under GDPR';
  }
  if (allowedNames.length === 1) {
    return `Needs ≤${workload.latencySlaMs}ms — only ${allowedNames[0]} qualifies from this user base`;
  }
  return `Restricted to ${workload.jurisdiction || 'its'} jurisdiction`;
}

// One workload -> a full audit decision.
export function auditWorkload(workload, opts = {}) {
  const dayIndex = opts.dayIndex ?? 0;
  const hour = opts.hour ?? currentHour();
  const maxInrPerTonne = workload.maxInrPerTonne ?? DEFAULT_MAX_INR_PER_TONNE;

  const currentRegion = findRegion(workload.currentRegion);
  const allRegionNames = REGIONS.map((r) => r.name);
  const jurisdictionAllowed = allowedRegionsFor(workload.dataClass, workload.jurisdiction, allRegionNames);
  const latencyAllowed = REGIONS.filter((r) => r.latencyFromIndia <= workload.latencySlaMs).map((r) => r.name);
  const allowedNames = jurisdictionAllowed.filter((n) => latencyAllowed.includes(n));

  const base = {
    workload,
    currentRegion: workload.currentRegion,
    allowedRegions: allowedNames,
  };

  const currentCi = currentRegion ? carbonAtHour(currentRegion, hour, dayIndex) : null;
  const energyKwhPerYear = round2(annualEnergyKwh(workload.vcpus, workload.hoursPerMonth));

  // Already outside its own rules: the region it runs in today is not one its
  // data class, jurisdiction and SLA permit. That is a breach to fix, not a
  // placement to optimise, so it is answered before anything else.
  if (!allowedNames.includes(workload.currentRegion)) {
    const target = REGIONS.filter((r) => allowedNames.includes(r.name))
      .map((r) => ({ name: r.name, ci: carbonAtHour(r, hour, dayIndex) }))
      .sort((a, b) => a.ci - b.ci)[0];
    // Name the rule that is actually broken: a region can be legal for the
    // data but too far from the users, or close enough but not legal.
    const residencyOk = jurisdictionAllowed.includes(workload.currentRegion);
    const why = residencyOk
      ? `${workload.currentRegion} is ${currentRegion ? currentRegion.latencyFromIndia : '?'}ms from its users, over its ${workload.latencySlaMs}ms SLA`
      : reasonForRestriction(workload, allowedNames);
    return {
      ...base,
      verdict: 'non_compliant',
      reason: target
        ? `Runs in ${workload.currentRegion}, which its own rules exclude \u2014 ${why}`
        : `No region satisfies both its residency rule and its ${workload.latencySlaMs}ms SLA \u2014 ${why}`,
      recommendedRegion: target ? target.name : workload.currentRegion,
      tonnesCo2PerYear: null,
      inrDeltaPerYear: 0,
      shiftHours: 0,
      details: {
        currentCi: currentCi != null ? round2(currentCi) : null,
        energyKwhPerYear,
        allowedCount: allowedNames.length,
      },
      suggestion: target
        ? `Move it to ${target.name} to satisfy the rule first. No carbon saving is estimated while a workload sits outside its own residency or latency limits.`
        : `No region satisfies both its residency rule and its ${workload.latencySlaMs}ms SLA. Relax the SLA, or re-check the data class \u2014 as configured this workload cannot run compliantly anywhere.`,
    };
  }

  // Never move: no other region is both legally and technically eligible.
  if (allowedNames.length <= 1) {
    return {
      ...base,
      verdict: 'never_move',
      reason: reasonForRestriction(workload, allowedNames),
      recommendedRegion: workload.currentRegion,
      tonnesCo2PerYear: null,
      inrDeltaPerYear: 0,
      shiftHours: 0,
      details: { currentCi: currentCi != null ? round2(currentCi) : null, energyKwhPerYear, allowedCount: allowedNames.length },
      suggestion: workload.kind === 'customer-facing'
        ? 'Relocation is closed off by rule. The levers left are efficiency: right-sizing, autoscaling, and cutting idle capacity.'
        : 'Relocation is closed off by rule. Consider running it in cleaner hours within this region, or splitting out any anonymised part that could move.',
    };
  }

  const candidateRegions = REGIONS.filter((r) => allowedNames.includes(r.name)).map((r) => ({
    name: r.name,
    carbon: carbonAtHour(r, hour, dayIndex),
    latency: r.latencyFromIndia,
    resources: 80,
  }));

  const weights = { carbon: 0.4, latency: 0.3, resources: 0.3 };
  const scored = calculateScores(candidateRegions, weights);
  // The comparison behind the verdict, so "why not that other region?" is answerable.
  const ranked = scored.slice(0, 5).map((s) => ({
    name: s.region.name,
    ci: round2(s.region.carbon),
    latency: s.region.latency,
    score: s.score,
  }));
  const best = scored[0];
  const bestRegion = findRegion(best.region.name);
  const bestCi = best.region.carbon;

  // Deferrable + already-best-region-but-not-best-hour -> consider a time shift.
  if (workload.kind === 'deferrable' && best.region.name === workload.currentRegion) {
    const model = 'lstm';
    const delay = bestDelayedHour(currentRegion, hour, Math.min(12, workload.deadlineFlexHours || 6), model, dayIndex);
    if (delay.guardPassed) {
      const energy = annualEnergyKwh(workload.vcpus, workload.hoursPerMonth);
      const tonnes = (energy * (currentCi - delay.predictedCi)) / 1e6;
      return {
        ...base,
        verdict: 'shift_time',
        reason: `Same region, cleaner hour: wait ${delay.offsetHours}h for a verified-confident forecast dip`,
        recommendedRegion: workload.currentRegion,
        shiftHours: delay.offsetHours,
        tonnesCo2PerYear: round2(tonnes),
        inrDeltaPerYear: 0,
        forecastModel: model,
        forecastSavingsPct: round2(delay.savingsPct),
        details: {
          currentCi: round2(currentCi),
          predictedCi: round2(delay.predictedCi),
          savingsPct: round2(delay.savingsPct),
          energyKwhPerYear,
          ranked,
        },
        suggestion: `Start it about ${delay.offsetHours}h later (cron window or queue delay). No region change, no egress cost, and the guard blocks the wait if the forecast is not trustworthy enough.`,
      };
    }
  }

  if (best.region.name === workload.currentRegion) {
    return {
      ...base,
      verdict: 'stay',
      reason: 'Already the cleanest region this workload is allowed to use',
      recommendedRegion: workload.currentRegion,
      tonnesCo2PerYear: 0,
      inrDeltaPerYear: 0,
      shiftHours: 0,
      details: { currentCi: round2(currentCi), energyKwhPerYear, allowedCount: allowedNames.length, ranked },
      suggestion: 'Nothing to change. Re-run the audit if its SLA, data class or size changes, or when region prices move.',
    };
  }

  // Candidate move — check the cost policy before recommending it.
  const energy = annualEnergyKwh(workload.vcpus, workload.hoursPerMonth);
  const tonnesSaved = (energy * Math.max(0, currentCi - bestCi)) / 1e6;

  const currentComputeInr = annualComputeInr(currentRegion, workload.vcpus, workload.hoursPerMonth);
  const bestComputeInr = annualComputeInr(bestRegion, workload.vcpus, workload.hoursPerMonth);
  const egressInr = annualEgressInr(bestRegion, workload.dataOutGbPerMonth || 0);
  const inrDelta = bestComputeInr + egressInr - currentComputeInr;

  const inrPerTonne = tonnesSaved > 0 ? inrDelta / tonnesSaved : Infinity;

  if (tonnesSaved > 0 && inrDelta > 0 && inrPerTonne > maxInrPerTonne) {
    return {
      ...base,
      verdict: 'blocked_by_cost',
      reason: `Moving would cost ≈₹${Math.round(inrPerTonne).toLocaleString('en-IN')}/tonne avoided — above the ₹${maxInrPerTonne.toLocaleString('en-IN')}/tonne policy ceiling (egress ≈₹${Math.round(egressInr).toLocaleString('en-IN')}/yr)`,
      recommendedRegion: workload.currentRegion,
      tonnesCo2PerYear: 0,
      inrDeltaPerYear: 0,
      shiftHours: 0,
      wouldSaveTonnes: round2(tonnesSaved),
      wouldCostInr: round2(inrDelta),
      details: {
        currentCi: round2(currentCi),
        bestCi: round2(bestCi),
        bestRegion: bestRegion.name,
        energyKwhPerYear,
        inrPerTonne: Math.round(inrPerTonne),
        egressInrPerYear: round2(egressInr),
        breakEvenCeilingInrPerTonne: Math.ceil(inrPerTonne / 500) * 500,
        ranked,
      },
      suggestion: `Raising the ceiling to about \u20b9${Math.ceil(inrPerTonne / 500) * 500}/tonne would make this a recommended move. Otherwise cut the ${Math.round(workload.dataOutGbPerMonth || 0)} GB/month of egress (caching, compression, keeping reads in-region) and re-run.`,
    };
  }

  return {
    ...base,
    verdict: 'move',
    reason: `${bestRegion.name} is cleaner and within SLA/jurisdiction`,
    recommendedRegion: bestRegion.name,
    tonnesCo2PerYear: round2(tonnesSaved),
    inrDeltaPerYear: round2(inrDelta),
    shiftHours: 0,
    details: {
      currentCi: round2(currentCi),
      bestCi: round2(bestCi),
      energyKwhPerYear,
      inrPerTonne: Number.isFinite(inrPerTonne) ? Math.round(inrPerTonne) : null,
      egressInrPerYear: round2(egressInr),
      ranked,
    },
    suggestion: `Move ${workload.name} to ${bestRegion.name}: the grid there is ${Math.round(currentCi - bestCi)} gCO\u2082/kWh cleaner right now. Plan the data migration and cut-over; re-run the audit afterwards to confirm.`,
  };
}

export function runAudit(workloads, opts = {}) {
  const decisions = workloads.map((w) => auditWorkload(w, opts));
  const summary = decisions.reduce(
    (acc, d) => {
      acc.tonnesCo2PerYear += d.tonnesCo2PerYear || 0;
      acc.inrDeltaPerYear += d.inrDeltaPerYear || 0;
      acc.counts[d.verdict] = (acc.counts[d.verdict] || 0) + 1;
      return acc;
    },
    { tonnesCo2PerYear: 0, inrDeltaPerYear: 0, counts: {} }
  );
  summary.tonnesCo2PerYear = round2(summary.tonnesCo2PerYear);
  summary.inrDeltaPerYear = round2(summary.inrDeltaPerYear);
  return { decisions, summary };
}

function round2(v) {
  return Math.round(v * 100) / 100;
}

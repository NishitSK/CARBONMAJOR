// Port of services/scheduler.py's filter_regions + calculate_scores +
// explain_decision, so simulated and live scoring produce the same shape
// (and, given the same regions/weights, the same ranking) — kept in sync
// with that file's DEFAULT_MAX_LATENCY-threshold latency norm and tie-break
// rules. Region: {name, carbon, latency, resources}.
const DEFAULT_MAX_LATENCY = 200;

function normalize(value, min, max) {
  if (max === min) return 0;
  return (value - min) / (max - min);
}

function thresholdNormalize(value, threshold, max) {
  if (value <= threshold) return 0;
  const denom = max - threshold;
  if (denom <= 0) return 0;
  return Math.min((value - threshold) / denom, 1);
}

export function filterRegions(regions, maxLatency) {
  return regions.filter((r) => r.latency <= maxLatency);
}

export function calculateScores(regions, weights) {
  if (!regions || regions.length === 0) return [];
  const carbons = regions.map((r) => r.carbon);
  const latencies = regions.map((r) => r.latency);
  const minC = Math.min(...carbons);
  const maxC = Math.max(...carbons);
  const maxL = Math.max(...latencies);

  const scored = regions.map((region) => {
    const cNorm = normalize(region.carbon, minC, maxC);
    const lNorm = thresholdNormalize(region.latency, DEFAULT_MAX_LATENCY, maxL);
    const rPenalty = 1 - region.resources / 100;
    const score =
      (weights.carbon ?? 0.4) * cNorm + (weights.latency ?? 0.3) * lNorm + (weights.resources ?? 0.3) * rPenalty;

    const strengths = [];
    if (cNorm < 0.3) strengths.push('Low Carbon');
    if (lNorm < 0.3) strengths.push('Low Latency');
    if (rPenalty < 0.3) strengths.push('High Resource Availability');

    return {
      region,
      score: Math.round(score * 10000) / 10000,
      metadata: { c_norm: round3(cNorm), l_norm: round3(lNorm), r_penalty: round3(rPenalty), strengths },
    };
  });

  scored.sort((a, b) => {
    if (a.score !== b.score) return a.score - b.score;
    if (a.region.carbon !== b.region.carbon) return a.region.carbon - b.region.carbon;
    if (a.region.latency !== b.region.latency) return a.region.latency - b.region.latency;
    return b.region.resources - a.region.resources;
  });

  return scored.map((s, i) => ({ ...s, rank: i + 1 }));
}

function round3(v) {
  return Math.round(v * 1000) / 1000;
}

export function explainDecision(best) {
  const { region, metadata } = best;
  const strengths = metadata.strengths;
  let summary = `Selected ${region.name} as the optimal placement.`;
  summary += strengths.length
    ? ` It excels in: ${strengths.join(', ')}.`
    : ' It offers the best balanced score across all metrics.';
  return {
    summary,
    details: {
      carbon_impact: metadata.c_norm < 0.2 ? 'Excellent' : 'Optimized',
      performance: metadata.l_norm < 0.2 ? 'High' : 'Stable',
      capacity: metadata.r_penalty < 0.2 ? 'Ample' : 'Sufficient',
    },
  };
}

// Full /score-equivalent: {success, eligible, rejected, explanation}
export function score(regions, weights, maxLatency) {
  const eligible = filterRegions(regions, maxLatency);
  const rejected = regions
    .filter((r) => r.latency > maxLatency)
    .map((r) => ({ name: r.name, reason: `Latency (${r.latency}ms) exceeds SLA ceiling (${maxLatency}ms)` }));

  if (eligible.length === 0) {
    return { success: false, eligible: [], rejected, explanation: null };
  }
  const scored = calculateScores(eligible, weights);
  return {
    success: true,
    eligible: scored,
    rejected,
    explanation: explainDecision(scored[0]),
  };
}

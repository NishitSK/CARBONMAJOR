// Jurisdiction / data-residency model, lifted from aws/pilot_runner_adaptive.py
// (APAC Sovereign / Americas Sovereign / Global Flexible) plus an explicit
// India-only rule for personal data under the DPDP Act — the audit's core
// compliance gate.
export const JURISDICTIONS = {
  india_dpdp: {
    label: 'India (DPDP personal data)',
    allowed: ['ap-south-1 (Mumbai)'],
  },
  eu_gdpr: {
    label: 'EU (GDPR personal data)',
    allowed: ['eu-west-1 (Ireland)', 'eu-central-1 (Frankfurt)', 'eu-north-1 (Sweden)'],
  },
  apac_sovereign: {
    label: 'APAC Sovereign',
    allowed: [
      'ap-south-1 (Mumbai)',
      'ap-southeast-1 (Singapore)',
      'ap-northeast-1 (Tokyo)',
      'ap-southeast-2 (Sydney)',
    ],
  },
  americas_sovereign: {
    label: 'Americas Sovereign',
    allowed: [
      'us-east-1 (N. Virginia)',
      'us-east-2 (Ohio)',
      'us-west-2 (Oregon)',
      'ca-central-1 (Canada)',
      'sa-east-1 (Sao Paulo)',
    ],
  },
  global_unconstrained: {
    label: 'Global Flexible',
    allowed: null, // any region
  },
};

// dataClass -> which jurisdiction gate applies. Personal data under a named
// residency law is pinned to that law's own region set regardless of the
// workload's jurisdiction field; everything else uses the jurisdiction field.
export function allowedRegionsFor(dataClass, jurisdictionKey, allRegionNames) {
  if (dataClass === 'personal_india') return JURISDICTIONS.india_dpdp.allowed;
  if (dataClass === 'personal_eu') return JURISDICTIONS.eu_gdpr.allowed;
  const j = JURISDICTIONS[jurisdictionKey] || JURISDICTIONS.global_unconstrained;
  return j.allowed || allRegionNames;
}

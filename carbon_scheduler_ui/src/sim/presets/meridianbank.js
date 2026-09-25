// Meridian Bank — fictional large enterprise (retail banking, India), many
// accounts and strict RBI-style data-localisation rules. Illustrates the
// enterprise story: almost everything stays put by policy, and what CADSS
// offers at this scale is a policy engine + API/CI integration, not a
// dashboard someone clicks through by hand.
export default {
  id: 'meridianbank',
  name: 'Meridian Bank',
  tagline: 'Retail banking, India — 40+ AWS accounts, RBI data-localisation policy',
  maxInrPerTonne: 10000,
  enterprise: true,
  policySnippet: `# meridian-carbon-policy.yaml
# Enforced centrally via CI + Terraform admission control, not per-engineer choice.
version: 1
residency:
  personal_india: [ap-south-1]      # RBI localisation — hard boundary
  personal_eu: [eu-west-1, eu-central-1, eu-north-1]
cost_ceiling_inr_per_tonne_co2: 10000
default_latency_sla_ms: 100
audit_schedule: quarterly
`,
  workloads: [
    {
      name: 'Core Banking Ledger',
      description: 'Account balances, transactions — RBI-localised',
      kind: 'customer-facing',
      dataClass: 'personal_india',
      latencySlaMs: 40,
      currentRegion: 'ap-south-1 (Mumbai)',
      vcpus: 96,
      hoursPerMonth: 730,
      dataOutGbPerMonth: 200,
    },
    {
      name: 'UPI / Payments Switch',
      description: 'Real-time payment authorisation',
      kind: 'customer-facing',
      dataClass: 'personal_india',
      latencySlaMs: 30,
      currentRegion: 'ap-south-1 (Mumbai)',
      vcpus: 64,
      hoursPerMonth: 730,
      dataOutGbPerMonth: 90,
    },
    {
      name: 'Mobile Banking API',
      description: 'Customer-facing app backend',
      kind: 'customer-facing',
      dataClass: 'personal_india',
      latencySlaMs: 100,
      currentRegion: 'ap-south-1 (Mumbai)',
      vcpus: 48,
      hoursPerMonth: 730,
      dataOutGbPerMonth: 150,
    },
    {
      name: 'Fraud Detection Scoring',
      description: 'Anonymised transaction-pattern scoring, needs India-region latency',
      kind: 'batch',
      dataClass: 'anonymised',
      jurisdiction: 'apac_sovereign',
      latencySlaMs: 150,
      currentRegion: 'ap-south-1 (Mumbai)',
      vcpus: 40,
      hoursPerMonth: 500,
      dataOutGbPerMonth: 60,
    },
    {
      name: 'Regulatory Reporting Batch',
      description: 'Anonymised aggregate reports for RBI/SEBI filings',
      kind: 'deferrable',
      dataClass: 'anonymised',
      jurisdiction: 'apac_sovereign',
      latencySlaMs: 5000,
      currentRegion: 'ap-south-1 (Mumbai)',
      vcpus: 20,
      hoursPerMonth: 100,
      dataOutGbPerMonth: 30,
      deadlineFlexHours: 12,
    },
    {
      name: 'Credit Risk Model Training',
      description: 'Anonymised, no residency constraint by policy exception',
      kind: 'deferrable',
      dataClass: 'anonymised',
      jurisdiction: 'global_unconstrained',
      latencySlaMs: 5000,
      currentRegion: 'ap-south-1 (Mumbai)',
      vcpus: 160,
      hoursPerMonth: 150,
      dataOutGbPerMonth: 25,
      deadlineFlexHours: 10,
    },
    {
      name: 'Internal Analytics Warehouse',
      description: 'Anonymised BI cubes, heavy data volume',
      kind: 'batch',
      dataClass: 'anonymised',
      jurisdiction: 'global_unconstrained',
      latencySlaMs: 5000,
      currentRegion: 'ap-south-1 (Mumbai)',
      vcpus: 32,
      hoursPerMonth: 720,
      dataOutGbPerMonth: 4000,
    },
  ],
};

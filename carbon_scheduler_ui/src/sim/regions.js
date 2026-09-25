// Region reference data for the in-browser simulation engine.
// Carbon/latency/resources are derived, illustrative constants (this
// project's own past measurements: data/regions.json, data/south_india_latency.json)
// — never the licensed Electricity Maps hourly series, which is never shipped
// to the browser.
//
// price/egress are illustrative INR figures for the Placement Audit's cost
// model (roughly AWS on-demand-equivalent order of magnitude), explicitly
// labelled as estimates everywhere they're shown.

// computeInrPerVcpuHr deliberately does NOT track cleanliness (as in real
// public-cloud price lists — Oregon/Virginia are cheap AND relatively clean;
// Mumbai is cheap and dirty; Stockholm is mid-priced and very clean) so the
// audit's cost signal comes from genuine price+egress economics, not a
// built-in "clean = expensive" thumb on the scale.
export const REGIONS = [
  { name: 'us-east-1 (N. Virginia)', zone: 'US-MIDA-PJM', lat: 38.13, lng: -78.45, baseCarbon: 380, latencyFromIndia: 230, computeInrPerVcpuHr: 3.75, egressInrPerGb: 6.5, continent: 'Americas' },
  { name: 'us-east-2 (Ohio)', zone: 'US-MIDW-MISO', lat: 40.0, lng: -82.5, baseCarbon: 420, latencyFromIndia: 233, computeInrPerVcpuHr: 3.7, egressInrPerGb: 6.5, continent: 'Americas' },
  { name: 'us-west-2 (Oregon)', zone: 'US-NW-PACW', lat: 45.82, lng: -119.7, baseCarbon: 160, latencyFromIndia: 314, computeInrPerVcpuHr: 3.8, egressInrPerGb: 6.5, continent: 'Americas' },
  { name: 'ca-central-1 (Canada)', zone: 'CA-QC', lat: 45.5, lng: -73.56, baseCarbon: 30, latencyFromIndia: 235, computeInrPerVcpuHr: 3.8, egressInrPerGb: 6.8, continent: 'Americas' },
  { name: 'sa-east-1 (Sao Paulo)', zone: 'BR', lat: -23.55, lng: -46.63, baseCarbon: 140, latencyFromIndia: 345, computeInrPerVcpuHr: 4.6, egressInrPerGb: 8.0, continent: 'Americas' },
  { name: 'eu-west-1 (Ireland)', zone: 'IE', lat: 53.0, lng: -8.0, baseCarbon: 230, latencyFromIndia: 151, computeInrPerVcpuHr: 3.85, egressInrPerGb: 6.9, continent: 'Europe' },
  { name: 'eu-central-1 (Frankfurt)', zone: 'DE', lat: 50.11, lng: 8.68, baseCarbon: 350, latencyFromIndia: 150, computeInrPerVcpuHr: 3.9, egressInrPerGb: 6.9, continent: 'Europe' },
  { name: 'eu-north-1 (Sweden)', zone: 'SE', lat: 60.13, lng: 18.64, baseCarbon: 20, latencyFromIndia: 179, computeInrPerVcpuHr: 3.8, egressInrPerGb: 6.7, continent: 'Europe' },
  { name: 'ap-south-1 (Mumbai)', zone: 'IN-WE', lat: 19.07, lng: 72.87, baseCarbon: 700, latencyFromIndia: 12, computeInrPerVcpuHr: 3.7, egressInrPerGb: 5.5, continent: 'APAC' },
  { name: 'ap-southeast-1 (Singapore)', zone: 'SG', lat: 1.35, lng: 103.82, baseCarbon: 450, latencyFromIndia: 83, computeInrPerVcpuHr: 3.85, egressInrPerGb: 6.2, continent: 'APAC' },
  { name: 'ap-northeast-1 (Tokyo)', zone: 'JP', lat: 35.68, lng: 139.69, baseCarbon: 480, latencyFromIndia: 130, computeInrPerVcpuHr: 4.3, egressInrPerGb: 7.2, continent: 'APAC' },
  { name: 'ap-southeast-2 (Sydney)', zone: 'AU-NSW', lat: -33.86, lng: 151.2, baseCarbon: 580, latencyFromIndia: 250, computeInrPerVcpuHr: 4.4, egressInrPerGb: 7.4, continent: 'APAC' },
  { name: 'af-south-1 (Cape Town)', zone: 'ZA', lat: -33.92, lng: 18.42, baseCarbon: 850, latencyFromIndia: 300, computeInrPerVcpuHr: 4.2, egressInrPerGb: 7.0, continent: 'APAC' },
];

export function findRegion(name) {
  return REGIONS.find((r) => r.name === name) || null;
}

export const REGION_NAMES = REGIONS.map((r) => r.name);

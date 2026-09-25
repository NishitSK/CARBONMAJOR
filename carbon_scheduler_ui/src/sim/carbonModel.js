// Synthetic diurnal + day-to-day carbon-intensity curve. Generalizes the
// formula already used in components/demo/TimelineMigrationPath.jsx and the
// backend's generate_synthetic_history (services/forecaster.py) — a clean
// midday dip, deeper for solar-heavy grids, plus small seeded noise. No
// licensed data is used or needed.
import { mulberry32, hashSeed } from './rng';

// Cleaner grids (hydro/nuclear-heavy, e.g. Sweden/Canada) swing less with
// the sun; solar/gas-heavy grids swing more.
function amplitudeFor(region) {
  if (region.baseCarbon < 60) return 0.12; // hydro/nuclear: nearly flat
  if (region.baseCarbon < 250) return 0.22;
  return 0.3; // fossil-heavy grids: bigger solar-driven daytime dip
}

export function carbonAtHour(region, hourOfDay, dayIndex = 0) {
  const rng = mulberry32(hashSeed(region.name) + dayIndex * 977);
  const amp = amplitudeFor(region);
  // Cleanest around 13:00 local-ish (solar peak), dirtiest at night.
  const diurnal = 1 - amp * Math.sin(((hourOfDay - 7) / 24) * 2 * Math.PI);
  const noise = 1 + (rng() - 0.5) * 0.06;
  return Math.max(5, region.baseCarbon * diurnal * noise);
}

export function daySeries(region, dayIndex = 0) {
  return Array.from({ length: 24 }, (_, h) => Math.round(carbonAtHour(region, h, dayIndex) * 10) / 10);
}

export function currentHour() {
  return new Date().getUTCHours();
}

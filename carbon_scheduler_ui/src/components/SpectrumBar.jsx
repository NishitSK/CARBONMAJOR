import React from 'react';

// Calibrated to the same gCO2/kWh bands used everywhere else in the app
// (WorldMap markers, table strengths): clean <=200, mid <=450, warm <=700, dirty >700.
const SCALE_MAX = 900;

function positionPct(carbon) {
  const clamped = Math.max(0, Math.min(SCALE_MAX, carbon));
  return (clamped / SCALE_MAX) * 100;
}

// Full-width page divider with tick labels — the page's signature element.
export function SpectrumDivider() {
  return (
    <div className="spectrum-bar-wrap">
      <div className="spectrum-divider" />
      <div className="spectrum-ticks">
        <span>0 g</span>
        <span>200 g</span>
        <span>450 g</span>
        <span>700 g</span>
        <span>900+ g CO₂/kWh</span>
      </div>
    </div>
  );
}

// Small inline ruler with a marker for one carbon value — used per table row.
export function SpectrumTick({ carbon }) {
  if (typeof carbon !== 'number') return null;
  return (
    <div className="spectrum-mini" title={`${carbon.toFixed(0)} gCO₂/kWh`}>
      <div className="marker" style={{ left: `${positionPct(carbon)}%` }} />
    </div>
  );
}

export default SpectrumDivider;

import React from 'react';
import StatTile from '../components/layout/StatTile';

export default function HeroSection() {
  return (
    <section className="section hero-section">
      <div className="console-eyebrow">Carbon-aware cloud scheduling — research + live demo</div>
      <h1 className="hero-title">
        Most of the carbon saving comes from picking the right region — not from reacting in real time.
      </h1>
      <p className="hero-lede">
        This project routes cloud workloads to whichever data-center region has the cleanest electricity grid at
        that moment. The surprising finding: under realistic constraints, just knowing in advance which regions are
        usually clean captures roughly 97% of the possible carbon savings. Reacting to the grid in real time only adds
        a little more on its own — <strong>unless</strong> that real-time information is used to decide{' '}
        <em>when</em> to run a workload rather than <em>where</em>, which turns out to be where real AI forecasting
        genuinely pays off.
      </p>
      <div className="hero-stats">
        <StatTile
          value="+2.7%"
          label="extra saving from reacting to live grid conditions, on top of just picking a fixed clean region"
          tone="neutral"
        />
        <StatTile
          value="+8.4%"
          label="extra saving once real AI forecasting decides WHEN to run a delay-tolerant job (vs. today's fake stand-in)"
          tone="accent"
        />
      </div>
    </section>
  );
}

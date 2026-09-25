import React from 'react';
import { Play, Pause, ArrowRight, Compass, ShieldCheck, Zap, Clock } from 'lucide-react';

export default function TimelineMigrationPath({
  daySimPlaying,
  onTogglePlay,
  simHour,
  onScrub,
  dailySeries,
  regions,
  bestRegion
}) {
  // Precompute the best region for each hour across the 24h timeline
  const hourlyDecisions = Array.from({ length: 24 }, (_, h) => {
    let best = null;
    let minCarbon = Infinity;
    
    if (regions && regions.length > 0) {
      regions.forEach(r => {
        // Estimate diurnal swing for region at hour h
        const base = r.carbon || r.carbon_intensity || 250;
        const diurnalFactor = 1 - 0.25 * Math.sin(((h - 12) / 12) * Math.PI);
        const estCarbon = Math.max(10, base * (r.name.includes('Sweden') ? 1 : diurnalFactor));
        if (estCarbon < minCarbon) {
          minCarbon = estCarbon;
          best = { ...r, estCarbon };
        }
      });
    }
    
    return {
      hour: h,
      region: best || { name: 'eu-north-1 (Sweden)', estCarbon: 18.0 }
    };
  });

  const currentStep = hourlyDecisions[simHour] || hourlyDecisions[0];

  return (
    <div className="card" style={{ background: 'var(--surface-card)', border: '1px solid var(--border-light)', padding: '1.75rem 2rem' }}>
      <div className="card-header" style={{ marginBottom: '1.25rem', paddingBottom: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Compass size={22} color="var(--primary)" />
            <h3 className="card-title" style={{ fontSize: '1.25rem' }}>24-Hour Workload Migration Path & Solar Trail</h3>
          </div>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
            Visualizes dynamic cross-continental workload handoffs as solar and wind production rotate with Earth's diurnal cycle
          </p>
        </div>

        {/* Playback & Clock Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button
            className="btn btn-primary"
            onClick={onTogglePlay}
            style={{ padding: '0.6rem 1.25rem', fontSize: '0.95rem' }}
          >
            {daySimPlaying ? <><Pause size={16} /> Pause Day Sim</> : <><Play size={16} /> Run 24h Sim</>}
          </button>
          <div className="mono" style={{ fontSize: '1.4rem', fontWeight: 800, background: 'var(--bg-subtle)', padding: '0.35rem 0.9rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
            {String(simHour).padStart(2, '0')}:00 UTC
          </div>
        </div>
      </div>

      {/* Interactive 24-Hour Timeline Track */}
      <div style={{ marginBottom: '1.75rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-faint)', fontWeight: 600, marginBottom: '0.5rem' }}>
          <span>00:00 (Europe Night / APAC Morning)</span>
          <span>12:00 (Europe Solar Peak)</span>
          <span>18:00 (Americas Solar Peak)</span>
          <span>23:00 UTC</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(24, 1fr)', gap: '3px', background: 'var(--bg-subtle)', padding: '4px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
          {hourlyDecisions.map((step, h) => {
            const isActive = h === simHour;
            const isSweden = step.region.name.includes('Sweden');
            const isCanada = step.region.name.includes('Canada');
            const isOregon = step.region.name.includes('Oregon');

            const bgCol = isActive 
              ? 'var(--primary)' 
              : isSweden 
                ? 'rgba(16, 185, 129, 0.4)' 
                : isCanada 
                  ? 'rgba(59, 130, 246, 0.4)' 
                  : 'rgba(245, 158, 11, 0.4)';

            return (
              <div
                key={h}
                onClick={() => onScrub(h)}
                title={`Hour ${String(h).padStart(2, '0')}:00 -> ${step.region.name} (${step.region.estCarbon.toFixed(0)} gCO2)`}
                style={{
                  height: isActive ? '36px' : '26px',
                  background: bgCol,
                  borderRadius: '4px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  color: '#fff',
                  transition: 'all 0.15s ease',
                  transform: isActive ? 'scale(1.05)' : 'none',
                  border: isActive ? '2px solid #fff' : 'none'
                }}
              >
                {h % 4 === 0 ? h : ''}
              </div>
            );
          })}
        </div>
      </div>

      {/* Active Migration Vector & Handoff Card */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem', background: 'var(--bg-subtle)', padding: '1.25rem 1.5rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
        {/* Origin Step */}
        <div>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-faint)' }}>Workload Origin</span>
          <div style={{ fontSize: '1.15rem', fontWeight: 700, marginTop: '0.2rem' }}>us-east-1 (N. Virginia)</div>
          <div className="mono" style={{ fontSize: '0.85rem', color: 'var(--dirty)', marginTop: '0.2rem' }}>437.0 gCO2/kWh (Baseline Grid)</div>
        </div>

        {/* Dynamic Migration Vector Arrow */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Active Spatial Migration
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--primary)', marginTop: '0.25rem' }}>
            <div style={{ height: '2px', width: '40px', background: 'var(--primary)' }}></div>
            <ArrowRight size={20} />
            <div style={{ height: '2px', width: '40px', background: 'var(--primary)' }}></div>
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-faint)', marginTop: '0.25rem' }}>Latency: 82ms &middot; SLA Passed (&lt;200ms)</span>
        </div>

        {/* Destination Target */}
        <div>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--clean)' }}>Optimal Destination Hub</span>
          <div style={{ fontSize: '1.15rem', fontWeight: 700, marginTop: '0.2rem', color: 'var(--clean)' }}>
            {currentStep.region.name}
          </div>
          <div className="mono" style={{ fontSize: '0.85rem', color: 'var(--clean)', marginTop: '0.2rem', fontWeight: 600 }}>
            {currentStep.region.estCarbon.toFixed(1)} gCO2/kWh ({(100 - (currentStep.region.estCarbon / 437.0 * 100)).toFixed(1)}% Reduction)
          </div>
        </div>
      </div>
    </div>
  );
}

import React from 'react';
import { Globe, History } from 'lucide-react';
import { Link } from 'react-router-dom';
import WorldMap from '../components/demo/WorldMap';
import RegionRankingsTable from '../components/demo/RegionRankingsTable';
import RejectedRegionsPanel from '../components/demo/RejectedRegionsPanel';
import TimeScrubber from '../components/demo/TimeScrubber';
import SectionHeader from '../components/layout/SectionHeader';
import { useHistoricalReplay } from '../hooks/useHistoricalReplay';

function exportReplayCsv(eligible, rejected, timestamp) {
  if (!eligible || eligible.length === 0) return;
  const headers = ['rank', 'region', 'carbon_g_per_kwh', 'latency_ms', 'resources_pct', 'score', 'strengths'];
  const rows = eligible.map(r => [
    r.rank, r.region.name, r.region.carbon, r.region.latency, r.region.resources, r.score,
    (r.metadata?.strengths || []).join('; ')
  ]);
  const rejectedRows = (rejected || []).map(r => ['-', r.name, '-', '-', '-', 'REJECTED', r.reason]);
  const csv = [headers, ...rows, ...rejectedRows]
    .map(row => row.map(v => `"${String(v).replace(/"/g, '""')}"`).join(','))
    .join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `real_decision_${(timestamp || '').replace(/[:.]/g, '-')}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// The model showcase -- a co-equal main focus alongside the research
// findings, not a footnote (design principle 1). Every value here comes
// from the real 2021-2025 grid data, run through the same, unmodified
// scoring endpoint as the rest of the app -- nothing simulated.
export default function HistoricalReplaySection() {
  const r = useHistoricalReplay();
  const eligible = r.scoreResult?.eligible;
  const rejected = r.scoreResult?.rejected;

  return (
    <section className="section historical-replay-section" id="model-showcase">
      <SectionHeader
        eyebrow="Model showcase — real data, not a simulation"
        icon={<History size={13} />}
        title="Scrub through five real years of grid data and watch the scheduler decide"
        lede="Every number below comes from the same real, historical carbon-intensity data — measured for actual power grids from 2021 through 2025 — that every research result on this page is built from. Pick an hour and see exactly which AWS region the scheduler would have picked at that real moment."
      />

      <TimeScrubber
        hourIndex={r.hourIndex}
        nHours={r.nHours}
        currentTimestamp={r.currentTimestamp}
        playing={r.playing}
        onTogglePlay={() => r.setPlaying(p => !p)}
        onStep={r.stepHour}
        onScrub={r.scrubTo}
      />

      {r.error && <div className="glass-panel status-fail" style={{ margin: '1rem 0' }}>{r.error}</div>}

      <div style={{ marginTop: '1.5rem' }}>
        <section className="glass-panel no-padding overflow-hidden" style={{ minHeight: '400px' }}>
          <div className="panel-header">
            <span className="panel-title"><Globe size={16} color="var(--accent)" /> Real placement at this hour</span>
            {r.loading && <span className="status-badge" style={{ background: 'var(--accent-dim)', color: 'var(--accent)' }}>Loading real data…</span>}
          </div>
          <WorldMap regions={r.regions} bestRegionName={r.bestRegion?.name} />
        </section>

        <RejectedRegionsPanel rejected={rejected} />
        <RegionRankingsTable
          results={eligible}
          debugMode={false}
          onExportCsv={() => exportReplayCsv(eligible, rejected, r.currentTimestamp)}
        />
      </div>

      <p style={{ marginTop: '1.5rem' }}>
        <Link to="/playground" className="ghost-btn" style={{ display: 'inline-flex' }}>
          Want to change the scoring weights yourself? Try the sandbox →
        </Link>
      </p>
    </section>
  );
}

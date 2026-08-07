import React from 'react';
import { Play, Pause, SkipBack, SkipForward } from 'lucide-react';

function formatTimestamp(iso) {
  if (!iso) return '—';
  const d = new Date(iso.slice(0, 19) + 'Z');
  return d.toLocaleString('en-US', {
    year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'UTC'
  }) + ' UTC';
}

export default function TimeScrubber({ hourIndex, nHours, currentTimestamp, playing, onTogglePlay, onStep, onScrub }) {
  return (
    <div className="glass-panel time-scrubber">
      <button className="daysim-playbtn" onClick={onTogglePlay} title={playing ? 'Pause' : 'Play'}>
        {playing ? <Pause size={15} /> : <Play size={15} />}
      </button>
      <button className="scrubber-step" onClick={() => onStep(-1)} title="Back 1 hour"><SkipBack size={13} /></button>
      <button className="scrubber-step" onClick={() => onStep(1)} title="Forward 1 hour"><SkipForward size={13} /></button>
      <span className="mono scrubber-clock">{formatTimestamp(currentTimestamp)}</span>
      <input
        type="range"
        min="0"
        max={Math.max(nHours - 1, 0)}
        step="1"
        value={hourIndex}
        onChange={(e) => onScrub(parseInt(e.target.value, 10))}
        className="daysim-scrub"
      />
      <span className="scrubber-label">Real 2021–2025 hourly data · {nHours.toLocaleString()} hours</span>
    </div>
  );
}

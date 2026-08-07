import React from 'react';
import { Play, Pause } from 'lucide-react';

export default function DaySimControls({ daySimPlaying, onTogglePlay, simHour, onScrub, dailySeries }) {
  return (
    <div className="glass-panel daysim-console">
      <button
        className="daysim-playbtn"
        onClick={onTogglePlay}
        disabled={!dailySeries}
        title={daySimPlaying ? 'Pause' : 'Play'}
      >
        {daySimPlaying ? <Pause size={15} /> : <Play size={15} />}
      </button>
      <span className="daysim-clock mono">{String(simHour).padStart(2, '0')}:00</span>
      <input
        type="range"
        min="0"
        max="23"
        step="1"
        value={simHour}
        disabled={!dailySeries}
        onChange={(e) => onScrub(parseInt(e.target.value))}
        className="daysim-scrub"
      />
      <span className="daysim-label">
        {dailySeries ? 'Simulated 24h diurnal carbon curve — scrub or press play' : 'Loading day curve…'}
      </span>
    </div>
  );
}

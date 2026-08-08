import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Shield, AlertTriangle } from 'lucide-react';
import { useClientFleet } from '../hooks/useClientFleet';
import { useZones } from '../hooks/useZones';
import { useConsoleClock } from '../hooks/useConsoleClock';
import ServerFleetManager from '../sections/console/ServerFleetManager';
import SwitchingModeToggle from '../sections/console/SwitchingModeToggle';
import ActiveServerPanel from '../sections/console/ActiveServerPanel';
import ScoringControls from '../components/demo/ScoringControls';
import TimeScrubber from '../components/demo/TimeScrubber';
import RegionRankingsTable from '../components/demo/RegionRankingsTable';
import RejectedRegionsPanel from '../components/demo/RejectedRegionsPanel';
import '../styles/demo.css';
import '../styles/console.css';

// The commercial-pitch demo: a client brings their OWN fleet (each server
// mapped to a real electricity zone) instead of the project's fixed pool,
// and controls whether carbon-aware failover applies itself or waits for
// their approval. Fleet + settings persist to localStorage only -- no
// login/backend account system, this is a demo.
import ProgramBoxesSection from '../sections/console/ProgramBoxesSection';

export default function ConsolePage() {
  const fleet = useClientFleet();
  const { zones, loading: zonesLoading } = useZones();
  const clock = useConsoleClock(
    fleet.servers, fleet.weights, fleet.maxLatency,
    fleet.switchingMode, fleet.activeServerId, fleet.setActiveServerId,
    fleet.workloads, fleet.setWorkloadActiveServer, fleet.programs
  );

  const handleWeightChange = (key, value) => {
    fleet.setWeights({ ...fleet.weights, [key]: parseFloat(value) });
  };

  const serverById = Object.fromEntries(fleet.servers.map(sv => [sv.id, sv]));
  const activeServer = serverById[fleet.activeServerId] || null;

  const labelOf = (id) => serverById[id]?.label || id;
  const displayResults = (clock.scoreResult?.eligible || []).map(res => ({
    ...res,
    region: { ...res.region, name: labelOf(res.region.name) },
  }));
  const displayRejected = (clock.scoreResult?.rejected || []).map(r => ({
    ...r,
    name: labelOf(r.name),
  }));

  return (
    <div className="dashboard-container">
      <header>
        <div className="console-header">
          <div>
            <Link to="/" className="ghost-btn" style={{ marginBottom: '0.9rem', display: 'inline-flex' }}>
              <ArrowLeft size={13} /> Back to research site
            </Link>
            <div className="console-eyebrow">Carbon-aware placement engine · client console</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Shield size={22} color="var(--accent)" />
              <h1>Your Console</h1>
            </div>
            <p className="console-sub">
              Create Project Boxes bound to specific Geographic Region Scopes (Europe, South Asia, South East Asia, East Asia, World, etc.) and manage carbon-aware failover for workloads within those regions.
            </p>
          </div>
        </div>

        {fleet.servers.length > 0 && (
          <TimeScrubber
            hourIndex={clock.hourIndex}
            nHours={clock.nHours}
            currentTimestamp={clock.currentTimestamp}
            playing={clock.playing}
            onTogglePlay={() => clock.setPlaying(p => !p)}
            onStep={clock.stepHour}
            onScrub={clock.scrubTo}
          />
        )}
      </header>

      {clock.error && (
        <div className="glass-panel status-fail" style={{ textAlign: 'center', margin: '0 0 1.25rem' }}>
          <AlertTriangle style={{ verticalAlign: 'middle', marginRight: '8px' }} />
          {clock.error} (Check port 8001)
        </div>
      )}

      <div className="grid-layout">
        <div className="left-panel">
          <ServerFleetManager
            servers={fleet.servers}
            zones={zones}
            zonesLoading={zonesLoading}
            activeServerId={fleet.activeServerId}
            onSelectActive={fleet.setActiveServerId}
            onAdd={fleet.addServer}
            onRemove={fleet.removeServer}
            onRename={fleet.renameServer}
          />

          {fleet.servers.length > 0 && (
            <>
              <ProgramBoxesSection
                programs={fleet.programs || []}
                workloads={fleet.workloads || []}
                servers={fleet.servers}
                zones={zones}
                workloadResults={clock.workloadResults}
                zoneCarbon={clock.zoneCarbon}
                onAddProgram={fleet.addProgram}
                onRemoveProgram={fleet.removeProgram}
                onUpdateProgram={fleet.updateProgram}
                onAddWorkloadToProgram={fleet.addWorkloadToProgram}
                onRemoveWorkload={fleet.removeWorkload}
                onUpdateWorkload={fleet.updateWorkload}
                onSelectActiveServer={fleet.setWorkloadActiveServer}
                onSwitchRegion={fleet.switchWorkloadRegion}
                onSetSwitchingMode={fleet.setWorkloadSwitchingMode}
              />
              <RejectedRegionsPanel rejected={displayRejected} />
              <RegionRankingsTable
                results={displayResults}
                debugMode={false}
                onExportCsv={() => {}}
                onSelectRegion={(serverLabelOrId) => {
                  const sv = fleet.servers.find(s => s.label === serverLabelOrId || s.id === serverLabelOrId);
                  if (sv) fleet.setActiveServerId(sv.id);
                }}
              />
            </>
          )}
        </div>

        <aside style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <SwitchingModeToggle mode={fleet.switchingMode} onChange={fleet.setSwitchingMode} />
          <ScoringControls
            weights={fleet.weights}
            onWeightChange={handleWeightChange}
            maxLatency={fleet.maxLatency}
            onMaxLatencyChange={fleet.setMaxLatency}
            bestRegion={activeServer ? { name: activeServer.label } : null}
          />
        </aside>
      </div>
    </div>
  );
}

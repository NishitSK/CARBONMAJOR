import React from "react";
import {
  ComposableMap,
  Geographies,
  Geography,
  Marker,
  Sphere,
  Graticule,
  Line
} from "react-simple-maps";
import { SpectrumDivider } from "./SpectrumBar";

const geoUrl = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

const SPECTRUM_CLEAN = "#10b981";
const SPECTRUM_MID = "#f59e0b";
const SPECTRUM_WARM = "#f97316";
const SPECTRUM_DIRTY = "#f43f5e";

// Reference Origin Hub (N. Virginia: -77.4875, 39.0438)
const ORIGIN_COORDS = [-77.4875, 39.0438];

// activeRegionName (optional): a manually chosen placement. The arc follows
// it; the optimal region keeps its green ring so the trade-off stays visible.
const WorldMap = ({ regions, bestRegionName, activeRegionName, onRegionClick }) => {
  if (!Array.isArray(regions)) {
    return (
      <div className="card" style={{ height: '420px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
        Loading global map topology…
      </div>
    );
  }

  const getMarkerColor = (carbon) => {
    if (carbon <= 100) return SPECTRUM_CLEAN;
    if (carbon <= 350) return SPECTRUM_MID;
    if (carbon <= 600) return SPECTRUM_WARM;
    return SPECTRUM_DIRTY;
  };

  const targetName = activeRegionName || bestRegionName;
  const isOverride = !!(activeRegionName && bestRegionName && activeRegionName !== bestRegionName);
  const arcTarget = regions.find(r => r && r.name === targetName) || regions.find(r => r && r.name && r.name.includes('Sweden'));

  return (
    <div className="card" style={{ padding: "1.5rem", minHeight: "480px", overflow: "hidden" }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h3 className="card-title" style={{ fontSize: '1.15rem' }}>Global Carbon Grid & Active Migration Arc</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            The arc runs from the origin to the active placement. Click an eligible region to switch to it.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '1rem', fontSize: '0.8rem', flexWrap: 'wrap' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--primary)' }}></span> Migration path
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', border: '2px solid var(--clean)' }}></span> Optimal
          </span>
          {isOverride && (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
              <span style={{ width: '10px', height: '10px', borderRadius: '50%', border: '2px dashed var(--primary)' }}></span> Your override
            </span>
          )}
        </div>
      </div>

      <ComposableMap
        projectionConfig={{
          rotate: [-10, 0, 0],
          scale: 155
        }}
        width={800}
        height={380}
        style={{ width: "100%", height: "auto" }}
      >
        <Sphere stroke="var(--map-line)" strokeWidth={0.5} />
        <Graticule stroke="var(--map-line)" strokeWidth={0.5} />
        <Geographies geography={geoUrl}>
          {({ geographies }) =>
            geographies.map((geo) => (
              <Geography
                key={geo.rsmKey}
                geography={geo}
                fill="var(--map-land)"
                stroke="var(--map-line)"
                strokeWidth={0.5}
                style={{
                  default: { outline: "none" },
                  hover: { fill: "var(--primary-subtle)", outline: "none" },
                  pressed: { outline: "none" }
                }}
              />
            ))
          }
        </Geographies>

        {/* Migration arc from Virginia to the active placement */}
        {arcTarget && arcTarget.lng && arcTarget.lat && (
          <Line
            from={ORIGIN_COORDS}
            to={[arcTarget.lng, arcTarget.lat]}
            stroke="var(--primary)"
            strokeWidth={2.5}
            strokeDasharray="5 4"
            strokeLinecap="round"
          />
        )}

        {/* Region Markers */}
        {regions && regions.map((region) => {
          if (!region || typeof region.lng === 'undefined' || typeof region.lat === 'undefined') return null;
          const isBest = bestRegionName === region.name;
          const isActiveOverride = isOverride && activeRegionName === region.name;
          const isOrigin = region.name && region.name.includes('Virginia');
          const color = getMarkerColor(region.carbon || region.carbon_intensity || 250);
          const emphasised = isBest || isActiveOverride;

          return (
            <Marker
              key={region.name}
              coordinates={[region.lng, region.lat]}
              onClick={() => onRegionClick && onRegionClick(region)}
            >
              <title>{`${region.name} · ${Math.round(region.carbon ?? 0)} gCO₂/kWh`}</title>
              <circle
                r={emphasised ? 8 : isOrigin ? 6 : 5}
                fill={isOrigin ? '#f43f5e' : color}
                stroke={emphasised ? '#fff' : "rgba(255,255,255,0.6)"}
                strokeWidth={emphasised ? 2.5 : 1}
                style={{ cursor: "pointer", transition: "all 0.3s ease" }}
              />
              {isBest && (
                <circle r={16} fill="none" stroke="var(--clean)" strokeWidth={1.5} style={{ opacity: 0.6 }} />
              )}
              {isActiveOverride && (
                <circle r={16} fill="none" stroke="var(--primary)" strokeWidth={2} strokeDasharray="4 3" />
              )}
            </Marker>
          );
        })}
      </ComposableMap>

      <div style={{ marginTop: '1rem' }}>
        <SpectrumDivider />
      </div>
    </div>
  );
};

export default WorldMap;

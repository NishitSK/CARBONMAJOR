import React from "react";
import {
  ComposableMap,
  Geographies,
  Geography,
  Marker,
  Sphere,
  Graticule
} from "react-simple-maps";
import { SpectrumDivider } from "./SpectrumBar";

const geoUrl = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

// Same bands as the page-wide spectrum ruler — markers are just that ruler
// projected onto the globe.
const SPECTRUM_CLEAN = "#3DDC84";
const SPECTRUM_MID = "#E8C547";
const SPECTRUM_WARM = "#E8853D";
const SPECTRUM_DIRTY = "#E85D4A";
const ACCENT = "#5EE6C8";

const WorldMap = ({ regions, bestRegionName, onRegionClick }) => {
  if (!Array.isArray(regions)) return <div className="glass-panel" style={{ height: '400px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-dim)' }}>Loading map data…</div>;

  const getMarkerColor = (carbon) => {
    if (carbon <= 200) return SPECTRUM_CLEAN;
    if (carbon <= 450) return SPECTRUM_MID;
    if (carbon <= 700) return SPECTRUM_WARM;
    return SPECTRUM_DIRTY;
  };

  return (
    <div className="glass-panel" style={{ padding: "10px", minHeight: "450px", overflow: "hidden" }}>
      <ComposableMap
        projectionConfig={{
          rotate: [-10, 0, 0],
          scale: 147
        }}
        width={800}
        height={400}
        style={{ width: "100%", height: "auto" }}
      >
        <Sphere stroke="rgba(255,255,255,0.08)" strokeWidth={0.5} />
        <Graticule stroke="rgba(255,255,255,0.04)" strokeWidth={0.5} />
        <Geographies geography={geoUrl}>
          {({ geographies }) =>
            geographies.map((geo) => (
              <Geography
                key={geo.rsmKey}
                geography={geo}
                fill="rgba(255, 255, 255, 0.04)"
                stroke="rgba(255, 255, 255, 0.08)"
                strokeWidth={0.5}
                style={{
                  default: { outline: "none" },
                  hover: { fill: "rgba(94, 230, 200, 0.08)", outline: "none" },
                  pressed: { outline: "none" }
                }}
              />
            ))
          }
        </Geographies>

        {regions && regions.map((region) => {
          if (!region || typeof region.lng === 'undefined' || typeof region.lat === 'undefined') return null;
          const isBest = bestRegionName === region.name;
          const color = getMarkerColor(region.carbon);

          return (
            <Marker
              key={region.name}
              coordinates={[region.lng, region.lat]}
              onClick={() => onRegionClick && onRegionClick(region)}
            >
              <circle
                r={isBest ? 8 : 5}
                fill={color}
                stroke={isBest ? ACCENT : "rgba(255,255,255,0.4)"}
                strokeWidth={isBest ? 2.5 : 1}
                style={{ cursor: "pointer", transition: "all 0.3s ease" }}
              />
              {isBest && (
                <circle
                  r={15}
                  fill="none"
                  stroke={ACCENT}
                  strokeWidth={1}
                  className="pulse-animation"
                  style={{ opacity: 0.5 }}
                />
              )}
            </Marker>
          );
        })}
      </ComposableMap>

      <div style={{ padding: '0 1.1rem 1rem' }}>
        <SpectrumDivider />
      </div>
    </div>
  );
};

export default WorldMap;

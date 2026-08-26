import maplibregl, { type Map as MLMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { Feature, MultiPolygon, Polygon } from "geojson";
import type { LayerDescriptor } from "../types";

interface Props {
  layers: LayerDescriptor[];
  visible: Record<string, boolean>;
  boundary: Polygon | MultiPolygon | null;
  bounds: [number, number, number, number] | null;
}

const ESRI =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";

/** The map workspace. Raster layers come straight from the API's layer list. */
export function MapView({ layers, visible, boundary, bounds }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);

  useEffect(() => {
    if (!container.current || map.current) return;
    map.current = new maplibregl.Map({
      container: container.current,
      style: {
        version: 8,
        sources: { satellite: { type: "raster", tiles: [ESRI], tileSize: 256, maxzoom: 19 } },
        layers: [{ id: "satellite", type: "raster", source: "satellite" }],
      },
      center: [78.9, 21.5],
      zoom: 4.5,
      attributionControl: { compact: true },
    });
    map.current.addControl(new maplibregl.NavigationControl(), "top-right");
    map.current.addControl(new maplibregl.ScaleControl({ unit: "metric" }));
    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, []);

  // Sync API-described raster layers onto the map.
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const apply = () => {
      for (const layer of layers) {
        if (layer.layer_id === "satellite" || layer.kind !== "raster") continue;
        const id = `api-${layer.layer_id}`;
        if (!m.getSource(id)) {
          m.addSource(id, { type: "raster", tiles: [layer.tile_url_template], tileSize: 256, maxzoom: 18 });
          m.addLayer({
            id,
            type: "raster",
            source: id,
            paint: { "raster-opacity": layer.layer_id === "hillshade" ? 0.55 : 0.7 },
          });
        }
        m.setLayoutProperty(id, "visibility", visible[layer.layer_id] ? "visible" : "none");
      }
      if (boundary) {
        const data: Feature = { type: "Feature", geometry: boundary, properties: {} };
        const source = m.getSource("boundary") as maplibregl.GeoJSONSource | undefined;
        if (source) source.setData(data);
        else {
          m.addSource("boundary", { type: "geojson", data });
          m.addLayer({
            id: "boundary-line",
            type: "line",
            source: "boundary",
            paint: { "line-color": "#ffd166", "line-width": 2.5 },
          });
        }
        m.setLayoutProperty("boundary-line", "visibility", visible.boundary === false ? "none" : "visible");
      }
    };
    if (m.isStyleLoaded()) apply();
    else m.once("load", apply);
  }, [layers, visible, boundary]);

  useEffect(() => {
    if (map.current && bounds) {
      map.current.fitBounds([bounds[0], bounds[1], bounds[2], bounds[3]], { padding: 40, duration: 800 });
    }
  }, [bounds]);

  return <div ref={container} className="map" role="region" aria-label="Map" />;
}

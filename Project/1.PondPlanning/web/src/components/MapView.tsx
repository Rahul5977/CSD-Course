import maplibregl, { type Map as MLMap, type MapMouseEvent } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Feature, FeatureCollection, MultiPolygon, Polygon } from "geojson";
import { useEffect, useRef } from "react";
import type { CatchmentResult, LayerDescriptor, PourPoint, SiteCandidate } from "../types";

interface Props {
  layers: LayerDescriptor[];
  visible: Record<string, boolean>;
  boundary: Polygon | MultiPolygon | null;
  bounds: [number, number, number, number] | null;
  contours: FeatureCollection | null;
  streams: FeatureCollection | null;
  catchment: CatchmentResult | null;
  sites: SiteCandidate[];
  land: FeatureCollection | null;
  pond: { lon: number; lat: number; lengthM: number; widthM: number } | null;
  onClick: (point: PourPoint) => void;
}

/** Axis-aligned rectangle of L×W metres centred on a lon/lat, as a GeoJSON polygon. */
function pondFootprint(lon: number, lat: number, lengthM: number, widthM: number): Feature {
  const dLat = widthM / 2 / 111_320;
  const dLon = lengthM / 2 / (111_320 * Math.cos((lat * Math.PI) / 180));
  return {
    type: "Feature",
    properties: { kind: "pond" },
    geometry: { type: "Polygon", coordinates: [[[lon - dLon, lat - dLat], [lon + dLon, lat - dLat], [lon + dLon, lat + dLat], [lon - dLon, lat + dLat], [lon - dLon, lat - dLat]]] },
  };
}

/** World polygon with the boundary cut out: dims everything outside the analysed area. */
function focusMask(boundary: Polygon | MultiPolygon): Feature {
  const rings = boundary.type === "Polygon" ? [boundary.coordinates[0]] : boundary.coordinates.map((p) => p[0]);
  return { type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [[[-180, -85], [180, -85], [180, 85], [-180, 85], [-180, -85]], ...rings] } };
}

const ESRI =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };

function setGeoJSON(m: MLMap, id: string, data: FeatureCollection | Feature) {
  const source = m.getSource(id) as maplibregl.GeoJSONSource | undefined;
  if (source) source.setData(data);
  else m.addSource(id, { type: "geojson", data });
}

/** The map workspace. Raster layers come straight from the API's layer list; vectors are GeoJSON. */
export function MapView({ layers, visible, boundary, bounds, contours, streams, catchment, sites, land, pond, onClick }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const clickHandler = useRef(onClick);
  clickHandler.current = onClick;

  useEffect(() => {
    if (!container.current || map.current) return;
    const m = new maplibregl.Map({
      container: container.current,
      style: {
        version: 8,
        glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
        sources: { satellite: { type: "raster", tiles: [ESRI], tileSize: 256, maxzoom: 19 } },
        layers: [{ id: "satellite", type: "raster", source: "satellite" }],
      },
      center: [78.9, 21.5],
      zoom: 4.5,
      attributionControl: { compact: true },
    });
    m.addControl(new maplibregl.NavigationControl(), "top-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "metric" }));
    m.on("click", (e: MapMouseEvent) => clickHandler.current({ lon: e.lngLat.lng, lat: e.lngLat.lat }));
    m.getCanvas().style.cursor = "crosshair";
    // First frame: the container is laid out by CSS grid after construction, so force a
    // resize once the style is in; a ResizeObserver keeps it right on phone rotation.
    m.once("load", () => m.resize());
    const observer = new ResizeObserver(() => m.resize());
    observer.observe(container.current);
    map.current = m;
    return () => {
      observer.disconnect();
      m.remove();
      map.current = null;
    };
  }, []);

  // Raster layers from the API, in catalogue order, under every vector layer.
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const apply = () => {
      for (const layer of layers) {
        if (layer.layer_id === "satellite" || layer.kind !== "raster") continue;
        const id = `api-${layer.layer_id}`;
        if (!m.getSource(id)) {
          m.addSource(id, { type: "raster", tiles: [layer.tile_url_template], tileSize: 256, maxzoom: 18 });
          m.addLayer(
            { id, type: "raster", source: id, paint: { "raster-opacity": layer.layer_id === "hillshade" ? 0.55 : 0.75 } },
            m.getLayer("vec-boundary") ? "vec-boundary" : undefined,
          );
        }
        m.setLayoutProperty(id, "visibility", visible[layer.layer_id] ? "visible" : "none");
      }
    };
    if (m.isStyleLoaded()) apply();
    else m.once("load", apply);
  }, [layers, visible]);

  // Vector layers: boundary, contours (+labels), streams, catchment, sites.
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const apply = () => {
      setGeoJSON(m, "boundary", boundary ? { type: "Feature", geometry: boundary, properties: {} } : EMPTY);
      if (!m.getLayer("vec-boundary")) {
        m.addLayer({ id: "vec-boundary", type: "line", source: "boundary", paint: { "line-color": "#ffd166", "line-width": 2.5 } });
      }
      setGeoJSON(m, "contours", contours ?? EMPTY);
      if (!m.getLayer("vec-contours")) {
        m.addLayer({ id: "vec-contours", type: "line", source: "contours", paint: { "line-color": "#f4e3b2", "line-width": 1, "line-opacity": 0.9 } });
        m.addLayer({
          id: "vec-contour-labels",
          type: "symbol",
          source: "contours",
          layout: { "symbol-placement": "line", "text-field": ["to-string", ["get", "elevation"]], "text-size": 11, "text-font": ["Open Sans Regular"] },
          paint: { "text-color": "#fff8e1", "text-halo-color": "#2b2b2b", "text-halo-width": 1.2 },
        });
      }
      setGeoJSON(m, "streams", streams ?? EMPTY);
      if (!m.getLayer("vec-streams")) {
        m.addLayer({
          id: "vec-streams",
          type: "line",
          source: "streams",
          paint: { "line-color": "#4fc3f7", "line-width": ["+", 1, ["*", 1.2, ["get", "strahler_order"]]] },
        });
      }
      setGeoJSON(m, "focus", boundary ? focusMask(boundary) : EMPTY);
      if (!m.getLayer("vec-focus")) {
        m.addLayer({ id: "vec-focus", type: "fill", source: "focus", paint: { "fill-color": "#1f2a30", "fill-opacity": 0.45 } });
      }
      setGeoJSON(m, "pond", pond ? pondFootprint(pond.lon, pond.lat, pond.lengthM, pond.widthM) : EMPTY);
      if (!m.getLayer("vec-pond-fill")) {
        m.addLayer({ id: "vec-pond-fill", type: "fill", source: "pond", paint: { "fill-color": "#0b6e8f", "fill-opacity": 0.55 } });
        m.addLayer({ id: "vec-pond-line", type: "line", source: "pond", paint: { "line-color": "#ffffff", "line-width": 2 } });
      }
      setGeoJSON(m, "land", land ?? EMPTY);
      if (!m.getLayer("vec-land-fill")) {
        m.addLayer({ id: "vec-land-fill", type: "fill", source: "land", paint: { "fill-color": "#8bc34a", "fill-opacity": 0.3 } });
        m.addLayer({ id: "vec-land-line", type: "line", source: "land", paint: { "line-color": "#33691e", "line-width": 1.5, "line-dasharray": [2, 1] } });
      }
      setGeoJSON(m, "catchment", catchment?.geojson ?? EMPTY);
      if (!m.getLayer("vec-catchment-fill")) {
        m.addLayer({ id: "vec-catchment-fill", type: "fill", source: "catchment", filter: ["==", ["get", "kind"], "catchment"], paint: { "fill-color": "#1e88e5", "fill-opacity": 0.28 } });
        m.addLayer({ id: "vec-catchment-line", type: "line", source: "catchment", filter: ["==", ["get", "kind"], "catchment"], paint: { "line-color": "#0d47a1", "line-width": 2 } });
        m.addLayer({ id: "vec-outlet", type: "circle", source: "catchment", filter: ["==", ["get", "kind"], "outlet"], paint: { "circle-radius": 7, "circle-color": "#ff5722", "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });
      }
      const siteFc: FeatureCollection = {
        type: "FeatureCollection",
        features: sites.map((s) => ({ type: "Feature", geometry: { type: "Point", coordinates: [s.location.lon, s.location.lat] }, properties: { rank: s.rank } })),
      };
      setGeoJSON(m, "sites", siteFc);
      if (!m.getLayer("vec-sites")) {
        m.addLayer({ id: "vec-sites", type: "circle", source: "sites", paint: { "circle-radius": ["case", ["==", ["get", "rank"], 1], 11, 8], "circle-color": ["case", ["==", ["get", "rank"], 1], "#2e7d32", "#8bc34a"], "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });
        m.addLayer({ id: "vec-site-labels", type: "symbol", source: "sites", layout: { "text-field": ["to-string", ["get", "rank"]], "text-size": 12, "text-font": ["Open Sans Regular"] }, paint: { "text-color": "#fff" } });
      }
      const show = (id: string, on: boolean) => m.getLayer(id) && m.setLayoutProperty(id, "visibility", on ? "visible" : "none");
      show("vec-boundary", visible.boundary !== false);
      show("vec-contours", visible.contours !== false);
      show("vec-contour-labels", visible.contours !== false);
      show("vec-streams", visible.streams !== false);
      for (const id of ["vec-catchment-fill", "vec-catchment-line", "vec-outlet"]) show(id, visible.catchment !== false);
      show("vec-sites", visible.sites !== false);
      show("vec-focus", visible.focus === true);
      show("vec-pond-fill", visible.pond !== false);
      show("vec-pond-line", visible.pond !== false);
      show("vec-land-fill", visible.available_land === true);
      show("vec-land-line", visible.available_land === true);
      show("vec-site-labels", visible.sites !== false);
    };
    if (m.isStyleLoaded()) apply();
    else m.once("load", apply);
  }, [boundary, contours, streams, catchment, sites, land, pond, visible]);

  useEffect(() => {
    if (map.current && bounds) {
      map.current.fitBounds([bounds[0], bounds[1], bounds[2], bounds[3]], { padding: 40, duration: 800 });
    }
  }, [bounds]);

  return <div ref={container} className="map" role="region" aria-label="Map — click to delineate a catchment" />;
}

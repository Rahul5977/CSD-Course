import type { Feature, FeatureCollection, MultiPolygon, Polygon } from "geojson";
import type { components } from "./generated/openapi";

// Wire types. The generic envelopes come straight from the OpenAPI document
// (`npm run gen:api` regenerates src/generated/openapi.d.ts from
// docs/api/openapi.json), so a contract change fails the frontend build.
// Result payloads keep hand-written shapes where the generated ones are too
// loose for the map (GeoJSON geometry is `dict` on the wire).
type Schemas = components["schemas"];

export type QuantityOut = Schemas["QuantityOut"];
export type ResultWarning = Schemas["ResultWarning"];
export type JobAccepted = Schemas["JobAccepted"];
export type JobStatus = Schemas["JobStatus"];

export interface VillageOut {
  id: string;
  name: string;
  state_code: string | null;
  district: string | null;
  centroid: [number, number];
  utm_epsg: number;
  area: QuantityOut;
  boundary: Polygon | MultiPolygon | null;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
}

export interface LayerDescriptor {
  layer_id: string;
  kind: "raster" | "vector";
  title: string;
  tile_url_template: string;
  units: string | null;
  value_range: [number, number] | null;
  source: string;
}

export interface DEMAsset {
  source: string;
  native_resolution: QuantityOut;
  working_resolution: QuantityOut;
  vertical_accuracy_relative: QuantityOut;
  crs: string;
  attribution: string[];
  warnings: ResultWarning[];
}

export interface VillageSummary {
  village: VillageOut;
  elevation: { minimum: QuantityOut; maximum: QuantityOut; mean: QuantityOut; relief: QuantityOut };
  mean_slope: QuantityOut;
  dem_source: string;
  dem_vertical_accuracy: QuantityOut;
  warnings: ResultWarning[];
}

export interface PourPoint {
  lon: number;
  lat: number;
}

export interface CatchmentResult {
  village_id: string;
  requested_point: PourPoint;
  snapped_point: PourPoint;
  snap_distance: QuantityOut;
  area: QuantityOut;
  perimeter: QuantityOut;
  longest_flow_path: QuantityOut;
  mean_slope: QuantityOut;
  relief: QuantityOut;
  outlet_elevation: QuantityOut;
  flow_routing: string;
  cell_size: QuantityOut;
  geojson: FeatureCollection;
  warnings: ResultWarning[];
}

export interface SiteCandidate {
  rank: number;
  location: PourPoint;
  score: QuantityOut;
  upstream_area: QuantityOut;
  local_slope: QuantityOut;
  wetness_index: QuantityOut;
  impoundment_volume: QuantityOut;
  impoundment_efficiency: QuantityOut;
  criteria: Record<string, number>;
}

export interface SitingMethod {
  weights: Record<string, number>;
  nominal_rise: QuantityOut;
  max_slope: QuantityOut;
  suppression_radius: QuantityOut;
  stream_threshold: QuantityOut;
  candidates_considered: number;
  description: string;
}

export interface TerrainPreparationResult {
  village_id: string;
  village_name: string;
  elevation_source: string;
  contour_count: number;
  contour_interval: QuantityOut;
  grid_resolution: QuantityOut;
  utm_epsg: number;
  bounds: [number, number, number, number];
  layers: LayerDescriptor[];
  boundary_geojson: Polygon | MultiPolygon;
  dem: DEMAsset;
  warnings: ResultWarning[];
}

export interface ContourAnalysisResult {
  source_file: string;
  village_id: string;
  village_name: string;
  contour_count: number;
  elevation_source: string;
  bounds: [number, number, number, number];
  utm_epsg: number;
  grid_resolution: QuantityOut;
  suggested_pond_location: PourPoint;
  location_rationale: string;
  catchment: CatchmentResult;
  candidate_sites: SiteCandidate[];
  siting: SitingMethod;
  terrain: TerrainPreparationResult;
  warnings: ResultWarning[];
}

export interface ContourResponse {
  interval: QuantityOut;
  levels: number;
  vertices_before_simplification: number;
  vertices_after_simplification: number;
  geojson: FeatureCollection;
}

export interface StreamNetwork {
  accumulation_threshold: QuantityOut;
  total_length: QuantityOut;
  strahler_max_order: number;
  geojson: FeatureCollection;
}

export type AnyFeature = Feature;

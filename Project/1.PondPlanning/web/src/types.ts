import type { MultiPolygon, Polygon } from "geojson";

// Wire types, mirroring app/schemas. Generated typing (openapi-typescript)
// replaces this file in P5; for the skeleton a hand copy keeps the toolchain small.

export interface QuantityOut {
  value: number;
  unit: string;
  uncertainty_pct: number | null;
  low: number | null;
  high: number | null;
  method: string | null;
  display: string | null;
}

export interface ResultWarning {
  code: string;
  message: string;
  severity: "info" | "caution" | "critical";
}

export interface JobAccepted {
  job_id: string;
  status: "queued";
  poll_url: string;
  estimated_seconds: number;
}

export interface JobStatus {
  job_id: string;
  kind: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  progress: number;
  stage: string | null;
  error: { code: string; title: string } | null;
  result_url: string | null;
}

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

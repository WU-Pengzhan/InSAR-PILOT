export interface RemoteProduct {
  unavailable?: boolean; product_key?: string; remote_product_id: string; provider_id: string; mission: string;
  platform: string; product_type?: string; acquisition_time: string | null; relative_orbit?: number | null;
  orbit_direction?: string | null; polarizations: string[]; size_bytes?: number | null;
  footprint?: GeoJSON.Geometry; download_supported?: boolean; download_url?: string;
  query_source?: Record<string, unknown>;
}
export const productKey = (p: RemoteProduct) => p.product_key || `${p.provider_id || p.mission}::${p.remote_product_id}`
export const requestId = (p: RemoteProduct) => p.product_key || p.remote_product_id
export interface ProjectTarget { project_id: string; name: string; profile: string; revision: number }
export interface DownloadReadiness {
  ready?: boolean; aria2_available: boolean; credentials_configured: boolean; credentials_validated: boolean;
  gdal_available?: boolean; aria2_executable?: string; gdal_executable?: string; library_path: string;
  network?: NetworkSettings;
}
export interface NetworkSettings {
  mode: 'direct' | 'environment' | 'manual'; preset: 'balanced' | 'stable';
  http_proxy: string; https_proxy: string; limit_mib: number; timeout_seconds: number;
}
export interface AcquisitionPlan {
  plan_id: string; created_at: string; product_ids: string[]; products: RemoteProduct[];
  expected_revision: number | null; blockers: string[]; destination: string; known_bytes: number;
  unknown_files: number; free_bytes: number; destination_kind?: 'project' | 'library';
  files: {file_id: string; scene_id: string; role: string; status: string; size_bytes?: number; local_path?: string}[];
  dem: null | { geometry: GeoJSON.Geometry; tile_count: number; buffer_m: number; verified_geometry: boolean; height_reference: string };
}
export interface AcquisitionResult { project: ProjectTarget | null; job: {job_id: string; status: string} | null; plan_id: string }

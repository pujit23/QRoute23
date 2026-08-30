const API_BASE = '/api';

export interface LocationItem {
  display_name: string;
  name: string;
  lat: number;
  lon: number;
  place_type?: string;
}

export interface OptimizeRequestParams {
  preset?: string;
  start_location?: { name: string; coords: [number, number] };
  stops?: { name: string; coords: [number, number]; window?: [number, number] }[];
  vehicle_count?: number;
  round_trip?: boolean;
  mileage_kml?: number;
  fuel_price_inr?: number;
  qpso_params?: {
    swarm_size?: number;
    max_iter?: number;
    beta_start?: number;
    beta_end?: number;
    plateau_window?: number;
  };
}

export async function searchGeocode(query: string): Promise<LocationItem[]> {
  if (!query || query.trim().length < 2) return [];
  try {
    const res = await fetch(`${API_BASE}/geocode/search?q=${encodeURIComponent(query)}`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.results || [];
  } catch (err) {
    console.error("Geocode error:", err);
    return [];
  }
}

export async function runOptimization(params: OptimizeRequestParams) {
  const res = await fetch(`${API_BASE}/optimize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  if (!res.ok) {
    throw new Error(`Optimization failed: ${res.statusText}`);
  }
  return await res.json();
}

export async function fetchBenchmark(runId: string) {
  const res = await fetch(`${API_BASE}/benchmark/${runId}`);
  if (!res.ok) {
    throw new Error(`Benchmark fetch failed: ${res.statusText}`);
  }
  return await res.json();
}

export async function fetchNetworkHealth() {
  const res = await fetch(`${API_BASE}/network/health`);
  if (!res.ok) {
    throw new Error(`Network health fetch failed: ${res.statusText}`);
  }
  return await res.json();
}

export async function fetchReportData(runId: string, useCase: string = 'generic') {
  const res = await fetch(`${API_BASE}/report/${runId}?use_case=${encodeURIComponent(useCase)}`);
  if (!res.ok) {
    throw new Error(`Report fetch failed: ${res.statusText}`);
  }
  return await res.json();
}

export function getReportDownloadUrl(runId: string, format: 'pdf' | 'json' = 'pdf', useCase: string = 'generic') {
  return `${API_BASE}/report/${runId}/download?format=${format}&use_case=${encodeURIComponent(useCase)}`;
}


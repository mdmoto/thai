/**
 * API Client for Thailand Digital Market Twin FastAPI Backend Service
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined" && window.location.hostname.includes("lazzor.com")
    ? "https://ai-100282158973.asia-southeast1.run.app"
    : "http://127.0.0.1:8080");

export interface CreateStudyPayload {
  name: string;
  study_type: string;
  language?: string;
  plan_code?: string;
  product_name?: string;
  price?: number;
  url?: string;
  description?: string;
  selling_points?: string[];
  competitors?: string[];
  business_questions?: string[];
}

export interface RunSimulationPayload {
  study_id: string;
  plan_code?: string;
  population_size?: number;
  mc_rounds?: number;
  seed?: number;
}

export async function createStudyApi(payload: CreateStudyPayload) {
  const resp = await fetch(`${API_BASE_URL}/v1/studies`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    throw new Error(`Failed to create study: ${resp.statusText}`);
  }
  return resp.json();
}

export async function confirmStudyApi(studyId: string, overrides: Record<string, unknown> = {}) {
  const resp = await fetch(`${API_BASE_URL}/v1/studies/${studyId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ overrides }),
  });
  if (!resp.ok) {
    throw new Error(`Failed to confirm study: ${resp.statusText}`);
  }
  return resp.json();
}

export async function runSimulationApi(payload: RunSimulationPayload) {
  const resp = await fetch(`${API_BASE_URL}/v1/studies/${payload.study_id}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    throw new Error(`Failed to run simulation: ${resp.statusText}`);
  }
  return resp.json();
}

export async function getReportApi(reportId: string) {
  const resp = await fetch(`${API_BASE_URL}/v1/reports/${reportId}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch report: ${resp.statusText}`);
  }
  return resp.json();
}

export async function getStudyApi(studyId: string) {
  const resp = await fetch(`${API_BASE_URL}/v1/studies/${studyId}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch study: ${resp.statusText}`);
  }
  return resp.json();
}

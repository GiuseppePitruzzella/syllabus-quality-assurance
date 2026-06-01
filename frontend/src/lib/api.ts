import type {
  Department,
  CdL,
  SyllabusListItem,
  SyllabusDetail,
  Stats,
  JobCreated,
  EvaluationCreated,
  EvaluationDetail,
  EvaluationSummary,
} from "./types";

const BASE_URL = "http://localhost:8000/api";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, options);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const getDepartments = () =>
  fetchApi<Department[]>("/departments");

export const getCdl = (deptId: number) =>
  fetchApi<CdL[]>(`/departments/${deptId}/cdl`);

export const getSyllabi = (cdlId: number, search?: string) => {
  const params = search ? `?search=${encodeURIComponent(search)}` : "";
  return fetchApi<SyllabusListItem[]>(`/cdl/${cdlId}/syllabi${params}`);
};

export const getSyllabus = (seuid: string) =>
  fetchApi<SyllabusDetail>(`/syllabi/${seuid}`);

export const getStats = () =>
  fetchApi<Stats>("/stats");

export const scrapeDepartments = () =>
  fetchApi<JobCreated>("/scrape/departments", { method: "POST" });

export const scrapeCdl = (deptId: number) =>
  fetchApi<JobCreated>(`/scrape/departments/${deptId}/cdl`, { method: "POST" });

export const scrapeSyllabiList = (cdlId: number) =>
  fetchApi<JobCreated>(`/scrape/cdl/${cdlId}/syllabi`, { method: "POST" });

export const scrapeSyllabusDetail = (seuid: string) =>
  fetchApi<SyllabusDetail>(`/scrape/syllabi/${seuid}`, { method: "POST" });

// ---------------------------------------------------------------------------
// Phase 5.5 — Evaluation endpoints (Phase 5.4.H.2 API surface)
// ---------------------------------------------------------------------------

/**
 * Kick off an evaluation. Returns `{evaluation_uuid}` with HTTP 202 —
 * the run continues asynchronously on the server; subscribe to the SSE
 * stream (`connectEvaluationSse`) to follow progress in real time.
 */
export const startEvaluation = (seuid: string) =>
  fetchApi<EvaluationCreated>(`/evaluate/${seuid}`, { method: "POST" });

/**
 * Fetch one evaluation row by UUID. Works for any status:
 * `pending` / `running` / `completed` / `partial` / `failed`.
 */
export const getEvaluation = (evaluationUuid: string) =>
  fetchApi<EvaluationDetail>(`/evaluations/${evaluationUuid}`);

/**
 * History of evaluations for a syllabus, most recent first (D038).
 * Defaults to `limit=20` server-side.
 */
export const listEvaluationsForSyllabus = (seuid: string, limit?: number) => {
  const qs = typeof limit === "number" ? `?limit=${limit}` : "";
  return fetchApi<EvaluationSummary[]>(`/syllabi/${seuid}/evaluations${qs}`);
};

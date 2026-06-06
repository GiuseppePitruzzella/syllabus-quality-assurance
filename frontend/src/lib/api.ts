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
  LocalDocument,
  LocalDocumentStatus,
  LocalDocumentType,
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

// ---------------------------------------------------------------------------
// Phase 8 — local-document registry
// ---------------------------------------------------------------------------

export interface LocalDocumentListFilters {
  cdl_id?: number;
  document_type?: LocalDocumentType;
  status?: LocalDocumentStatus;
  include_deleted?: boolean;
}

/** List documents, ordered by `uploaded_at desc` server-side. */
export const listLocalDocuments = (filters: LocalDocumentListFilters = {}) => {
  const params = new URLSearchParams();
  if (filters.cdl_id !== undefined) params.set("cdl_id", String(filters.cdl_id));
  if (filters.document_type) params.set("document_type", filters.document_type);
  if (filters.status) params.set("status", filters.status);
  if (filters.include_deleted) params.set("include_deleted", "true");
  const qs = params.toString();
  return fetchApi<LocalDocument[]>(`/local-documents${qs ? `?${qs}` : ""}`);
};

export const getLocalDocument = (id: number) =>
  fetchApi<LocalDocument>(`/local-documents/${id}`);

/** Hard-delete the document (DB row + file + Chroma chunks). */
export const deleteLocalDocument = async (id: number): Promise<void> => {
  const res = await fetch(`${BASE_URL}/local-documents/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
};

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
  LocalDocumentChunkPreview,
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

export interface LocalDocumentUploadResponse {
  document: LocalDocument;
  job_id: string | null;
}

export interface LocalDocumentUploadPayload {
  cdl_id: number;
  document_type: LocalDocumentType;
  academic_year: string;
  title: string;
  enabled_criteria?: string[]; // CSV-encoded server-side, omitted -> defaults
  file: File;
}

export interface LocalDocumentPatchResponse {
  document: LocalDocument;
  job_id: string | null;
}

/** Replace `enabled_criteria` on a document. Schedules an async
 *  reindex when the row is already `indexed`; otherwise the DB
 *  update is recorded and `job_id` stays `null`. */
export const patchLocalDocumentCriteria = async (
  id: number,
  enabled_criteria: string[],
): Promise<LocalDocumentPatchResponse> => {
  const res = await fetch(`${BASE_URL}/local-documents/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled_criteria }),
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
};

/** Multipart upload + immediate async indexing trigger. */
export const uploadLocalDocument = async (
  payload: LocalDocumentUploadPayload,
): Promise<LocalDocumentUploadResponse> => {
  const form = new FormData();
  form.set("cdl_id", String(payload.cdl_id));
  form.set("document_type", payload.document_type);
  form.set("academic_year", payload.academic_year);
  form.set("title", payload.title);
  if (payload.enabled_criteria && payload.enabled_criteria.length > 0) {
    form.set("enabled_criteria", payload.enabled_criteria.join(","));
  }
  form.set("file", payload.file);
  const res = await fetch(`${BASE_URL}/local-documents`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
};

/** Read-only chunk preview for the current version of the document.
 *  Sorted by `chunk_order` server-side. */
export const getLocalDocumentChunks = (
  id: number,
  options: { limit?: number; text_preview_chars?: number } = {},
) => {
  const params = new URLSearchParams();
  if (options.limit) params.set("limit", String(options.limit));
  if (options.text_preview_chars)
    params.set("text_preview_chars", String(options.text_preview_chars));
  const qs = params.toString();
  return fetchApi<LocalDocumentChunkPreview[]>(
    `/local-documents/${id}/chunks${qs ? `?${qs}` : ""}`,
  );
};

/** Hard-delete the document (DB row + file + Chroma chunks). */
export const deleteLocalDocument = async (id: number): Promise<void> => {
  const res = await fetch(`${BASE_URL}/local-documents/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
};

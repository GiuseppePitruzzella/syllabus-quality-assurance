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
  ResolutionPreview,
  AuthResponse,
  AuthUser,
} from "./types";

const BASE_URL = "http://localhost:8000/api";

/**
 * Typed API error preserving the HTTP status, the raw detail
 * payload and — when the backend surfaces it (Phase 9.E.1 422
 * validations) — a structured ``code`` so the UI can branch on
 * the specific rule that fired.
 *
 * The generic ``fetchApi`` wrapper always raises this exception
 * on a non-2xx response. Callers that need to distinguish error
 * types can ``catch`` it and inspect ``status`` / ``code`` /
 * ``detail``.
 */
export class ApiError<Code extends string = string> extends Error {
  readonly status: number;
  readonly detail: unknown;
  readonly code: Code | undefined;

  constructor(opts: {
    status: number;
    statusText: string;
    detail: unknown;
    code?: Code;
    message?: string;
  }) {
    super(
      opts.message ?? `API error: ${opts.status} ${opts.statusText}`,
    );
    this.name = "ApiError";
    this.status = opts.status;
    this.detail = opts.detail;
    this.code = opts.code;
  }
}

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    credentials: "include",
    ...options,
  });
  if (!res.ok) {
    let detail: unknown = null;
    // The backend sends structured JSON for 4xx (FastAPI's
    // ``HTTPException(detail=...)``). Parse defensively so a
    // malformed response can't crash the UI.
    try {
      detail = await res.clone().json();
    } catch {
      try {
        detail = await res.text();
      } catch {
        detail = null;
      }
    }
    // Phase 9.E.1 validators surface `{ "detail": { "code", "message" } }`.
    // FastAPI may also send `{ "detail": "<string>" }` or
    // `{ "detail": [{...}] }` (Pydantic 422). Extract the code only
    // when the nested shape matches the 9.E.1 contract.
    const inner =
      detail && typeof detail === "object" && "detail" in detail
        ? (detail as { detail: unknown }).detail
        : undefined;
    const code =
      inner && typeof inner === "object" && "code" in inner
        ? (inner as { code: unknown }).code
        : undefined;
    const message =
      inner && typeof inner === "object" && "message" in inner
        ? (inner as { message: unknown }).message
        : undefined;
    throw new ApiError({
      status: res.status,
      statusText: res.statusText,
      detail,
      code: typeof code === "string" ? code : undefined,
      message: typeof message === "string" ? message : undefined,
    });
  }
  return res.json();
}

export interface RegisterPayload {
  full_name: string;
  email: string;
  password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
}

export const register = (payload: RegisterPayload) =>
  fetchApi<AuthResponse>("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const login = (payload: LoginPayload) =>
  fetchApi<AuthResponse>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const logout = async (): Promise<void> => {
  const res = await fetch(`${BASE_URL}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) {
    throw new ApiError({
      status: res.status,
      statusText: res.statusText,
      detail: null,
    });
  }
};

export const getCurrentUser = () =>
  fetchApi<AuthUser>("/auth/me");

export const changePassword = (payload: ChangePasswordPayload) =>
  fetchApi<AuthUser>("/auth/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

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
/**
 * Kick off an evaluation. Phase 9.E.1 lets the caller pin specific
 * ``LocalDocument`` versions via ``selectedDocumentIds``. The
 * options object is open-ended so future additions (e.g. dry-run,
 * custom prompt overrides) stay backwards compatible.
 *
 * When ``selectedDocumentIds`` is undefined / empty the request
 * is sent without a body — the resolver's standard precedence
 * ladder kicks in. With explicit ids, the validation runs
 * server-side and surfaces structured 422s via :class:`ApiError`.
 */
export interface StartEvaluationOptions {
  selectedDocumentIds?: number[];
}

export const startEvaluation = (
  seuid: string,
  options?: StartEvaluationOptions,
) => {
  const ids = options?.selectedDocumentIds ?? [];
  const init: RequestInit = { method: "POST" };
  if (ids.length > 0) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify({ selected_document_ids: ids });
  }
  return fetchApi<EvaluationCreated>(`/evaluate/${seuid}`, init);
};

/**
 * Phase 9.E.1 — typed view of the resolver's verdict for this
 * syllabus, plus the alternatives the user can pick. The
 * response is deterministic and side-effect-free: ``GET`` only.
 */
export const getResolutionPreview = (seuid: string) =>
  fetchApi<ResolutionPreview>(`/syllabi/${seuid}/resolution-preview`);

/**
 * Closed enum of structured validation codes the backend emits
 * on a 422 from POST /api/evaluate/{seuid}. Re-exported here so
 * UI consumers can match without hardcoding the strings.
 */
export type { SelectedDocumentValidationCode } from "./types";

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
    credentials: "include",
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
    credentials: "include",
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
    credentials: "include",
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
};

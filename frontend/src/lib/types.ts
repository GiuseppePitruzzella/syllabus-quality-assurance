export interface Department {
  id: number;
  name: string;
  area: string;
  website_url: string;
  email: string;
  phone: string;
  director: string;
  scraped_at: string;
}

export interface CdL {
  id: number;
  department_id: number;
  name: string;
  code: string;
  type: string;
  academic_year: string | null;
  url: string;
  scraped_at: string;
}

export interface SyllabusListItem {
  id: number;
  cdl_id: number;
  seuid: string;
  course_code: string;
  course_name: string;
  module: string | null;
  teacher: string;
  academic_year: string;
  year_of_study: string;
  url_it: string;
  url_en: string;
  has_english: boolean;
  scraped_at: string;
}

export interface SyllabusDetail extends SyllabusListItem {
  learning_outcomes_it: string | null;
  dublin_knowledge_it: string | null;
  dublin_applying_it: string | null;
  dublin_judgement_it: string | null;
  dublin_communication_it: string | null;
  dublin_learning_it: string | null;
  teaching_methods_it: string | null;
  prerequisites_it: string | null;
  attendance_it: string | null;
  course_content_it: string | null;
  references_it: string | null;
  schedule_it: ScheduleItem[] | null;
  assessment_methods_it: string | null;
  sample_questions_it: string | null;
  learning_outcomes_en: string | null;
  dublin_knowledge_en: string | null;
  dublin_applying_en: string | null;
  dublin_judgement_en: string | null;
  dublin_communication_en: string | null;
  dublin_learning_en: string | null;
  teaching_methods_en: string | null;
  prerequisites_en: string | null;
  attendance_en: string | null;
  course_content_en: string | null;
  references_en: string | null;
  schedule_en: ScheduleItem[] | null;
  assessment_methods_en: string | null;
  sample_questions_en: string | null;
  cdl_name: string | null;
  department_id: number | null;
  department_name: string | null;
}

export interface ScheduleItem {
  numero?: string;
  argomenti?: string;
  riferimenti_testi?: string;
  subjects?: string;
  subject?: string;
  topics?: string;
  topic?: string;
  text_references?: string;
  textbook_references?: string;
  references?: string;
}

export interface Stats {
  departments: number;
  cdl: number;
  syllabi: number;
  with_english: number;
}

export interface JobCreated {
  job_id: string;
}

export interface SseProgress {
  type: "progress";
  current: number;
  total: number;
  message: string;
}

export interface SseDone {
  type: "done";
  scraped: number;
  errors: number;
}

export interface SseError {
  type: "error";
  message: string;
}

export type SseEvent = SseProgress | SseDone | SseError;

// ---------------------------------------------------------------------------
// Phase 5.5 — Evaluation endpoints (mirrors backend app/schemas/evaluation.py
// and app/schemas/evaluation_event.py)
// ---------------------------------------------------------------------------

export type EvaluationStatus =
  | "pending"
  | "running"
  | "completed"
  | "partial"
  | "failed";

export interface EvaluationCreated {
  /** Returned by `POST /api/evaluate/{seuid}` with HTTP 202. */
  evaluation_uuid: string;
}

/** Compact shape returned by `GET /api/syllabi/{seuid}/evaluations`. */
export interface EvaluationSummary {
  evaluation_uuid: string;
  syllabus_seuid_snapshot: string;
  course_name_snapshot: string;
  status: EvaluationStatus;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  core_score: number | null;
  coverage: number | null;
  llm_model: string;
  embedding_model: string;
  prompt_versions: Record<string, string>;
}

/** Full shape returned by `GET /api/evaluations/{evaluation_uuid}`. */
export interface EvaluationDetail extends EvaluationSummary {
  embedding_dim: number;
  llm_temperature: number;
  llm_max_output_tokens: number;
  rag_top_k: number;
  rag_final_k: number;
  rag_similarity_threshold: number;
  gcp_project_id: string;
  gcp_location: string;
  error_message: string | null;
  /** Map criterion_code -> score (0 / 1 / 2) or null when NA / unevaluated. */
  criterion_scores: Record<string, number | null> | null;
  na_criteria: NACriterionRecord[] | null;
  agent_outputs: Record<string, AgentOutputDump | null> | null;
  agent_errors: Record<string, string> | null;
  retrieved_chunks: Record<string, RetrievedChunkRef[]> | null;
  final_report: string | null;
}

export interface NACriterionRecord {
  criterion_code: string;
  source: "agent" | "agent_error" | string;
  reason: string;
}

export interface AgentOutputDump {
  agent_code: string;
  judgments: CriterionJudgmentDump[];
  execution_metadata: {
    latency_ms?: number;
    retry_count?: number;
    prompt_version?: string;
    criteria_codes?: string[];
    retrieved_chunks_count?: number;
    max_output_tokens_override?: number | null;
    llm_metadata?: Record<string, unknown>;
    [key: string]: unknown;
  };
  retrieved_chunks: RetrievedChunkRef[];
}

export interface CriterionJudgmentDump {
  criterion_code: string;
  score: number | null;
  is_na: boolean;
  na_reason: string | null;
  justification: string;
  evidences: { text: string; source_field: string }[];
  confidence: "low" | "medium" | "high" | string;
}

export interface RetrievedChunkRef {
  criterion_code: string;
  chunk_id: string;
  document_id: string | null;
  section_ref: string | null;
  similarity_score: number | null;
}

/** SSE event types emitted by the evaluation stream (8 typed kinds). */
export type EvaluationEventType =
  | "evaluation_started"
  | "agent_started"
  | "agent_completed"
  | "agent_failed"
  | "aggregation_completed"
  | "report_synthesized"
  | "evaluation_completed"
  | "error";

// ---------------------------------------------------------------------------
// Phase 8 — local-document registry
// ---------------------------------------------------------------------------

/** Closed enum for document_type. Mirrors backend `DocumentType` literal.
 *  Phase 9.A adds `matrice_tuning` as the sole source of E2. */
export type LocalDocumentType =
  | "regolamento_didattico"
  | "sua_cds"
  | "matrice_tuning"
  | "piano_studi"
  | "manifesto"
  | "propedeuticita"
  | "metadati_ufficiali"
  | "usi_dipartimentali"
  | "linee_guida_cdl"
  | "template_locale"
  | "nota_presidio";

/** Closed enum for the lifecycle status. */
export type LocalDocumentStatus =
  | "uploaded"
  | "extracting"
  | "chunking"
  | "indexing"
  | "indexed"
  | "failed";

/** Closed enum for the extended criterion codes. */
export type ExtendedCriterionCode = "E1" | "E2" | "E3" | "E4" | "E5";

/** Mirror of `LocalDocumentResponse` in the backend. */
export interface LocalDocument {
  id: number;
  cdl_id: number;
  document_type: LocalDocumentType;
  academic_year: string;
  title: string;
  normalized_title: string;
  file_path: string;
  file_extension: string;
  file_hash: string;
  file_size: number;
  version: number;
  enabled_criteria: ExtendedCriterionCode[];
  status: LocalDocumentStatus;
  chunk_count: number | null;
  failure_reason: string | null;
  uploaded_at: string;
  indexed_at: string | null;
  deleted_at: string | null;
}

/** Mirror of `ChunkPreview` (used by 8.D.D, declared here for symmetry). */
export interface LocalDocumentChunkPreview {
  chunk_id: string;
  chunk_order: number;
  char_count: number;
  document_id: number;
  version: number;
  text_preview: string;
  tags: Record<string, boolean>;
}

/**
 * Flat shape mirroring `app/schemas/evaluation_event.py::ProgressEvent`.
 * All per-type fields are optional; consumers branch on `type`.
 */
export interface EvaluationProgressEvent {
  type: EvaluationEventType;
  evaluation_uuid: string;
  timestamp: string;
  seuid?: string | null;
  course_name?: string | null;
  agent_code?: string | null;
  latency_ms?: number | null;
  n_judgments?: number | null;
  status?: string | null;
  core_score?: number | null;
  coverage?: number | null;
  n_na?: number | null;
  report_chars?: number | null;
  duration_ms?: number | null;
  error_type?: string | null;
  error_message?: string | null;
}

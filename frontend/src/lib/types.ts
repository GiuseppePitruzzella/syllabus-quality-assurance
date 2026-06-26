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
  course_name_en: string | null;
  module: string | null;
  teacher: string;
  academic_year: string;
  year_of_study: string;
  url_it: string;
  url_en: string;
  has_english: boolean;
  content_scraped: boolean;
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

export type UserRole = "admin" | "quality_reviewer" | "technical_reviewer";
export type RegisterableUserRole = "quality_reviewer" | "technical_reviewer";

export interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  user: AuthUser;
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
  /** Phase 9.D.1 — compact typed A5 result. ``null`` for legacy runs
   *  (pre-9.C.5.3) so the consumer can render an EmptyState. */
  extended_criteria_result: ExtendedCriteriaResultPayload | null;
  /** Phase 9.D.1 — audit-table view of which registry documents fed
   *  which extended criterion in this run. Empty when no document was
   *  consumed. Order: by criterion_code asc, local_document_id asc. */
  external_documents_used: ExternalDocumentUsedPayload[];
}

// ---------------------------------------------------------------------------
// Phase 12 — Results summary page
// ---------------------------------------------------------------------------

export type CoreCriterionCode =
  | "C1"
  | "C2"
  | "C3"
  | "C4"
  | "C5"
  | "C6"
  | "C7"
  | "C8"
  | "C9";

export interface ResultsOverview {
  latest_evaluations_count: number;
  terminal_runs_count: number;
  completed_count: number;
  partial_count: number;
  failed_count: number;
  average_core_score: number | null;
  average_coverage: number | null;
  total_critical_criteria: number;
  total_improvable_criteria: number;
  total_na_criteria: number;
}

export interface CriterionDistribution {
  criterion_code: CoreCriterionCode;
  score_0: number;
  score_1: number;
  score_2: number;
  na: number;
  evaluated: number;
}

export interface ResultsEvaluationRow {
  evaluation_uuid: string;
  syllabus_seuid: string;
  cdl_id: number;
  course_name: string;
  cdl_name: string | null;
  cdl_code: string | null;
  department_name: string | null;
  status: Extract<EvaluationStatus, "completed" | "partial" | "failed">;
  started_at: string;
  finished_at: string | null;
  core_score: number | null;
  coverage: number | null;
  critical_count: number;
  improvable_count: number;
  adequate_count: number;
  na_count: number;
}

export interface HumanValidationSummary {
  status: "not_available" | "in_preparation";
  title: string;
  description: string;
}

export interface ResultsSummary {
  generated_at: string;
  overview: ResultsOverview;
  criteria: CriterionDistribution[];
  evaluations: ResultsEvaluationRow[];
  human_validation: HumanValidationSummary;
}

// ---------------------------------------------------------------------------
// Normative corpus — fixed CoreScore sources
// ---------------------------------------------------------------------------

export type CoreAgentCode = "A1" | "A2" | "A3" | "A4";

export interface NormativeCorpusDocument {
  document_id: string;
  title: string;
  version: string;
  source_type: string;
  priority: number;
  filename: string;
  file_hash: string;
  file_size: number;
  chunk_count: number;
  core_chunk_count: number;
  core_criteria: CoreCriterionCode[];
  agents: CoreAgentCode[];
  is_core_source: boolean;
}

// ---------------------------------------------------------------------------
// Phase 9.D.1 — Extended-criteria (E1-E5) payloads (mirror of
// app/schemas/evaluation.py)
// ---------------------------------------------------------------------------

export type ExtendedStatus = "completed" | "partial" | "failed";

/** Closed enum: the *provenance* of an extended NA. ``handler_error``
 *  is the *technical* NA branch — the UI must surface it distinctly
 *  from the other two (semantic NA). */
export type ExtendedNASource = "resolver" | "handler_na" | "handler_error";

/** Closed enum: criteria served by the registry. E4 is NEVER here by
 *  construction (it's syllabus-served and never produces an audit
 *  row). The type forbids passing E4 to anything expecting this
 *  variant. */
export type RegistryServedCriterion = "E1" | "E2" | "E3" | "E5";

export type ResolutionReason =
  | "explicit_selection"
  | "academic_year_match"
  | "latest_available_fallback";

export interface ExtendedEvidencePayload {
  text: string;
  source_field: string | null;
  source_document_id: number | null;
  source_chunk_id: string | null;
}

export interface ExtendedJudgmentPayload {
  criterion_code: ExtendedCriterionCode;
  score: 0 | 1 | 2 | null;
  is_na: boolean;
  is_na_technical: boolean;
  na_reason: string | null;
  justification: string;
  evidences: ExtendedEvidencePayload[];
  confidence: "low" | "medium" | "high";
}

export interface ExtendedNAPayload {
  criterion_code: ExtendedCriterionCode;
  source: ExtendedNASource;
  reason: string;
}

export interface ExtendedCriteriaResultPayload {
  status: ExtendedStatus;
  /** Per-criterion score, ``null`` for NA. Keys are E* codes. */
  criterion_scores: Record<string, number | null>;
  na_criteria: ExtendedNAPayload[];
  /** Map E* -> error message. Always populated when the matching
   *  criterion is reported as ``handler_error`` in ``na_criteria``. */
  handler_errors: Record<string, string>;
  judgments: ExtendedJudgmentPayload[];
  /** Map E* -> prompt version actually used in this run. Includes
   *  only handlers that were invoked. */
  handler_prompt_versions: Record<string, string>;
}

// ---------------------------------------------------------------------------
// Phase 9.E.1 — Resolution preview + selected-document validation
// ---------------------------------------------------------------------------

/** Closed enum: the source that serves an extended criterion in the
 *  preview. ``registry`` is E1/E2/E3/E5; ``syllabus`` is E4 with
 *  ``has_english=true``; ``none`` is the resolver-NA state. */
export type ResolutionPreviewServedBy = "registry" | "syllabus" | "none";

/** Closed enum of structured codes returned by the backend on 422
 *  from ``POST /api/evaluate/{seuid}`` when ``selected_document_ids``
 *  violates a Phase 9.E.1 rule. Used by the dialog to render an
 *  actionable error per row instead of a generic toast. */
export type SelectedDocumentValidationCode =
  | "duplicate"
  | "unknown"
  | "not_indexed"
  | "archived"
  | "wrong_cdl"
  | "no_enabled_criteria";

export interface ResolutionPreviewCandidate {
  local_document_id: number;
  /** Stable per-chain identifier. Two versions of the same
   *  document share the value; two different chains differ.
   *  Format: ``{document_type}::{normalized_title}``.
   *  Phase 9.E.2.fix: the dialog groups radios by chain so an
   *  override on one chain does not blank out the auto pick on
   *  another (multi-chain E5 case). */
  chain_key: string;
  title: string;
  document_type: LocalDocumentType;
  version: number;
  file_hash: string;
  academic_year: string;
  enabled_criteria: ExtendedCriterionCode[];
  /** True when the resolver's precedence ladder picks this row
   *  for its chain. Exactly one candidate per chain is flagged. */
  is_auto_resolved: boolean;
  /** Populated only on the auto-resolved candidate. */
  resolution_reason: ResolutionReason | null;
  /** ISO timestamp set when the document was soft-deleted. */
  deleted_at: string | null;
  /** ``false`` for soft-deleted rows — visible for transparency
   *  but cannot feed new evaluations (Phase 9.E policy). */
  selectable: boolean;
}

export interface ResolutionPreviewCriterion {
  criterion_code: ExtendedCriterionCode;
  served_by: ResolutionPreviewServedBy;
  applicable: boolean;
  na_reason: string | null;
  /** Empty list for E4 (always) and for ``served_by="none"``. */
  candidates: ResolutionPreviewCandidate[];
}

export interface ResolutionPreview {
  seuid: string;
  cdl_id: number;
  academic_year: string | null;
  has_english: boolean;
  by_criterion: Record<ExtendedCriterionCode, ResolutionPreviewCriterion>;
}

export interface ExternalDocumentUsedPayload {
  criterion_code: RegistryServedCriterion;
  local_document_id: number;
  document_type: LocalDocumentType;
  document_version: number;
  file_hash: string;
  resolution_reason: ResolutionReason;
  /** Title from the live registry row. ``null`` only if the row was
   *  hard-deleted (RESTRICT FK should normally prevent this). */
  title: string | null;
  /** ISO timestamp set when the document was soft-deleted after
   *  this run. UI should display a "archiviato" pill in that case. */
  deleted_at: string | null;
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

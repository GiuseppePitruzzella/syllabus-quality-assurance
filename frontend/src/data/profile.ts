/**
 * Phase 7 — read-only snapshot of the active evaluation profile.
 *
 * SOURCES OF TRUTH (kept in sync MANUALLY — no runtime fetch):
 *   - prompt versions          backend/app/evaluation/service.py
 *                              `DEFAULT_PROMPT_VERSIONS`
 *   - LLM / embedding / RAG    backend/app/config.py `ScientificConfig`
 *   - A1 max-tokens override   backend/app/evaluation/agents/a1_completeness.py
 *   - rubric label / scope     docs/progettazione.md §2.4-2.6
 *
 * If any of these change, this file is updated by hand and the
 * profile is implicitly versioned by the commit. The `locked: true`
 * flag below documents the methodological constraint: a profile
 * change should yield a new profile version, not silently mutate
 * the current one.
 */

export interface PromptVersionEntry {
  agent: string;
  version: string;
}

export interface EvaluationProfile {
  name: string;
  rubric_label: string;
  llm_model: string;
  embedding_model: string;
  embedding_output_dimensionality: number;
  llm_temperature: number;
  llm_max_output_tokens: number;
  llm_a1_max_output_tokens_override: number;
  rag_top_k: number;
  rag_similarity_threshold: number;
  gcp_location: string;
  prompt_versions: PromptVersionEntry[];
  locked: boolean;
  locked_reason: string;
}

export const ACTIVE_PROFILE: EvaluationProfile = {
  name: "LM-18 / Tesi v1",
  rubric_label: "C1-C9 (core) + E1-E5 (estesi, sperimentali)",
  llm_model: "gemini-2.5-flash",
  embedding_model: "gemini-embedding-001",
  embedding_output_dimensionality: 3072,
  llm_temperature: 0.1,
  llm_max_output_tokens: 8192,
  llm_a1_max_output_tokens_override: 16384,
  rag_top_k: 5,
  rag_similarity_threshold: 0.6,
  gcp_location: "europe-west1",
  prompt_versions: [
    { agent: "A1", version: "a1_v6" },
    { agent: "A2", version: "a2_v1" },
    { agent: "A3", version: "a3_v1" },
    { agent: "A4", version: "a4_v10" },
  ],
  locked: true,
  locked_reason:
    "Profilo bloccato per riproducibilità della validazione sperimentale Phase 5.7 (30 syllabi LM-18) e dei giudizi umani Phase 5.8 (shortlist 8 syllabi). Una modifica ai parametri deve generare una nuova versione del profilo, non mutare quello esistente.",
};

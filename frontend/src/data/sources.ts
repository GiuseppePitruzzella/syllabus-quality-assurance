/**
 * Phase 8.D — UI metadata for the local-document registry.
 *
 * Italian labels + colour mapping for `document_type` and
 * `status`. Kept here (not in `data/rubric.ts`) so the Settings
 * page treats the registry as a separate governance surface from
 * the rubric itself.
 */
import type {
  ExtendedCriterionCode,
  LocalDocumentStatus,
  LocalDocumentType,
} from "@/lib/types";

export interface DocumentTypeLabel {
  code: LocalDocumentType;
  label: string;
  /** Which extended criteria the registry auto-assigns on upload.
   *  Mirrors backend `DEFAULT_ENABLED_CRITERIA`. */
  default_enabled: ExtendedCriterionCode[];
  /** Which extended criteria are admissible for this type. Server-
   *  side validation enforces `enabled_criteria ⊆ allowed_criteria`
   *  on upload and PATCH. Mirrors backend
   *  `ALLOWED_CRITERIA_BY_DOCUMENT_TYPE`. */
  allowed_criteria: ExtendedCriterionCode[];
}

/**
 * Phase 9.A — consolidated document-to-criterion contract.
 *
 * Mirrors the backend invariants in
 * `app/schemas/local_document.py::DEFAULT_ENABLED_CRITERIA` and
 * `ALLOWED_CRITERIA_BY_DOCUMENT_TYPE`. Server-side validation
 * rejects any explicit `enabled_criteria` that exceeds the allowed
 * set for the document type, so the modal / inline editor SHOULD
 * use `allowed_criteria` to gate which chips are toggleable
 * (drives the UX in Phase 9.E).
 *
 * Four types are kept in the registry as context-only
 * (`piano_studi`, `manifesto`, `propedeuticita`,
 * `metadati_ufficiali`): they don't auto-serve any extended
 * criterion and the registry won't accept one.
 */
export const DOCUMENT_TYPES: DocumentTypeLabel[] = [
  { code: "regolamento_didattico", label: "Regolamento didattico", default_enabled: ["E3"], allowed_criteria: ["E3"] },
  { code: "sua_cds", label: "SUA-CdS", default_enabled: ["E1"], allowed_criteria: ["E1"] },
  { code: "matrice_tuning", label: "Matrice di Tuning", default_enabled: ["E2"], allowed_criteria: ["E2"] },
  { code: "piano_studi", label: "Piano di studi", default_enabled: [], allowed_criteria: [] },
  { code: "manifesto", label: "Manifesto", default_enabled: [], allowed_criteria: [] },
  { code: "propedeuticita", label: "Propedeuticità", default_enabled: [], allowed_criteria: [] },
  { code: "metadati_ufficiali", label: "Metadati ufficiali", default_enabled: [], allowed_criteria: [] },
  { code: "usi_dipartimentali", label: "Usi dipartimentali", default_enabled: ["E5"], allowed_criteria: ["E5"] },
  { code: "linee_guida_cdl", label: "Linee guida CdL", default_enabled: ["E5"], allowed_criteria: ["E5"] },
  { code: "template_locale", label: "Template locale", default_enabled: ["E5"], allowed_criteria: ["E5"] },
  { code: "nota_presidio", label: "Nota presidio", default_enabled: ["E5"], allowed_criteria: ["E5"] },
];

export function allowedCriteriaFor(
  code: LocalDocumentType,
): ExtendedCriterionCode[] {
  return DOCUMENT_TYPES.find((t) => t.code === code)?.allowed_criteria ?? [];
}

export function labelForDocumentType(code: LocalDocumentType): string {
  return DOCUMENT_TYPES.find((t) => t.code === code)?.label ?? code;
}

export interface StatusVisual {
  label: string;
  /** Tailwind palette tone used to colour the badge. */
  tone: "emerald" | "amber" | "rose" | "cyan" | "slate";
  /** True while the document is on its way to `indexed`. */
  in_flight: boolean;
}

export const STATUS_VISUALS: Record<LocalDocumentStatus, StatusVisual> = {
  uploaded: {
    label: "caricato",
    tone: "slate",
    in_flight: true,
  },
  extracting: {
    label: "estrazione",
    tone: "cyan",
    in_flight: true,
  },
  chunking: {
    label: "chunking",
    tone: "cyan",
    in_flight: true,
  },
  indexing: {
    label: "indicizzazione",
    tone: "cyan",
    in_flight: true,
  },
  indexed: {
    label: "indicizzato",
    tone: "emerald",
    in_flight: false,
  },
  failed: {
    label: "fallito",
    tone: "rose",
    in_flight: false,
  },
};

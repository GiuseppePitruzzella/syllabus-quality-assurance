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
  /** Which extended criteria the registry would default to. Mirrors
   *  `DEFAULT_ENABLED_CRITERIA` in the backend. */
  default_enabled: ExtendedCriterionCode[];
}

export const DOCUMENT_TYPES: DocumentTypeLabel[] = [
  { code: "regolamento_didattico", label: "Regolamento didattico", default_enabled: ["E1"] },
  { code: "sua_cds", label: "SUA-CdS", default_enabled: ["E1"] },
  { code: "piano_studi", label: "Piano di studi", default_enabled: ["E2"] },
  { code: "manifesto", label: "Manifesto", default_enabled: ["E2"] },
  { code: "propedeuticita", label: "Propedeuticità", default_enabled: ["E3"] },
  { code: "metadati_ufficiali", label: "Metadati ufficiali", default_enabled: ["E4"] },
  { code: "usi_dipartimentali", label: "Usi dipartimentali", default_enabled: ["E5"] },
  { code: "linee_guida_cdl", label: "Linee guida CdL", default_enabled: ["E5"] },
  { code: "template_locale", label: "Template locale", default_enabled: ["E5"] },
  { code: "nota_presidio", label: "Nota presidio", default_enabled: ["E5"] },
];

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

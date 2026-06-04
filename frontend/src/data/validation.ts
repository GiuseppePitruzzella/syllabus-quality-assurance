/**
 * Phase 7 — read-only snapshot of the human-validation protocol
 * (Phase 5.8 of the project plan).
 *
 * SOURCES OF TRUTH (kept in sync MANUALLY — no runtime fetch):
 *   - shortlist + templates    data/human_judgment/templates/
 *   - schema                   data/human_judgment/schema.json
 *   - protocol rationale       docs/progettazione.md §3
 *   - aggregator script        backend/scripts/aggregate_human_judgment.py
 *
 * The protocol is "two-stage blind + post-hoc": the human reviewer
 * scores a syllabus first without seeing the model output (blind),
 * then re-scores the same syllabus with the model output visible
 * (post-hoc). The two passes feed different metrics — the blind
 * pass is the reference for inter-rater agreement, the post-hoc
 * pass measures the influence of the system on the human reviewer.
 */

export interface ShortlistItem {
  ordinal: number;
  syllabus: string;
}

export interface ValidationMetric {
  name: string;
  description: string;
}

export interface ValidationProtocol {
  phase: string;
  total_dataset: string;
  shortlist: ShortlistItem[];
  modes: string[];
  metrics: ValidationMetric[];
  templates_path: string;
  schema_path: string;
  aggregator_script: string;
}

export const HUMAN_VALIDATION_PROTOCOL: ValidationProtocol = {
  phase: "Phase 5.8 — Validazione umana LM-18",
  total_dataset:
    "30 syllabi LM-18 valutati dal sistema (Phase 5.7). Shortlist di 8 syllabi selezionata per il confronto uomo-macchina.",
  shortlist: [
    { ordinal: 1, syllabus: "Computer Vision Lab" },
    { ordinal: 2, syllabus: "Internet of Things" },
    { ordinal: 3, syllabus: "Peer to Peer Lab" },
    { ordinal: 4, syllabus: "Multimedia Lab" },
    { ordinal: 5, syllabus: "Computer Vision" },
    { ordinal: 6, syllabus: "Ottimizzazione" },
    { ordinal: 7, syllabus: "Deep Learning" },
    { ordinal: 8, syllabus: "Machine Learning" },
  ],
  modes: [
    "Blind: il valutatore umano assegna i punteggi C1-C9 senza vedere l'output del sistema.",
    "Post-hoc: lo stesso valutatore riassegna i punteggi vedendo l'output del sistema, per misurarne l'influenza.",
  ],
  metrics: [
    {
      name: "Cohen's κ pesata",
      description:
        "Concordanza a due fra ciascun valutatore umano e il sistema, su scala ordinale 0/1/2.",
    },
    {
      name: "Krippendorff α ordinale",
      description:
        "Concordanza inter-umana sull'intera shortlist, robusta a NA e a numero di valutatori variabile.",
    },
    {
      name: "Gwet AC2",
      description:
        "Metrica di controllo contro il paradosso della κ in presenza di distribuzioni asimmetriche.",
    },
    {
      name: "MAE sul CoreScore",
      description:
        "Errore medio assoluto sulla media C1-C9 a livello di syllabus.",
    },
    {
      name: "Correlazione di Spearman",
      description:
        "Concordanza nell'ordinamento dei syllabi per CoreScore.",
    },
    {
      name: "Matrice di confusione",
      description:
        "Distribuzione delle classi 0/1/2/NA per criterio, utile a diagnosticare drift sistematici.",
    },
  ],
  templates_path: "data/human_judgment/templates/",
  schema_path: "data/human_judgment/schema.json",
  aggregator_script: "backend/scripts/aggregate_human_judgment.py",
};

"""Prompt builder for the E4 handler (coerenza cross-lingua del syllabus).

E4 is the only extended criterion that does NOT consult external
documents. Evidence is built strictly from IT/EN paired prefixes
of the syllabus itself.

Phase 9.F.2 (e4_v2)
-------------------

The targeted_v1 campaign uncovered a structural bias in e4_v1: the
handler used to pre-filter the IT/EN payload to *only* paired
fields. Sections that existed in IT but had no EN counterpart were
invisible to the model, which had no way to penalise the
omission. The Advanced Computer Graphics case received E4=2 even
though ``course_content_en`` was empty.

e4_v2 fixes this by introducing :class:`E4FieldPartition`, a typed
four-way breakdown of the syllabus's bilingual perimeter. The
prompt receives:

  * ``paired_fields`` (both sides substantial) — the only block
    that satisfies the paired-prefix evidence rule, unchanged
    from e4_v1;
  * ``it_only_substantial`` / ``en_only_substantial`` — prefixes
    where exactly one language side carries substantial content.
    These feed the e4_v2 **threshold rule**:
       - ``len(it_only_substantial) == 0`` → max score 2;
       - ``1 ≤ len(it_only_substantial) ≤ 2`` → max score 1
         (omissioni rilevanti);
       - ``len(it_only_substantial) ≥ 3`` → max score 0
         (ampie sezioni mancanti);
       - ``len(en_only_substantial) ≥ 1`` → max score 1
         (anomalia formale).
    The thresholds are *upper bounds*, not auto-scores;
    semantic contradictions can still pull the score lower.
  * ``it_only_non_substantial`` / ``en_only_non_substantial`` —
    prefixes whose populated side is below the substantiality
    threshold (placeholders, language markers, near-empty
    strings). Visible in the prompt for audit, but they do NOT
    count toward the threshold rule.

The paired-prefix evidence rule on the response schema is
unchanged: any numeric score still requires at least one
substantial paired evidence in the judgment's ``evidences`` list.
The pre-LLM semantic NA path (no paired evidence at all) is
unchanged too.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.evaluation.agents.external_prompts.common import (
    EXTERNAL_BASE_SYSTEM_PROMPT,
    PAIRED_PREFIX_RULE,
    json_block,
    output_schema_block,
)

E4_PROMPT_VERSION = "e4_v2"


@dataclass(frozen=True)
class E4PrefixOmission:
    """A prefix whose only one language side carries substantial content.

    ``prefix`` is the canonical name without the ``_it`` / ``_en``
    suffix (e.g. ``course_content``). ``field`` is the actual
    populated field name (e.g. ``course_content_it``). ``content``
    is the substantial side's text, included so the model can verify
    the substantiality call rather than blindly trusting the
    partition.
    """

    prefix: str
    field: str
    content: str


@dataclass(frozen=True)
class E4FieldPartition:
    """Four-way breakdown of the syllabus bilingual perimeter for E4.

    The handler builds this from the Syllabus row and passes it to
    :func:`build_e4_prompt`. The dataclass is the typed contract
    between handler and prompt — adding a new bucket requires
    bumping ``E4_PROMPT_VERSION``.
    """

    # Both sides substantial. {field_name -> value} for both _it and _en.
    paired_fields: dict[str, Any]
    # IT side substantial, EN missing or non-substantial.
    it_only_substantial: tuple[E4PrefixOmission, ...]
    # EN side substantial, IT missing or non-substantial.
    en_only_substantial: tuple[E4PrefixOmission, ...]
    # Populated but not substantial. Audit-only.
    it_only_non_substantial: tuple[str, ...]
    en_only_non_substantial: tuple[str, ...]

    @property
    def paired_prefix_count(self) -> int:
        """Count of paired prefixes (one entry per matched ``_it`` side)."""
        return sum(1 for k in self.paired_fields if k.endswith("_it"))


E4_SPECIFIC_INSTRUCTIONS = """Sei il gestore del criterio E4 dell'AGENTE DI COERENZA ESTERNA (A5).

E4, "Coerenza cross-lingua": verifichi l'equivalenza semantica tra la versione italiana e la versione inglese del syllabus. La sola presenza formale di entrambe le versioni è oggetto del criterio C2, NON di E4.

A differenza degli altri criteri estesi, E4 NON consulta documenti esterni dal registry: le evidenze sono SEMPRE coppie di campi del syllabus che condividono lo stesso prefisso e differiscono solo per il suffisso `_it` / `_en` (es. `learning_outcomes_it` + `learning_outcomes_en`, oppure `course_content_it` + `course_content_en`).

PERIMETRO BILINGUE OSSERVATO (Phase 9.F.2 — e4_v2):

Oltre ai campi confrontabili, il prompt elenca esplicitamente i prefissi in cui esiste materiale sostanziale su un solo lato linguistico. Questa informazione è obbligatoria per il tuo giudizio: le sezioni esistenti in italiano e mancanti in inglese (o viceversa) rappresentano esattamente le "omissioni rilevanti" e le "sezioni mancanti" della rubrica E4. NON puoi ignorarle solo perché non hai una coppia da confrontare.

REGOLA SOGLIA (vincolante):

- Nessun prefisso in `it_only_substantial` né in `en_only_substantial` → score massimo ammissibile 2.
- 1 o 2 prefissi in `it_only_substantial` → score massimo ammissibile 1 (omissioni rilevanti).
- 3 o più prefissi in `it_only_substantial` → score massimo ammissibile 0 (ampie sezioni mancanti).
- Almeno 1 prefisso in `en_only_substantial` (anomalia formale: contenuto inglese senza versione italiana, di solito un artefatto di estrazione) → score massimo ammissibile 1; non forza da solo lo 0.

Le soglie sono **massimi ammissibili**, non punteggi automatici: contraddizioni semantiche, derive terminologiche o cambi di significato nelle coppie effettivamente confrontate possono abbassare ulteriormente il risultato.

DEFINIZIONE DI SOSTANZIALE (criterio operativo per la soglia):

Un campo conta come sostanziale solo quando contiene materiale significativo. Non lo è quando è una stringa vuota, un placeholder noto ("N/A", "-", "—", "nessuno", "non applicabile", "to be defined", marker di lingua come "Italiano" / "English"), o un testo molto breve sotto la soglia operativa (< 30 caratteri E < 5 parole). I prefissi con contenuto non sostanziale appaiono nel blocco PERIMETRO BILINGUE OSSERVATO sotto la voce ``it_only_non_substantial`` / ``en_only_non_substantial`` e NON concorrono alla soglia: sono mostrati esclusivamente per audit, così puoi verificare che il filtraggio sia corretto.

Avvertenze metodologiche:

- Equivalenza semantica significa che le due versioni veicolano la stessa informazione e gli stessi impegni didattici. Differenze stilistiche o di registro non penalizzano.
- Una traduzione automatica letterale che produce contenuti formalmente uguali ma terminologicamente impropri o ambigui in inglese va valutata come equivalenza parziale (1).
- Cambi di significato o terminologia incoerente abbassano il punteggio.
- NA E4 è semantico: si applica quando nessuna coppia sostanziale esiste. L'assenza tecnica dei campi `*_en` (parsing fallito) è gestita dal coordinator come NA tecnico PRIMA della tua chiamata: se ricevi questo prompt significa che esiste almeno una coppia IT/EN sostanziale da confrontare.
- Confronta a coppie: per ogni campo confrontato cita simultaneamente la versione IT e la versione EN, usando `source_field` con il nome esatto del campo (es. `course_content_it` e poi `course_content_en`).
"""

E4_CRITERION_SPEC: dict[str, Any] = {
    "criterion_code": "E4",
    "name": "Coerenza cross-lingua",
    "owned_by": "A5",
    "anchors": {
        "0": "Contraddizioni sostanziali, cambi di significato o ampie sezioni mancanti.",
        "1": "Equivalenza generale con omissioni o derive terminologiche rilevanti.",
        "2": "Equivalenza semantica sostanziale e terminologia coerente.",
        "NA": "Versione inglese assente o contenuto insufficiente per il confronto.",
    },
}


def build_e4_prompt(*, partition: E4FieldPartition) -> str:
    """Build the E4 prompt for one syllabus.

    No external chunks are passed — by design E4 sees only the
    syllabus's bilingual perimeter. ``partition`` is the typed
    breakdown produced by the handler's
    :func:`_partition_prefixes` so the prompt has explicit access
    to the asymmetric cases.
    """
    perimeter_view = _render_perimeter_view(partition)
    blocks = [
        EXTERNAL_BASE_SYSTEM_PROMPT.strip(),
        E4_SPECIFIC_INSTRUCTIONS.strip(),
        "SPECIFICA CRITERIO:\n" + json_block(E4_CRITERION_SPEC),
        "DATI DEL SYLLABUS DA VALUTARE (coppie IT/EN sostanziali):\n"
        + json_block(partition.paired_fields),
        "PERIMETRO BILINGUE OSSERVATO:\n" + json_block(perimeter_view),
        PAIRED_PREFIX_RULE.strip(),
        output_schema_block(
            criterion_code="E4",
            rule_block_name="REGOLA PAIRED-PREFIX",
        ).strip(),
        "Rispondi ora esclusivamente con il JSON valido richiesto.",
    ]
    return "\n\n".join(blocks)


def _render_perimeter_view(partition: E4FieldPartition) -> dict[str, Any]:
    """Project the dataclass into a JSON-serialisable dict.

    Substantial omissions carry their populated-side content so the
    model can verify the partition's call; non-substantial entries
    are reduced to the prefix name (audit visibility only).
    """
    return {
        "paired_prefixes_count": partition.paired_prefix_count,
        "it_only_substantial": [
            {"prefix": x.prefix, "field": x.field, "content": x.content}
            for x in partition.it_only_substantial
        ],
        "en_only_substantial": [
            {"prefix": x.prefix, "field": x.field, "content": x.content}
            for x in partition.en_only_substantial
        ],
        "it_only_non_substantial": list(partition.it_only_non_substantial),
        "en_only_non_substantial": list(partition.en_only_non_substantial),
    }


__all__ = [
    "E4_PROMPT_VERSION",
    "E4_CRITERION_SPEC",
    "E4FieldPartition",
    "E4PrefixOmission",
    "build_e4_prompt",
]

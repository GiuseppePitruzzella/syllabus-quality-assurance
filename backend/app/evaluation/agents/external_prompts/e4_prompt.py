"""Prompt builder for the E4 handler (coerenza cross-lingua del syllabus).

E4 è il solo criterio esteso che NON consulta documenti esterni:
le evidenze sono SEMPRE coppie di campi `*_it` / `*_en` dello stesso
syllabus. Il prompt è costruito per scoraggiare l'uso di
`source_document_id` e per richiedere la regola paired-prefix.
"""
from __future__ import annotations

from typing import Any

from app.evaluation.agents.external_prompts.common import (
    EXTERNAL_BASE_SYSTEM_PROMPT,
    PAIRED_PREFIX_RULE,
    json_block,
    output_schema_block,
)

E4_PROMPT_VERSION = "e4_v1"

E4_SPECIFIC_INSTRUCTIONS = """Sei il gestore del criterio E4 dell'AGENTE DI COERENZA ESTERNA (A5).

E4, "Coerenza cross-lingua": verifichi l'equivalenza semantica tra la versione italiana e la versione inglese del syllabus. La sola presenza formale di entrambe le versioni è oggetto del criterio C2, NON di E4.

A differenza degli altri criteri estesi, E4 NON consulta documenti esterni dal registry: le evidenze sono SEMPRE coppie di campi del syllabus che condividono lo stesso prefisso e differiscono solo per il suffisso `_it` / `_en` (es. `learning_outcomes_it` + `learning_outcomes_en`, oppure `course_content_it` + `course_content_en`).

Avvertenze metodologiche:
- Equivalenza semantica significa che le due versioni veicolano la stessa informazione e gli stessi impegni didattici. Differenze stilistiche o di registro non penalizzano.
- Una traduzione automatica letterale che produce contenuti formalmente uguali ma terminologicamente impropri o ambigui in inglese va valutata come equivalenza parziale (1).
- Cambi di significato, omissioni di intere sezioni o terminologia incoerente abbassano il punteggio.
- NA E4 è semantico: si applica quando la versione inglese è assente o quando il perimetro EN è inadeguato al confronto (es. presenti solo il titolo e poche righe).
- L'assenza tecnica dei campi `*_en` (parsing fallito) è gestita dal coordinator come NA tecnico PRIMA della tua chiamata: se ricevi questo prompt significa che esiste almeno una coppia IT/EN da confrontare.
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


def build_e4_prompt(
    *,
    syllabus_data: dict[str, Any],
) -> str:
    """Build the E4 prompt for one syllabus.

    No external chunks are passed — by design E4 sees only syllabus
    fields. The coordinator filters `syllabus_data` to the fields
    available on both languages so the LLM doesn't waste tokens on
    Italian-only sections.
    """
    blocks = [
        EXTERNAL_BASE_SYSTEM_PROMPT.strip(),
        E4_SPECIFIC_INSTRUCTIONS.strip(),
        "SPECIFICA CRITERIO:\n" + json_block(E4_CRITERION_SPEC),
        "DATI DEL SYLLABUS DA VALUTARE (campi IT/EN affiancati):\n"
        + json_block(syllabus_data),
        PAIRED_PREFIX_RULE.strip(),
        output_schema_block(
            criterion_code="E4",
            rule_block_name="REGOLA PAIRED-PREFIX",
        ).strip(),
        "Rispondi ora esclusivamente con il JSON valido richiesto.",
    ]
    return "\n\n".join(blocks)


__all__ = [
    "E4_PROMPT_VERSION",
    "E4_CRITERION_SPEC",
    "build_e4_prompt",
]

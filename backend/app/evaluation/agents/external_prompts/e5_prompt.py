"""Prompt builder for the E5 handler (aderenza agli usi dipartimentali / di CdL).

E5 supports multi-document evidence: a CdL may have several
local-usage documents (a department-level note, a CdL template, a
"presidio" comment...). The handler is expected to retrieve from
each document separately and pass all chunks to a SINGLE prompt:
the LLM produces one judgment that may cite multiple documents.
"""
from __future__ import annotations

from typing import Any

from app.evaluation.agents.external_prompts.common import (
    DUAL_SOURCE_RULE,
    EXTERNAL_BASE_SYSTEM_PROMPT,
    json_block,
    output_schema_block,
)

E5_PROMPT_VERSION = "e5_v1"

E5_SPECIFIC_INSTRUCTIONS = """Sei il gestore del criterio E5 dell'AGENTE DI COERENZA ESTERNA (A5).

E5, "Aderenza agli usi dipartimentali / di CdL": verifichi se il syllabus rispetta istruzioni operative locali esplicite fornite dal Dipartimento o dal Corso di Studio. Esempi tipici: formule standard, preferenze redazionali (es. struttura raccomandata dei prerequisiti), modelli di criteri di voto, esempi di domande tipo, organizzazione dei testi adottati, modalità di compilazione di sezioni specifiche.

I documenti esterni forniti sono uno o più documenti locali (tipi `usi_dipartimentali`, `linee_guida_cdl`, `template_locale`, `nota_presidio`). I frammenti sono filtrati per `tag_E5=True` e raggruppati per `source_document_id` — ogni gruppo corrisponde a un singolo documento locale e il suo `document_id` è esposto nel blocco JSON.

Avvertenze metodologiche:
- E5 non duplica C1–C9: valuta SOLO il rispetto di istruzioni locali esplicite e applicabili al syllabus in esame.
- "Esplicita" significa che l'indicazione locale è leggibile nei frammenti forniti; non puoi assumere usi che non risultano dal documento.
- "Applicabile" significa che l'indicazione è pertinente al syllabus: una linea guida sui prerequisiti non si applica se il documento dichiara di valere solo per gli insegnamenti del terzo anno e il syllabus è di un corso a scelta libera.
- Aderenza non implica copia letterale: la sostanza dell'indicazione locale può essere rispettata anche con formulazioni differenti.
- Se i documenti forniti non contengono indicazioni applicabili all'insegnamento (perché eccessivamente generici, o limitati ad altre tipologie di insegnamento), il giudizio diventa NA semantico con `na_reason` esplicita.
- Quando citi una evidenza dal documento esterno, valorizza SEMPRE `source_document_id` con l'ID del documento da cui hai preso la citazione (puoi citare più documenti diversi nello stesso giudizio).
"""

E5_CRITERION_SPEC: dict[str, Any] = {
    "criterion_code": "E5",
    "name": "Aderenza agli usi dipartimentali / di CdL",
    "owned_by": "A5",
    "anchors": {
        "0": "Documento locale disponibile, ma il syllabus disattende indicazioni rilevanti e applicabili.",
        "1": "Il syllabus aderisce solo parzialmente o in modo non uniforme alle indicazioni locali.",
        "2": "Il syllabus aderisce in modo sostanziale alle indicazioni locali applicabili.",
        "NA": "Documento locale assente o non abilitato, oppure indicazioni non pertinenti al syllabus.",
    },
}


def build_e5_prompt(
    *,
    syllabus_data: dict[str, Any],
    external_chunks_by_document: list[dict[str, Any]],
) -> str:
    """Build the E5 prompt for one syllabus and one or more local documents.

    Args:
        syllabus_data: Relevant syllabus fields.
        external_chunks_by_document: One entry per local document.
            Each entry has the shape
            ``{"document_id": int, "document_type": str, "chunks": [...]}``
            so the LLM keeps the document-level provenance when
            citing evidence.
    """
    blocks = [
        EXTERNAL_BASE_SYSTEM_PROMPT.strip(),
        E5_SPECIFIC_INSTRUCTIONS.strip(),
        "SPECIFICA CRITERIO:\n" + json_block(E5_CRITERION_SPEC),
        "DOCUMENTI ESTERNI — Usi dipartimentali / di CdL (uno o più documenti):\n"
        + json_block(external_chunks_by_document),
        "DATI DEL SYLLABUS DA VALUTARE:\n" + json_block(syllabus_data),
        DUAL_SOURCE_RULE.strip(),
        output_schema_block(
            criterion_code="E5",
            rule_block_name="REGOLA DUAL-SOURCE",
        ).strip(),
        "Rispondi ora esclusivamente con il JSON valido richiesto.",
    ]
    return "\n\n".join(blocks)


__all__ = [
    "E5_PROMPT_VERSION",
    "E5_CRITERION_SPEC",
    "build_e5_prompt",
]

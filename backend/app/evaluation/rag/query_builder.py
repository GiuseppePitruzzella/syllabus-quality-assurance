"""Build the retrieval query for a (criterion, agent) pair.

The retrieval query combines:

- the criterion description (what we're looking for in the corpus),
- the agent role (which lens we're applying),
- a curated subset of the syllabus fields relevant to the criterion.

Keeping the query construction in one place isolates the prompt-engineering
step from the retriever and makes it easy to A/B test alternate phrasings
without touching the ChromaDB call.

The criterion descriptions reflect the rubric in
``docs/progettazione.md`` §2.5 and the anchors used in the agent prompts
(Phase 5.3+). Edits here must stay consistent with the rubric.
"""
from __future__ import annotations

from typing import Any

# Criterion → human-readable description in Italian. The Italian wording
# matters: queries embed via gemini-embedding-001 RETRIEVAL_QUERY task,
# and the corpus is Italian, so cross-lingual queries hurt similarity.
CRITERION_DESCRIPTIONS: dict[str, str] = {
    "C1": (
        "Completezza strutturale e documentale del syllabus: presenza e "
        "compilazione sostanziale delle nove sezioni obbligatorie previste "
        "dalle Linee Guida UniCT (RA, PR, CN, MV, ED, TD, MS, MF, PRG)."
    ),
    "C2": (
        "Completezza bilingue: disponibilità della versione inglese del "
        "syllabus per il perimetro minimo (titolo, risultati di apprendimento, "
        "contenuti, modalità di verifica)."
    ),
    "C3": (
        "Formulazione dei risultati di apprendimento: chiarezza, "
        "verificabilità e specificità dei risultati di apprendimento attesi, "
        "espressi in termini di conoscenze e competenze."
    ),
    "C4": (
        "Allineamento dei risultati di apprendimento ai Descrittori di "
        "Dublino: copertura e coerenza con i cinque descrittori "
        "(conoscenza e comprensione, applicate, autonomia di giudizio, "
        "abilità comunicative, capacità di apprendimento)."
    ),
    "C5": (
        "Chiarezza dei prerequisiti: distinzione tra prerequisiti culturali "
        "e formali, gradazione di importanza (utili, importanti, "
        "indispensabili), formulazione utile allo studente."
    ),
    "C6": (
        "Modalità di verifica dell'apprendimento: chiarezza e specificità "
        "dei criteri di valutazione, esempi di domande, criteri di "
        "attribuzione del voto."
    ),
    "C7": (
        "Contenuti del corso: chiarezza, organizzazione e coerenza dei "
        "contenuti rispetto agli obiettivi formativi e ai risultati di "
        "apprendimento attesi."
    ),
    "C8": (
        "Coerenza didattico-valutativa: allineamento tra metodi didattici, "
        "modalità di verifica e risultati di apprendimento attesi."
    ),
    "C9": (
        "Cura editoriale del syllabus: refusi, coerenza interna, qualità "
        "redazionale dei riferimenti bibliografici e cura complessiva del "
        "documento."
    ),
}

# Agent → role description, used to nudge the retrieval towards the
# specific lens of the agent that will consume the chunks.
AGENT_ROLES: dict[str, str] = {
    "A1": (
        "Agente di completezza documentale: verifica presenza, completezza "
        "e chiarezza delle sezioni del syllabus."
    ),
    "A2": (
        "Agente pedagogico: valuta i risultati di apprendimento attesi e "
        "il loro allineamento ai Descrittori di Dublino."
    ),
    "A3": (
        "Agente di coerenza didattico-valutativa: valuta la relazione tra "
        "contenuti, metodi didattici e modalità di verifica."
    ),
    "A4": (
        "Agente di cura editoriale: valuta refusi, coerenza interna e "
        "qualità redazionale del syllabus."
    ),
}

# Per-criterion list of relevant syllabus fields. A field name like
# "prerequisites" expands to the IT/EN pair (prerequisites_it,
# prerequisites_en) at composition time. Empty list means "all fields".
CRITERION_FIELDS: dict[str, list[str]] = {
    "C1": [],  # presence check across all sections
    "C2": [],  # bilingual coverage requires comparing IT and EN sides
    "C3": ["dublin_knowledge", "dublin_applying", "dublin_judgement",
           "dublin_communication", "dublin_learning"],
    "C4": ["dublin_knowledge", "dublin_applying", "dublin_judgement",
           "dublin_communication", "dublin_learning"],
    "C5": ["prerequisites"],
    "C6": ["assessment_methods", "sample_questions"],
    "C7": ["course_content", "schedule", "dublin_knowledge", "dublin_applying"],
    "C8": ["assessment_methods", "teaching_methods", "dublin_knowledge",
           "dublin_applying"],
    "C9": [],  # editorial care is a global judgment
}


def build_retrieval_query(
    criterion: str,
    agent: str,
    syllabus_fields: dict[str, Any] | None = None,
    *,
    max_chars: int = 1500,
) -> str:
    """Compose the natural-language query string used to embed and retrieve.

    Args:
        criterion: Code in C1..C9 (or E1..E4 once extended criteria are
            wired in).
        agent: Code in A1..A4.
        syllabus_fields: Optional dict of syllabus fields. Only fields
            referenced by ``CRITERION_FIELDS[criterion]`` are included
            (or all of them if the list is empty).
        max_chars: Defensive cap to avoid sending an oversized query
            string to the embedding model.

    Returns:
        A query string in Italian combining the criterion description,
        the agent role, and the relevant syllabus excerpts.
    """
    if criterion not in CRITERION_DESCRIPTIONS:
        raise ValueError(f"unknown criterion: {criterion!r}")
    if agent not in AGENT_ROLES:
        raise ValueError(f"unknown agent: {agent!r}")

    parts: list[str] = [
        f"Criterio {criterion}: {CRITERION_DESCRIPTIONS[criterion]}",
        f"Ruolo {agent}: {AGENT_ROLES[agent]}",
    ]

    if syllabus_fields:
        relevant = _select_relevant_fields(criterion, syllabus_fields)
        if relevant:
            parts.append("Estratti dal syllabus rilevanti per il criterio:")
            parts.extend(f"- {key}: {_truncate(str(value), 400)}" for key, value in relevant)

    composed = "\n".join(parts)
    if len(composed) > max_chars:
        composed = composed[: max_chars - 3].rstrip() + "..."
    return composed


def _select_relevant_fields(
    criterion: str, fields: dict[str, Any]
) -> list[tuple[str, Any]]:
    """Return ``[(key, value)]`` pairs for fields relevant to ``criterion``.

    A criterion-fields entry like ``"prerequisites"`` expands to both
    ``prerequisites_it`` and ``prerequisites_en`` if either is present
    and non-empty. An empty list in ``CRITERION_FIELDS`` includes every
    non-empty field (used by C1, C2, C9).
    """
    wanted = CRITERION_FIELDS.get(criterion, [])
    out: list[tuple[str, Any]] = []
    if not wanted:
        for key, value in fields.items():
            if value:
                out.append((key, value))
        return out
    for base in wanted:
        for suffix in ("_it", "_en"):
            full = f"{base}{suffix}"
            if fields.get(full):
                out.append((full, fields[full]))
        # Some fields are not bilingual (e.g. dublin_knowledge_it without _en).
        if fields.get(base):
            out.append((base, fields[base]))
    return out


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."

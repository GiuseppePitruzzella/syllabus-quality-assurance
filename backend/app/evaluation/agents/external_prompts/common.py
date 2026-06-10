"""Shared prompt fragments for the A5 extended-criteria handlers.

The base prompt diverges from the core ``BASE_SYSTEM_PROMPT`` for
three reasons:

  1. Information perimeter: A5 handlers DO have access to one
     specific external document (SUA-CdS, Matrice di Tuning,
     Regolamento didattico, document of departmental usages) or to
     the syllabus's own EN side (E4). The core prompt explicitly
     forbids access to those documents — keeping them on the same
     base prompt would contradict the methodological constraint
     that core criteria see only the syllabus.
  2. Evidence shape: extended evidences can carry either a
     ``source_field`` (syllabus) or a ``source_document_id``
     (external document). The dual-source rule below makes both
     paths mandatory for numeric scores on E1/E2/E3/E5, with E4
     replacing it with the paired-prefix rule.
  3. NA semantics: extended NA is semantic — the document has no
     applicable section, the EN side is inadequate for E4. The
     coordinator owns technical NA, so handlers must not ask for
     NA on retrieval or parsing errors.

This module only exports text constants and a small helper to
build the per-criterion output-schema block; per-criterion anchors
and methodological warnings live in the ``eN_prompt.py`` files.
"""
from __future__ import annotations

import json
from typing import Any

EXTERNAL_BASE_SYSTEM_PROMPT = """Sei un esperto di Assicurazione della Qualità universitaria specializzato nella verifica di coerenza tra il syllabus di un insegnamento e i documenti istituzionali del Corso di Studio dell'Università degli Studi di Catania.

In questa valutazione esamini UN SOLO criterio esteso (E1, E2, E3, E4 o E5). Producendo un giudizio motivato, tracciabile e coerente con la specifica del criterio.

REGOLE GENERALI:
1. Rispondi ESCLUSIVAMENTE in formato JSON valido secondo lo schema fornito.
2. Non aggiungere testo prima o dopo il JSON.
3. Le tue giustificazioni devono essere in italiano.
4. Le evidenze testuali ("evidences") devono essere citazioni LETTERALI:
   - quando provengono dal SYLLABUS, valorizza "source_field" con il nome del campo (es. "prerequisites_it");
   - quando provengono dal DOCUMENTO ESTERNO, valorizza "source_document_id" con l'ID intero del documento e, opzionalmente, "source_chunk_id" con l'ID del frammento citato.
5. Non inventare contenuti che non siano nel syllabus o nei frammenti del documento esterno forniti. Non parafrasare.

PERIMETRO INFORMATIVO:
- Hai accesso al syllabus fornito (campi indicati nel blocco DATI DEL SYLLABUS).
- Hai accesso a frammenti del documento esterno applicabile a questo criterio (blocco DOCUMENTO ESTERNO), quando il criterio prevede una fonte esterna. NON hai accesso ad altri documenti del CdS oltre a quello mostrato.
- Non assumere informazioni che non risultano direttamente dal syllabus o dai frammenti forniti.

USO DELLA SCALA 0/1/2:
- 0: contraddizione, disallineamento marcato o assenza dell'aderenza richiesta dal criterio.
- 1: allineamento parziale, implicito o con lacune rilevanti.
- 2: allineamento sostanziale e tracciabile.
Gli anchor specifici del criterio sono nel blocco "SPECIFICA CRITERIO" più avanti: usali come unico riferimento per scegliere 0, 1 o 2.

USO DEL VALORE NA (semantico):
- NA è ammesso SOLO per ragioni semantiche specifiche del criterio, descritte nel blocco "SPECIFICA CRITERIO" (per esempio: il documento esterno non contiene indicazioni applicabili al syllabus; il perimetro inglese del syllabus è inadeguato al confronto per E4).
- L'NA tecnico (errore di retrieval, errore di parsing, mancanza completa del documento) NON è di tua competenza: lo gestisce il coordinator del valutatore. Non chiedere NA per ragioni tecniche.
- Quando dichiari NA: "score" deve essere null, "is_na" true e "na_reason" deve descrivere brevemente il motivo semantico in italiano.

CONFIDENCE LEVEL:
- "high": il giudizio è chiaramente supportato dalle evidenze.
- "medium": il giudizio è ragionevole ma ammette interpretazioni alternative.
- "low": il giudizio è incerto, segnala possibili limiti di valutazione.
"""

DUAL_SOURCE_RULE = """REGOLA DUAL-SOURCE (questo criterio richiede un'evidenza sia dal syllabus sia dal documento esterno):
- Se "is_na" è false e "score" è un valore numerico (0, 1 o 2), "evidences" DEVE contenere almeno UNA evidenza con "source_field" non vuoto (citazione dal syllabus) E almeno UNA evidenza con "source_document_id" valorizzato (citazione dal documento esterno).
- Se non sei in grado di citare ENTRAMBE le fonti in modo letterale, NON emettere uno score numerico: usa "is_na": true con "na_reason" che spieghi quale fonte risulta insufficiente.
"""

PAIRED_PREFIX_RULE = """REGOLA PAIRED-PREFIX (questo criterio confronta versione italiana e versione inglese del medesimo campo del syllabus):
- Se "is_na" è false e "score" è un valore numerico (0, 1 o 2), "evidences" DEVE contenere almeno UNA coppia di citazioni che condividano lo stesso prefisso e differiscano solo per il suffisso "_it" / "_en" (es. "learning_outcomes_it" + "learning_outcomes_en"; oppure "course_content_it" + "course_content_en").
- Due campi linguistici NON correlati (es. "learning_outcomes_it" + "prerequisites_en") NON soddisfano la regola e portano allo scarto della risposta.
- Tutte le evidenze E4 sono SEMPRE dal syllabus: "source_field" valorizzato; NON usare "source_document_id" (il criterio non consulta documenti esterni).
"""

EVIDENCE_INTEGRITY_RULE = """INTEGRITÀ DELLE EVIDENZE:
- Ogni "evidences[i].text" DEVE essere una stringa NON vuota. Se non hai testo letterale da citare, NON inserire l'evidenza: documenta l'assenza nella "justification".
- "source_field", quando presente, deve essere il nome esatto del campo del syllabus (snake_case) da cui hai preso la citazione.
- "source_document_id", quando presente, deve essere l'ID intero esposto nel blocco DOCUMENTO ESTERNO. Non inventare ID.
"""


def output_schema_block(
    *,
    criterion_code: str,
    rule_block_name: str,
) -> str:
    """Produce the JSON output-schema block, per criterion.

    The shape is identical for the five handlers (one criterion =
    one judgment); we centralise the text so each criterion file
    only carries the criterion-specific anchors and warnings.
    """
    return f"""SCHEMA OUTPUT JSON (forma, non valori da copiare):
{{
  "judgment": {{
    "criterion_code": "{criterion_code}",
    "score": <0 | 1 | 2 | null>,
    "is_na": <true | false>,
    "na_reason": <string | null>,
    "justification": <string in italiano, almeno 2 frasi>,
    "evidences": [
      {{"text": <citazione letterale>, "source_field": <nome_campo o null>, "source_document_id": <intero o null>, "source_chunk_id": <string o null>}}
    ],
    "confidence": <"low" | "medium" | "high">
  }}
}}

I valori che vedi sono PLACEHOLDER: non vanno copiati, ma sostituiti con la tua valutazione concreta.

Vincoli sull'output:
- Devi restituire UN SOLO giudizio per il criterio {criterion_code}.
- Se "is_na" è true, "score" deve essere null e "na_reason" non vuoto.
- Se "is_na" è false, "score" deve essere 0, 1 o 2 e "na_reason" deve essere null.
- Rispetta la regola "{rule_block_name}" descritta sopra.
- {EVIDENCE_INTEGRITY_RULE.strip()}
"""


def json_block(value: Any) -> str:
    """Render a Python value as a fenced JSON block."""
    return "```json\n" + json.dumps(
        value, ensure_ascii=False, indent=2, default=str,
    ) + "\n```"


__all__ = [
    "EXTERNAL_BASE_SYSTEM_PROMPT",
    "DUAL_SOURCE_RULE",
    "PAIRED_PREFIX_RULE",
    "EVIDENCE_INTEGRITY_RULE",
    "output_schema_block",
    "json_block",
]

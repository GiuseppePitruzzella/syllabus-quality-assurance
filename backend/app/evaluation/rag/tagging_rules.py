"""Apply criterion/agent tags to chunks based on a YAML rules file.

The YAML schema is documented in ``data/tagging_rules.yaml``. Match
semantics:

- A rule keyed ``R`` matches any chunk whose ``section_ref`` is exactly
  ``R`` or starts with ``R + "."`` (children and split-suffix sub-chunks).
- The most specific (longest-key) rule wins. Ties are not expected
  because longer keys imply structurally different sections.
- ``excluded_sections`` are matched with the same prefix logic and
  always strip all tags, regardless of any matching ``section_tags``
  rule (excluded wins).
- A chunk whose document has no rule, or whose section matches no rule,
  receives empty tag lists. It is still ingested but cannot be retrieved
  via criterion/agent metadata filters.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.evaluation.rag.chunker import Chunk

# Set of valid criterion/agent codes used to validate the YAML at load
# time and to fill all corresponding boolean fields on every chunk.
_CORE_CRITERIA = {"C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"}
_EXTENDED_CRITERIA = {"E1", "E2", "E3", "E4"}
_AGENTS = {"A1", "A2", "A3", "A4"}
ALL_CRITERIA = _CORE_CRITERIA | _EXTENDED_CRITERIA
ALL_AGENTS = _AGENTS


class TaggingRulesError(ValueError):
    """Raised when the rules YAML is malformed or references invalid codes."""


class TaggingRules:
    """Loaded tagging rules indexed by document_id.

    Use :meth:`from_yaml` to load rules from disk and :meth:`apply` to
    enrich a chunk's metadata with the tag fields. The loader validates
    the schema eagerly so a broken YAML fails at startup, not at first
    retrieval.
    """

    def __init__(self, raw: dict[str, Any]) -> None:
        if "documents" not in raw or not isinstance(raw["documents"], dict):
            raise TaggingRulesError("YAML must have a top-level 'documents' mapping")
        self._docs: dict[str, dict[str, Any]] = raw["documents"]
        self._validate()

    @classmethod
    def from_yaml(cls, path: Path) -> "TaggingRules":
        if not path.exists():
            raise FileNotFoundError(f"Tagging rules file not found: {path}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise TaggingRulesError("YAML root must be a mapping")
        return cls(raw)

    def _validate(self) -> None:
        """Eagerly validate every criterion/agent code used in the rules."""
        for doc_id, doc in self._docs.items():
            section_tags = doc.get("section_tags") or {}
            if not isinstance(section_tags, dict):
                raise TaggingRulesError(
                    f"{doc_id}: section_tags must be a mapping, got {type(section_tags)}"
                )
            for section_ref, rule in section_tags.items():
                if not isinstance(rule, dict):
                    raise TaggingRulesError(
                        f"{doc_id} / {section_ref!r}: rule must be a mapping"
                    )
                for code in rule.get("criterion_tags") or []:
                    if code not in ALL_CRITERIA:
                        raise TaggingRulesError(
                            f"{doc_id} / {section_ref!r}: unknown criterion '{code}'"
                        )
                for code in rule.get("agent_tags") or []:
                    if code not in ALL_AGENTS:
                        raise TaggingRulesError(
                            f"{doc_id} / {section_ref!r}: unknown agent '{code}'"
                        )

    def documents(self) -> list[str]:
        return list(self._docs.keys())

    def document_metadata(self, document_id: str) -> dict[str, Any]:
        """Return the per-document static metadata block.

        The chunker accepts this dict as ``document_metadata`` and merges
        it into every chunk's metadata. Returns an empty dict if the
        document has no entry in the YAML (callers can still ingest
        such a document; the chunks just won't have provenance tags).
        """
        doc = self._docs.get(document_id, {})
        return {
            "document_id": document_id,
            "document_title": doc.get("document_title", ""),
            "document_version": doc.get("document_version", ""),
            "source_type": doc.get("source_type", ""),
            "document_priority": int(doc.get("document_priority", 0)),
        }

    def apply(self, chunk: Chunk) -> Chunk:
        """Return a new ``Chunk`` with tag fields populated.

        Always sets ``tag_C1``...``tag_C9``, ``tag_E1``...``tag_E4`` and
        ``tag_A1``...``tag_A4`` to booleans, so downstream consumers
        (ChromaDB metadata filters) can rely on the schema.
        """
        document_id = chunk.metadata.get("document_id", "")
        section_ref = chunk.metadata.get("section_ref", "")

        criteria, agents = self._lookup(document_id, section_ref)

        new_metadata = dict(chunk.metadata)
        for code in ALL_CRITERIA:
            new_metadata[f"tag_{code}"] = code in criteria
        for code in ALL_AGENTS:
            new_metadata[f"tag_{code}"] = code in agents

        return Chunk(chunk_id=chunk.chunk_id, text=chunk.text, metadata=new_metadata)

    def _lookup(self, document_id: str, section_ref: str) -> tuple[set[str], set[str]]:
        doc = self._docs.get(document_id)
        if doc is None:
            return set(), set()

        # Excluded sections: prefix match wins regardless of section_tags.
        for excluded in doc.get("excluded_sections") or []:
            if _matches_prefix(section_ref, excluded):
                return set(), set()

        section_tags = doc.get("section_tags") or {}
        # Most-specific match (longest key) wins.
        best_key: str | None = None
        for key in section_tags:
            if _matches_prefix(section_ref, key):
                if best_key is None or len(key) > len(best_key):
                    best_key = key
        if best_key is None:
            return set(), set()

        rule = section_tags[best_key]
        criteria = set(rule.get("criterion_tags") or [])
        agents = set(rule.get("agent_tags") or [])
        return criteria, agents


def _matches_prefix(section_ref: str, key: str) -> bool:
    """Return True if ``section_ref`` is exactly ``key`` or a child of it.

    Children are sections whose ``section_ref`` extends ``key`` with a
    ``.`` separator (covers both nested H3 like ``D.CDS.1.4 -> D.CDS.1.4.1``
    and split sub-chunks like ``Allegato 1 -> Allegato 1.a``).
    """
    return section_ref == key or section_ref.startswith(key + ".")

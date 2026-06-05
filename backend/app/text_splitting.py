"""Generic text-splitting primitives shared by the corpus and the
local-document chunkers.

Phase 8.B.2 extracts these helpers out of
``app/evaluation/rag/chunker.py`` so that the new
``ExternalDocumentChunker`` can reuse the exact same paragraph /
line / sentence / hard-cut cascade without duplicating the logic.
The corpus ``MarkdownChunker`` re-imports the same names from here;
its behaviour is therefore unchanged by construction.

Everything in this module is plain-text only: no Markdown, no
section detection, no heading awareness. The corpus-specific logic
(H2 / H3 boundaries, section refs, sub-suffixes, noise merging
keyed on the alnum density of a *section*) stays in
``app/evaluation/rag/chunker.py``.
"""
from __future__ import annotations

import re

# Soft limit used as the target for paragraph-level packing.
DEFAULT_MAX_CHARS = 1500

# Hard limit. A sub-chunk that exceeds the soft limit but stays
# under the hard limit is kept whole, on the principle that
# semantic coherence beats arbitrary numeric thresholds.
DEFAULT_HARD_MAX_CHARS = 2200

# Strategy cascade for `split_long`. Each entry is
# (regex to split on, separator to rejoin with).
SPLIT_STRATEGIES: list[tuple[str, str]] = [
    (r"\n\s*\n", "\n\n"),      # paragraph
    (r"\n", "\n"),             # line (tables, bullet lists)
    (r"(?<=[.!?])\s+", " "),   # sentence
]


def alnum_len(s: str) -> int:
    """Count alphanumeric characters in ``s``.

    Used to detect noise sub-chunks composed mostly of punctuation
    or whitespace (table separators, bullet markers, ...).
    """
    return sum(1 for ch in s if ch.isalnum())


def pack_greedy(items: list[str], max_chars: int, separator: str) -> list[str]:
    """Greedily pack items into sub-chunks of at most ``max_chars`` chars.

    Items longer than ``max_chars`` are emitted as their own sub-
    chunk rather than truncated: this preserves semantic units when
    the caller's split granularity is already as fine as it can go.
    """
    sep_len = len(separator)
    out: list[str] = []
    current: list[str] = []
    current_len = 0
    for item in items:
        if not item.strip():
            continue
        item = item.strip()
        added_sep = sep_len if current else 0
        if current and current_len + added_sep + len(item) > max_chars:
            out.append(separator.join(current))
            current = [item]
            current_len = len(item)
        else:
            current.append(item)
            current_len += added_sep + len(item)
    if current:
        out.append(separator.join(current))
    return out


def split_long(body: str, max_chars: int, hard_max_chars: int) -> list[str]:
    """Split a body into sub-chunks of at most ``hard_max_chars`` characters.

    Uses a two-level threshold:

    - ``max_chars`` is the *soft* target used by :func:`pack_greedy`.
    - ``hard_max_chars`` is the recursion trigger: a sub-chunk that
      exceeds the soft target but stays under ``hard_max_chars`` is
      kept whole. Only sub-chunks past the hard limit are split with
      the next finer strategy.

    Strategy cascade (see :data:`SPLIT_STRATEGIES`):
    paragraph (``\\n\\n``) -> line (``\\n``) -> sentence -> hard cut.
    """
    if len(body) <= hard_max_chars:
        return [body]

    for pattern, separator in SPLIT_STRATEGIES:
        items = [p for p in re.split(pattern, body) if p.strip()]
        if len(items) <= 1:
            continue
        packed = pack_greedy(items, max_chars, separator=separator)
        result: list[str] = []
        for sub in packed:
            if len(sub) > hard_max_chars and sub != body:
                result.extend(split_long(sub, max_chars, hard_max_chars))
            else:
                result.append(sub)
        return result

    # Last resort: hard split at character boundaries.
    return [body[i: i + hard_max_chars] for i in range(0, len(body), hard_max_chars)]


def merge_noise_subchunks(
    sub_bodies: list[str], min_alnum: int, max_chars: int,
) -> list[str]:
    """Merge sub-chunks that are mostly punctuation/whitespace into neighbours.

    Used after :func:`split_long` to clean up artefacts like
    isolated table separators (``|``), markdown header dividers
    (``| :--- |``) or aggressive sentence splits on abbreviations.

    A merge is skipped when it would push the receiving sub-chunk
    past ``max_chars``: prevents repeated low-content fragments from
    accumulating into an oversize bag in pathological cases.
    Single-element lists are returned unchanged.
    """
    if len(sub_bodies) <= 1:
        return sub_bodies

    result: list[str] = []
    for body in sub_bodies:
        is_noise = alnum_len(body) < min_alnum
        if is_noise and result:
            candidate = result[-1] + "\n" + body
            if len(candidate) <= max_chars:
                result[-1] = candidate
                continue
            result.append(body)
        elif is_noise:
            result.append(body)
        elif result and alnum_len(result[-1]) < min_alnum:
            candidate = result[-1] + "\n" + body
            if len(candidate) <= max_chars:
                result[-1] = candidate
            else:
                result.append(body)
        else:
            result.append(body)
    return result

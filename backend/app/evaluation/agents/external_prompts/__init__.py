"""Prompt builders for the A5 ExternalConsistencyAgent (Phase 9.C.3).

One file per criterion (``e1_prompt.py``..``e5_prompt.py``) plus a
shared :mod:`common` module that holds only what is genuinely common
across the five handlers — the rubric anchors, the dual-source /
paired-prefix rules and the per-criterion methodological warnings
live in the per-criterion files.

The ``PROMPT_VERSIONS`` map is the single source of truth for what
``ExtendedAgentOutput.handler_prompt_versions`` records per run.
Bump the entry on the matching ``eN_v*`` constant when the prompt
text changes in a way that affects scoring.
"""
from app.evaluation.agents.external_prompts.e1_prompt import (
    E1_PROMPT_VERSION,
    build_e1_prompt,
)
from app.evaluation.agents.external_prompts.e2_prompt import (
    E2_PROMPT_VERSION,
    build_e2_prompt,
)
from app.evaluation.agents.external_prompts.e3_prompt import (
    E3_PROMPT_VERSION,
    build_e3_prompt,
)
from app.evaluation.agents.external_prompts.e4_prompt import (
    E4_PROMPT_VERSION,
    build_e4_prompt,
)
from app.evaluation.agents.external_prompts.e5_prompt import (
    E5_PROMPT_VERSION,
    build_e5_prompt,
)

PROMPT_VERSIONS: dict[str, str] = {
    "E1": E1_PROMPT_VERSION,
    "E2": E2_PROMPT_VERSION,
    "E3": E3_PROMPT_VERSION,
    "E4": E4_PROMPT_VERSION,
    "E5": E5_PROMPT_VERSION,
}

__all__ = [
    "build_e1_prompt",
    "build_e2_prompt",
    "build_e3_prompt",
    "build_e4_prompt",
    "build_e5_prompt",
    "E1_PROMPT_VERSION",
    "E2_PROMPT_VERSION",
    "E3_PROMPT_VERSION",
    "E4_PROMPT_VERSION",
    "E5_PROMPT_VERSION",
    "PROMPT_VERSIONS",
]

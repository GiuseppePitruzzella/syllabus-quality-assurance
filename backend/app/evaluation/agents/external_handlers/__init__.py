"""Per-criterion handlers for the A5 ExternalConsistencyAgent (Phase 9.C.3).

Each E* criterion has its own concrete handler. Handlers do NOT
inherit from the core ``BaseAgent`` because that class hardcodes
normative-corpus retrieval and a multi-criterion LLM call — both
incompatible with the A5 contract.

The shared base lives in :mod:`base`. Each concrete handler owns
its retrieval shape (single document for E1/E2/E3, none for E4,
multi-document for E5) and a single LLM call.

The coordinator in 9.C.4 dispatches resolver output to one handler
per criterion and aggregates the results.
"""
from app.evaluation.agents.external_handlers.base import (
    ExternalHandler,
    ExternalHandlerError,
    HandlerResult,
)
from app.evaluation.agents.external_handlers.e1_handler import E1Handler
from app.evaluation.agents.external_handlers.e2_handler import E2Handler
from app.evaluation.agents.external_handlers.e3_handler import E3Handler
from app.evaluation.agents.external_handlers.e4_handler import E4Handler
from app.evaluation.agents.external_handlers.e5_handler import E5Handler

__all__ = [
    "ExternalHandler",
    "ExternalHandlerError",
    "HandlerResult",
    "E1Handler",
    "E2Handler",
    "E3Handler",
    "E4Handler",
    "E5Handler",
]

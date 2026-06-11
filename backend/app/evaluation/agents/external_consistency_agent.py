"""A5 — ExternalConsistencyAgent (Phase 9.C.4).

The coordinator turns a :class:`ResolverOutput` plus a syllabus
into a single :class:`ExtendedAgentOutput`. It owns four contract
guarantees the C.3 handlers cannot enforce on their own:

  1. **Deterministic order** — judgments and retrieved chunks come
     out in ``E1, E2, E3, E4, E5`` order regardless of how the
     resolver dict was constructed.

  2. **Resolver hard-NA short-circuit** — when the resolver says a
     criterion is not applicable, the coordinator emits a *semantic*
     NA judgment (``is_na_technical=False``) directly, never calls
     the handler, never reaches the LLM. The judgment's
     ``na_reason`` is the resolver's own message so the audit
     trail stays intact.

  3. **Per-handler error isolation** — :class:`ExternalHandlerError`
     and any unexpected exception raised by one handler is recorded
     in :attr:`ExtendedAgentOutput.handler_errors` and translated
     into a *technical* NA judgment for that criterion. Other
     handlers continue to run.

  4. **Honest bookkeeping** — :attr:`handler_prompt_versions`
     contains entries only for handlers actually invoked
     (success or error); resolver hard-NA criteria never appear
     there. :attr:`retrieved_chunks` contains only chunks
     returned by successful handlers. E4 always contributes zero
     external chunks (it is syllabus-only by construction).

The coordinator itself is pure orchestration: no retrieval, no
LLM call, no SQL. It expects a :class:`ResolverOutput` produced by
:class:`ExternalDocumentResolver` and a handler bag whose keys
cover all five criteria. Caller-side wiring in C.5 supplies the
handler bag via :func:`build_default_handlers`.
"""
from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any, ClassVar, Literal

from app.evaluation.agents.external_handlers import (
    E1Handler,
    E2Handler,
    E3Handler,
    E4Handler,
    E5Handler,
    ExternalHandler,
    ExternalHandlerError,
)
from app.evaluation.agents.external_schemas import (
    ExtendedAgentOutput,
    ExtendedCriterionCode,
    ExtendedCriterionJudgment,
    ExtendedRetrievedChunkRef,
)
from app.local_documents.resolver import ResolverOutput

# Deterministic evaluation order. Exposed as a module-level
# constant so tests can pin against it without re-encoding the
# tuple.
EXTENDED_CRITERIA_ORDER: tuple[ExtendedCriterionCode, ...] = (
    "E1", "E2", "E3", "E4", "E5",
)


class ExternalConsistencyAgent:
    """A5 coordinator. Dispatches resolver verdicts to E* handlers."""

    agent_code: ClassVar[Literal["A5"]] = "A5"

    def __init__(
        self,
        handlers: Mapping[ExtendedCriterionCode, ExternalHandler],
    ) -> None:
        missing = [c for c in EXTENDED_CRITERIA_ORDER if c not in handlers]
        if missing:
            raise ValueError(
                f"ExternalConsistencyAgent requires handlers for "
                f"all of {EXTENDED_CRITERIA_ORDER}; missing: {missing}",
            )
        # Re-key in deterministic order so iteration follows the
        # contract regardless of the caller's dict order.
        self._handlers: dict[ExtendedCriterionCode, ExternalHandler] = {
            code: handlers[code] for code in EXTENDED_CRITERIA_ORDER
        }

    # ---- public API ----

    def evaluate(
        self,
        *,
        syllabus: Any,
        cdl_id: int,
        resolver_output: ResolverOutput,
    ) -> ExtendedAgentOutput:
        started = time.time()
        judgments: list[ExtendedCriterionJudgment] = []
        handler_errors: dict[str, str] = {}
        handler_prompt_versions: dict[str, str] = {}
        retrieved_chunks: list[ExtendedRetrievedChunkRef] = []
        invoked: list[str] = []
        resolver_skipped: list[str] = []

        for code in EXTENDED_CRITERIA_ORDER:
            resolution = resolver_output.by_criterion.get(code)
            handler = self._handlers[code]

            # 1. Defensive: resolver entry missing entirely. Treated
            #    as a technical issue on this criterion so the rest
            #    of the agent can still run.
            if resolution is None:
                msg = f"resolver did not report a verdict for {code}"
                handler_errors[code] = msg
                judgments.append(_technical_na_judgment(code, msg))
                continue

            # 2. Resolver hard-NA: short-circuit. Semantic NA, no
            #    handler invocation, no prompt_version, no chunks.
            if not resolution.applicable:
                judgments.append(
                    _resolver_na_judgment(code, resolution.na_reason or ""),
                )
                resolver_skipped.append(code)
                continue

            # 3. Applicable. Invoke the handler.
            document_ids = [d.local_document_id for d in resolution.documents]
            try:
                result = handler.evaluate(
                    syllabus=syllabus,
                    cdl_id=cdl_id,
                    document_ids=document_ids,
                )
            except ExternalHandlerError as exc:
                handler_errors[code] = str(exc)
                handler_prompt_versions[code] = handler.prompt_version
                invoked.append(code)
                judgments.append(_technical_na_judgment(code, str(exc)))
                continue
            except Exception as exc:  # noqa: BLE001 — handler isolation
                # Handler raised something unexpected (KeyError,
                # AttributeError, ...). We trap it so the other
                # handlers still run; the message is preserved for
                # post-mortem in handler_errors.
                handler_errors[code] = f"unexpected error: {exc}"
                handler_prompt_versions[code] = handler.prompt_version
                invoked.append(code)
                judgments.append(_technical_na_judgment(code, str(exc)))
                continue

            judgments.append(result.judgment)
            handler_prompt_versions[code] = result.prompt_version
            invoked.append(code)
            retrieved_chunks.extend(result.retrieved_chunks)

        return ExtendedAgentOutput(
            agent_code="A5",
            judgments=judgments,
            handler_prompt_versions=handler_prompt_versions,
            handler_errors=handler_errors,
            execution_metadata={
                "latency_ms": int((time.time() - started) * 1000),
                "handlers_invoked": invoked,
                "resolver_skipped": resolver_skipped,
            },
            retrieved_chunks=retrieved_chunks,
        )


# ---------------------------------------------------------------------------
# Helpers for orchestrator wiring (C.5 will use these)
# ---------------------------------------------------------------------------


def build_default_handlers(
    *,
    llm_client: Any,
    external_retriever: Any,
) -> dict[ExtendedCriterionCode, ExternalHandler]:
    """Return one handler per criterion, wired with shared LLM client
    and external retriever (the retriever is unused by E4)."""
    return {
        "E1": E1Handler(llm_client=llm_client, external_retriever=external_retriever),
        "E2": E2Handler(llm_client=llm_client, external_retriever=external_retriever),
        "E3": E3Handler(llm_client=llm_client, external_retriever=external_retriever),
        "E4": E4Handler(llm_client=llm_client),
        "E5": E5Handler(llm_client=llm_client, external_retriever=external_retriever),
    }


def resolver_na_map(resolver_output: ResolverOutput) -> dict[str, str]:
    """Extract the ``{code: na_reason}`` map the aggregator expects.

    The orchestrator passes this map alongside the coordinator's
    :class:`ExtendedAgentOutput` to ``aggregate_extended``. Kept
    here so both producer and consumer share one extraction rule.
    """
    out: dict[str, str] = {}
    for code, resolution in resolver_output.by_criterion.items():
        if not resolution.applicable:
            out[code] = resolution.na_reason or "criterion not applicable"
    return out


# ---------------------------------------------------------------------------
# Judgment factories
# ---------------------------------------------------------------------------


def _resolver_na_judgment(
    code: ExtendedCriterionCode, na_reason: str,
) -> ExtendedCriterionJudgment:
    """Semantic NA judgment for a resolver-skipped criterion.

    The ``na_reason`` is the resolver's own message (typically:
    "no indexed document enabled for E1 on cdl_id=3"). We pass it
    through verbatim so the report can attribute the NA to a real
    cause rather than a generic "not applicable".
    """
    reason = na_reason.strip() or "criterio non applicabile"
    return ExtendedCriterionJudgment(
        criterion_code=code,
        score=None,
        is_na=True,
        is_na_technical=False,
        na_reason=reason,
        justification=(
            f"Il criterio {code} è dichiarato non applicabile dal resolver dei "
            f"documenti esterni: {reason}. Nessun handler dell'A5 è stato "
            f"invocato per questo criterio."
        ),
        evidences=[],
        confidence="high",
    )


def _technical_na_judgment(
    code: ExtendedCriterionCode, error_message: str,
) -> ExtendedCriterionJudgment:
    """Technical NA judgment for a criterion whose handler errored.

    The handler's exception message is preserved on ``na_reason``
    so the report can show the underlying cause; the coordinator
    additionally stores the same message in
    :attr:`ExtendedAgentOutput.handler_errors` for the aggregator
    to count toward the ``partial`` / ``failed`` status logic.
    """
    msg = error_message.strip() or "errore tecnico non specificato"
    return ExtendedCriterionJudgment(
        criterion_code=code,
        score=None,
        is_na=True,
        is_na_technical=True,
        na_reason=f"errore tecnico: {msg}",
        justification=(
            f"L'handler del criterio {code} non è stato in grado di produrre "
            f"un giudizio valido. L'errore è registrato per consentire un'analisi "
            f"successiva; il criterio è marcato NA tecnico così gli altri handler "
            f"hanno potuto completare la valutazione."
        ),
        evidences=[],
        confidence="low",
    )


__all__ = [
    "ExternalConsistencyAgent",
    "EXTENDED_CRITERIA_ORDER",
    "build_default_handlers",
    "resolver_na_map",
]

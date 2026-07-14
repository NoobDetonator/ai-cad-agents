from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterator
from uuid import UUID, uuid4


class CadTransactionOutcome(StrEnum):
    COMMITTED = "committed"
    ABORTED = "aborted"
    UNDONE = "undone"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class CadTransactionTrace:
    transaction_id: str
    action_id: UUID
    call_id: str
    label: str | None = None
    outcome: CadTransactionOutcome = CadTransactionOutcome.UNKNOWN


_CURRENT_TRACE: ContextVar[CadTransactionTrace | None] = ContextVar(
    "aicad_current_transaction_trace",
    default=None,
)


@contextmanager
def transaction_trace(
    action_id: UUID,
    call_id: str,
) -> Iterator[CadTransactionTrace]:
    trace = CadTransactionTrace(
        transaction_id=f"tx-{uuid4().hex}",
        action_id=action_id,
        call_id=call_id,
    )
    token = _CURRENT_TRACE.set(trace)
    try:
        yield trace
    finally:
        _CURRENT_TRACE.reset(token)


def current_transaction_trace() -> CadTransactionTrace | None:
    return _CURRENT_TRACE.get()


def transaction_title(title: str) -> str:
    trace = current_transaction_trace()
    if trace is None:
        return f"AI CAD: {title}"
    trace.label = f"AI CAD [{trace.transaction_id}]: {title}"
    return trace.label


def mark_transaction(outcome: CadTransactionOutcome) -> None:
    trace = current_transaction_trace()
    if trace is not None:
        trace.outcome = outcome


def mark_undone_transaction(
    transaction_id: str,
    label: str,
) -> None:
    trace = current_transaction_trace()
    if trace is None:
        return
    trace.transaction_id = transaction_id
    trace.label = label
    trace.outcome = CadTransactionOutcome.UNDONE

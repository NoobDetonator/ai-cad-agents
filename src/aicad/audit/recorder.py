from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from threading import RLock
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

from aicad.audit.models import (
    AuditActionKind,
    AuditActionRecord,
    AuditActionStatus,
    AuditApprovalDecision,
    AuditApprovalRecord,
    AuditPlanRecord,
    AuditSource,
    AuditToolCallRecord,
    AuditTransactionRecord,
    AuditValidationRecord,
)
from aicad.audit.store import AuditStore


class AuditRecorder:
    """Create and advance audit action snapshots for one local session."""

    def __init__(
        self,
        store: AuditStore,
        *,
        session_id: UUID | None = None,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] = perf_counter,
    ) -> None:
        self._store = store
        self._session_id = session_id or uuid4()
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic
        self._started: dict[UUID, float] = {}
        self._lock = RLock()

    @property
    def session_id(self) -> UUID:
        return self._session_id

    def start_action(
        self,
        *,
        source: AuditSource,
        kind: AuditActionKind,
        tool_calls: tuple[AuditToolCallRecord, ...] = (),
        plan: AuditPlanRecord | None = None,
        original_request: str | None = None,
        intention: str | None = None,
        assumptions: tuple[str, ...] = (),
        approval_decision: AuditApprovalDecision = AuditApprovalDecision.PENDING,
        action_id: UUID | None = None,
        parent_action_id: UUID | None = None,
        sensitive_values: tuple[str, ...] = (),
    ) -> AuditActionRecord:
        identifier = action_id or uuid4()
        started_at = self._checked_now()
        approval = AuditApprovalRecord(
            decision=approval_decision,
            decided_at=(
                started_at
                if approval_decision is not AuditApprovalDecision.PENDING
                else None
            ),
            source=(
                "policy"
                if approval_decision is AuditApprovalDecision.NOT_REQUIRED
                else None
            ),
        )
        record = AuditActionRecord(
            session_id=self._session_id,
            action_id=identifier,
            parent_action_id=parent_action_id,
            source=source,
            kind=kind,
            started_at=started_at,
            original_request=original_request,
            intention=intention,
            assumptions=assumptions,
            plan=plan,
            tool_calls=tool_calls,
            approval=approval,
        )
        saved = self._store.save(record, sensitive_values=sensitive_values)
        with self._lock:
            self._started[identifier] = self._monotonic()
        return saved

    def record_approval(
        self,
        record: AuditActionRecord,
        *,
        decision: AuditApprovalDecision,
        source: str,
        grant_id: UUID | None = None,
        sensitive_values: tuple[str, ...] = (),
    ) -> AuditActionRecord:
        self._validate_session(record)
        if record.status is not AuditActionStatus.PENDING:
            raise ValueError("A terminal audit action cannot receive an approval.")
        if record.approval.decision is not AuditApprovalDecision.PENDING:
            raise ValueError("An audit approval decision cannot be replaced.")
        approval = AuditApprovalRecord(
            decision=decision,
            decided_at=self._checked_now(),
            source=source,
            grant_id=grant_id,
        )
        updated = record.model_copy(
            update={"revision": record.revision + 1, "approval": approval}
        )
        return self._store.save(updated, sensitive_values=sensitive_values)

    def finish_action(
        self,
        record: AuditActionRecord,
        *,
        status: AuditActionStatus,
        result: Any = None,
        error_code: str | None = None,
        validations: tuple[AuditValidationRecord, ...] = (),
        transactions: tuple[AuditTransactionRecord, ...] = (),
        duration_ms: int | None = None,
        sensitive_values: tuple[str, ...] = (),
    ) -> AuditActionRecord:
        self._validate_session(record)
        if status is AuditActionStatus.PENDING:
            raise ValueError("Finishing an audit action requires a terminal status.")
        if record.status is not AuditActionStatus.PENDING:
            raise ValueError("The audit action is already terminal.")
        with self._lock:
            started = self._started.get(record.action_id)
        measured_duration = duration_ms
        if measured_duration is None:
            if started is None:
                raise ValueError("Duration is required after recorder restart.")
            measured_duration = max(0, round((self._monotonic() - started) * 1_000))
        updated = record.model_copy(
            update={
                "revision": record.revision + 1,
                "finished_at": self._checked_now(),
                "status": status,
                "result": result,
                "error_code": error_code,
                "duration_ms": measured_duration,
                "validations": validations,
                "transactions": transactions,
            }
        )
        checked = AuditActionRecord.model_validate(updated.model_dump(mode="json"))
        saved = self._store.save(checked, sensitive_values=sensitive_values)
        with self._lock:
            self._started.pop(record.action_id, None)
        return saved

    def _validate_session(self, record: AuditActionRecord) -> None:
        if record.session_id != self._session_id:
            raise ValueError("The audit action belongs to another recorder session.")

    def _checked_now(self) -> datetime:
        value = self._now()
        if value.utcoffset() is None:
            raise ValueError("The audit clock must return a timezone-aware value.")
        return value

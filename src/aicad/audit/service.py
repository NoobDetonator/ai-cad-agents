from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from threading import RLock
from typing import Any, Iterator
from uuid import UUID, uuid4

from aicad.audit.models import (
    AUDIT_SCHEMA_VERSION,
    AuditActionKind,
    AuditActionRecord,
    AuditActionStatus,
    AuditApprovalDecision,
    AuditPlanRecord,
    AuditSource,
    AuditToolCallRecord,
    AuditTransactionOutcome,
    AuditTransactionRecord,
    AuditValidationRecord,
    AuditValidationStatus,
)
from aicad.audit.recorder import AuditRecorder
from aicad.audit.store import AuditStore, default_audit_store
from aicad.core.tool_registry import (
    ToolConfirmationRequired,
    ToolInputError,
    ToolRegistry,
    ToolRisk,
)
from aicad.core.transactions import (
    CadTransactionOutcome,
    CadTransactionTrace,
    transaction_trace,
)


_ACTIVE_ACTION_ID: ContextVar[UUID | None] = ContextVar(
    "aicad_active_audit_action",
    default=None,
)


class AuditService:
    """Shared lifecycle service used by chat, plans, and the GUI bridge."""

    def __init__(
        self,
        store: AuditStore | None = None,
        *,
        session_id: UUID | None = None,
        recorder: AuditRecorder | None = None,
    ) -> None:
        checked_store = store or default_audit_store()
        self._recorder = recorder or AuditRecorder(
            checked_store,
            session_id=session_id,
        )
        self._store = checked_store
        self._records: dict[UUID, AuditActionRecord] = {}
        self._execution_calls: dict[UUID, AuditToolCallRecord] = {}
        self._plan_actions: dict[UUID, UUID] = {}
        self._plan_traces: dict[UUID, list[CadTransactionTrace]] = {}
        self._lock = RLock()

    @property
    def session_id(self) -> UUID:
        return self._recorder.session_id

    @property
    def store(self) -> AuditStore:
        return self._store

    def begin_tool(
        self,
        registry: ToolRegistry,
        tool_name: str,
        arguments: Mapping[str, Any] | None,
        *,
        source: AuditSource,
        original_request: str | None,
        intention: str | None = None,
        assumptions: tuple[str, ...] = (),
        call_id: str | None = None,
        action_id: UUID | None = None,
        parent_action_id: UUID | None = None,
    ) -> UUID:
        checked_arguments = registry.validate_arguments(tool_name, arguments)
        spec = registry.get_spec(tool_name)
        identifier = action_id or uuid4()
        execution_call = AuditToolCallRecord(
            call_id=call_id or f"call-{identifier.hex}",
            tool_name=tool_name,
            arguments=checked_arguments,
            risk=spec.risk,
            expected_validations=(
                "registry.arguments",
                "handler.completed",
            ),
        )
        record = self._recorder.start_action(
            source=source,
            kind=AuditActionKind.TOOL,
            original_request=original_request,
            intention=intention or f"Executar {tool_name}.",
            assumptions=assumptions,
            tool_calls=(execution_call,),
            approval_decision=(
                AuditApprovalDecision.NOT_REQUIRED
                if spec.risk is ToolRisk.READ
                else AuditApprovalDecision.PENDING
            ),
            action_id=identifier,
            parent_action_id=parent_action_id,
        )
        with self._lock:
            self._records[identifier] = record
            self._execution_calls[identifier] = execution_call
        return identifier

    def approve(
        self,
        action_id: UUID,
        *,
        automatic: bool,
        source: str,
        grant_id: UUID | None = None,
    ) -> AuditActionRecord:
        record = self._record(action_id)
        decision = (
            AuditApprovalDecision.APPROVED_AUTOMATIC
            if automatic
            else AuditApprovalDecision.APPROVED_MANUAL
        )
        if record.approval.decision is decision:
            return record
        if record.approval.decision is not AuditApprovalDecision.PENDING:
            raise ValueError("The audited approval decision is already final.")
        updated = self._recorder.record_approval(
            record,
            decision=decision,
            source=source,
            grant_id=grant_id,
        )
        self._replace(updated)
        return updated

    def cancel(
        self,
        action_id: UUID,
        *,
        source: str,
        denied: bool = False,
        error_code: str = "cancelled",
    ) -> AuditActionRecord:
        record = self._record(action_id)
        if record.status is not AuditActionStatus.PENDING:
            return record
        if record.approval.decision is AuditApprovalDecision.PENDING:
            record = self._recorder.record_approval(
                record,
                decision=(
                    AuditApprovalDecision.DENIED
                    if denied
                    else AuditApprovalDecision.CANCELLED
                ),
                source=source,
            )
        finished = self._recorder.finish_action(
            record,
            status=AuditActionStatus.CANCELLED,
            error_code=error_code,
        )
        self._replace(finished)
        with self._lock:
            self._execution_calls.pop(action_id, None)
        return finished

    def execute_tool(
        self,
        action_id: UUID,
        registry: ToolRegistry,
    ) -> Any:
        record = self._record(action_id)
        if record.status is not AuditActionStatus.PENDING:
            raise ValueError("The audited tool action is already terminal.")
        with self._lock:
            call = self._execution_calls.get(action_id, record.tool_calls[0])
        if call.risk is not ToolRisk.READ and record.approval.decision not in {
            AuditApprovalDecision.APPROVED_MANUAL,
            AuditApprovalDecision.APPROVED_AUTOMATIC,
        }:
            raise PermissionError("The audited tool action has not been approved.")
        confirmed = call.risk is not ToolRisk.READ
        token = _ACTIVE_ACTION_ID.set(action_id)
        try:
            with transaction_trace(action_id, call.call_id) as trace:
                try:
                    result = registry.execute(
                        call.tool_name,
                        call.arguments,
                        confirmed=confirmed,
                    )
                except Exception as exc:
                    self._finish_tool_failure(record, trace, exc)
                    raise
            validations = self._success_validations(result)
            finished = self._recorder.finish_action(
                record,
                status=AuditActionStatus.COMPLETED,
                result=result,
                validations=validations,
                transactions=self._transaction_records((trace,)),
            )
            self._replace(finished)
            with self._lock:
                self._execution_calls.pop(action_id, None)
            if call.tool_name == "cad.export_audit_history" and isinstance(
                result, Mapping
            ):
                destination = result.get("destination")
                if isinstance(destination, str):
                    self._store.export_session(
                        self.session_id,
                        destination,
                        overwrite=True,
                    )
            return result
        finally:
            _ACTIVE_ACTION_ID.reset(token)

    def run_tool(
        self,
        registry: ToolRegistry,
        tool_name: str,
        arguments: Mapping[str, Any] | None,
        *,
        source: AuditSource,
        original_request: str | None,
        intention: str | None = None,
        assumptions: tuple[str, ...] = (),
        parent_action_id: UUID | None = None,
    ) -> Any:
        action_id = self.begin_tool(
            registry,
            tool_name,
            arguments,
            source=source,
            original_request=original_request,
            intention=intention,
            assumptions=assumptions,
            parent_action_id=parent_action_id,
        )
        return self.execute_tool(action_id, registry)

    def begin_plan(
        self,
        plan: Any,
        registry: ToolRegistry,
        *,
        source: AuditSource,
        original_request: str | None,
        parent_action_id: UUID | None = None,
    ) -> UUID:
        plan_id = UUID(str(plan.plan_id))
        with self._lock:
            existing = self._plan_actions.get(plan_id)
            if existing is not None:
                return existing
        plan_calls = getattr(plan, "calls", None)
        if plan_calls is None:
            plan_calls = (plan.call,)
        calls = tuple(
            AuditToolCallRecord(
                call_id=call.call_id,
                tool_name=call.name,
                arguments=registry.validate_arguments(call.name, call.arguments),
                risk=registry.get_spec(call.name).risk,
                expected_validations=tuple(call.expected_validations),
            )
            for call in plan_calls
        )
        action_id = uuid4()
        record = self._recorder.start_action(
            source=source,
            kind=AuditActionKind.PLAN,
            original_request=original_request,
            intention=plan.intention,
            assumptions=tuple(plan.assumptions),
            plan=AuditPlanRecord(
                contract_version=plan.contract_version,
                plan_id=plan_id,
                plan_hash=plan.plan_hash,
                base_state_token=plan.base_state_token.model_dump(mode="json"),
                steps=tuple(plan.steps),
            ),
            tool_calls=calls,
            approval_decision=AuditApprovalDecision.PENDING,
            action_id=action_id,
            parent_action_id=parent_action_id,
        )
        with self._lock:
            self._records[action_id] = record
            self._plan_actions[plan_id] = action_id
            self._plan_traces[plan_id] = []
        return action_id

    def approve_plan(
        self,
        plan_id: UUID,
        *,
        automatic: bool,
        source: str,
        grant_id: UUID | None,
    ) -> AuditActionRecord:
        return self.approve(
            self._plan_action_id(plan_id),
            automatic=automatic,
            source=source,
            grant_id=grant_id,
        )

    def cancel_plan(
        self,
        plan_id: UUID,
        *,
        source: str,
        denied: bool = False,
        error_code: str = "cancelled",
    ) -> AuditActionRecord:
        return self.cancel(
            self._plan_action_id(plan_id),
            source=source,
            denied=denied,
            error_code=error_code,
        )

    @contextmanager
    def plan_call_scope(self, plan_id: UUID, call_id: str) -> Iterator[None]:
        action_id = self._plan_action_id(plan_id)
        with transaction_trace(action_id, call_id) as trace:
            try:
                yield
            finally:
                if trace.label is not None:
                    with self._lock:
                        self._plan_traces[plan_id].append(trace)

    def finish_plan_success(self, plan_id: UUID, result: Any) -> AuditActionRecord:
        record = self._record(self._plan_action_id(plan_id))
        results = getattr(result, "results", None)
        if results is None:
            results = (result.tool_result,)
        validation_payloads = getattr(result, "validation_results", None)
        if validation_payloads is None:
            validation_payloads = (result.validation_result,)
        validations = tuple(
            AuditValidationRecord(
                name=f"{record.tool_calls[index].call_id}:document.valid",
                status=(
                    AuditValidationStatus.PASSED
                    if payload.get("valid") is True
                    else AuditValidationStatus.FAILED
                ),
                details=dict(payload),
            )
            for index, payload in enumerate(validation_payloads)
        )
        finished = self._recorder.finish_action(
            record,
            status=AuditActionStatus.COMPLETED,
            result={
                "plan_id": str(plan_id),
                "results": list(results),
            },
            validations=validations,
            transactions=self._plan_transaction_records(plan_id),
        )
        self._replace(finished)
        with self._lock:
            self._execution_calls.pop(record.action_id, None)
        return finished

    def finish_plan_failure(
        self,
        plan_id: UUID,
        *,
        status: AuditActionStatus,
        error_code: str,
    ) -> AuditActionRecord:
        record = self._record(self._plan_action_id(plan_id))
        if record.status is not AuditActionStatus.PENDING:
            return record
        finished = self._recorder.finish_action(
            record,
            status=status,
            error_code=error_code,
            validations=(
                AuditValidationRecord(
                    name="plan.completed",
                    status=AuditValidationStatus.FAILED,
                    details={"error_code": error_code},
                ),
            ),
            transactions=self._plan_transaction_records(plan_id),
        )
        self._replace(finished)
        return finished

    def begin_turn(
        self,
        *,
        source: AuditSource,
        original_request: str,
    ) -> UUID:
        action_id = uuid4()
        record = self._recorder.start_action(
            source=source,
            kind=AuditActionKind.TURN,
            original_request=original_request,
            intention="Interpretar o pedido e preparar uma resposta segura.",
            approval_decision=AuditApprovalDecision.NOT_REQUIRED,
            action_id=action_id,
        )
        with self._lock:
            self._records[action_id] = record
        return action_id

    def finish_turn(
        self,
        action_id: UUID,
        *,
        status: AuditActionStatus,
        intention: str | None = None,
        assumptions: tuple[str, ...] = (),
        result: Any = None,
        error_code: str | None = None,
    ) -> AuditActionRecord:
        record = self._record(action_id).model_copy(
            update={
                "intention": intention or self._record(action_id).intention,
                "assumptions": assumptions,
            }
        )
        finished = self._recorder.finish_action(
            record,
            status=status,
            result=result,
            error_code=error_code,
        )
        self._replace(finished)
        return finished

    def get_history(self, limit: int = 20) -> dict[str, Any]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("The audit history limit must be between 1 and 100.")
        active = _ACTIVE_ACTION_ID.get()
        records = [
            record
            for record in self._store.list_records(self.session_id)
            if record.action_id != active
        ][-limit:]
        return {
            "schema_version": AUDIT_SCHEMA_VERSION,
            "session_id": str(self.session_id),
            "count": len(records),
            "actions": [self._summary(record) for record in records],
        }

    def export_history(
        self,
        destination: str,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        path = Path(destination)
        if not path.is_absolute():
            raise ValueError("The audit export destination must be absolute.")
        exported = self._store.export_session(
            self.session_id,
            path,
            overwrite=overwrite,
        )
        return {
            "destination": str(exported),
            "session_id": str(self.session_id),
            "record_count": len(self._store.list_records(self.session_id)),
            "valid": True,
        }

    def _finish_tool_failure(
        self,
        record: AuditActionRecord,
        trace: CadTransactionTrace,
        error: Exception,
    ) -> None:
        code = self._error_code(error)
        finished = self._recorder.finish_action(
            record,
            status=AuditActionStatus.FAILED,
            error_code=code,
            validations=(
                AuditValidationRecord(
                    name="handler.completed",
                    status=AuditValidationStatus.FAILED,
                    details={"error_code": code},
                ),
            ),
            transactions=self._transaction_records((trace,)),
        )
        self._replace(finished)
        with self._lock:
            self._execution_calls.pop(record.action_id, None)

    @staticmethod
    def _success_validations(result: Any) -> tuple[AuditValidationRecord, ...]:
        validations = [
            AuditValidationRecord(
                name="registry.arguments",
                status=AuditValidationStatus.PASSED,
            ),
            AuditValidationRecord(
                name="handler.completed",
                status=AuditValidationStatus.PASSED,
            ),
        ]
        if isinstance(result, Mapping) and isinstance(result.get("valid"), bool):
            validations.append(
                AuditValidationRecord(
                    name="result.valid",
                    status=(
                        AuditValidationStatus.PASSED
                        if result["valid"]
                        else AuditValidationStatus.FAILED
                    ),
                    details={"valid": result["valid"]},
                )
            )
        return tuple(validations)

    def _plan_transaction_records(
        self,
        plan_id: UUID,
    ) -> tuple[AuditTransactionRecord, ...]:
        with self._lock:
            traces = tuple(self._plan_traces.get(plan_id, ()))
        return self._transaction_records(traces)

    @staticmethod
    def _transaction_records(
        traces: tuple[CadTransactionTrace, ...],
    ) -> tuple[AuditTransactionRecord, ...]:
        outcomes = {
            CadTransactionOutcome.COMMITTED: AuditTransactionOutcome.COMMITTED,
            CadTransactionOutcome.ABORTED: AuditTransactionOutcome.ABORTED,
            CadTransactionOutcome.UNDONE: AuditTransactionOutcome.UNDONE,
            CadTransactionOutcome.UNKNOWN: AuditTransactionOutcome.UNKNOWN,
        }
        return tuple(
            AuditTransactionRecord(
                transaction_id=trace.transaction_id,
                call_id=trace.call_id,
                sequence=index,
                label=trace.label,
                outcome=outcomes[trace.outcome],
            )
            for index, trace in enumerate(
                (item for item in traces if item.label is not None),
                start=1,
            )
        )

    def _record(self, action_id: UUID) -> AuditActionRecord:
        with self._lock:
            record = self._records.get(action_id)
        if record is None:
            record = self._store.load(self.session_id, action_id)
            with self._lock:
                self._records[action_id] = record
        return record

    def _replace(self, record: AuditActionRecord) -> None:
        with self._lock:
            self._records[record.action_id] = record

    def _plan_action_id(self, plan_id: UUID) -> UUID:
        with self._lock:
            action_id = self._plan_actions.get(plan_id)
        if action_id is None:
            raise KeyError("The audit plan is unknown in this session.")
        return action_id

    @staticmethod
    def _error_code(error: Exception) -> str:
        if isinstance(error, ToolInputError):
            return "invalid_arguments"
        if isinstance(error, ToolConfirmationRequired):
            return "confirmation_required"
        if isinstance(error, PermissionError):
            return "permission_denied"
        if isinstance(error, KeyError):
            return "unknown_tool"
        return "execution_failed"

    @staticmethod
    def _summary(record: AuditActionRecord) -> dict[str, Any]:
        return {
            "action_id": str(record.action_id),
            "parent_action_id": (
                str(record.parent_action_id)
                if record.parent_action_id is not None
                else None
            ),
            "started_at": record.started_at.isoformat(),
            "source": record.source.value,
            "kind": record.kind.value,
            "status": record.status.value,
            "intention": record.intention,
            "tool_names": [call.tool_name for call in record.tool_calls],
            "approval": record.approval.decision.value,
            "duration_ms": record.duration_ms,
            "error_code": record.error_code,
        }

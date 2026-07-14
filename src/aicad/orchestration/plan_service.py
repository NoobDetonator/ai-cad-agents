from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager, nullcontext
from enum import StrEnum
import hashlib
import json
from threading import RLock
from time import perf_counter
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from aicad.core.context import DocumentStateToken
from aicad.core.tool_registry import ToolRegistry, ToolRisk
from aicad.orchestration.models import OrchestrationPlan
from aicad.orchestration.plans import (
    DEFAULT_APPROVAL_TTL_SECONDS,
    PlanApprovalError,
    PlanExecutionError,
    PlanHash,
    StalePlanError,
    ValidatedPlanCall,
)


COMPOSITE_PLAN_CONTRACT_VERSION = "1.0"
MAX_COMPOSITE_CALLS = 8


class CompositePlanError(RuntimeError):
    """A composite plan could not complete atomically by compensation."""


class CompositeRollbackError(CompositePlanError):
    """Rollback ran but the baseline could not be verified."""


class CompositePlanStatus(StrEnum):
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"
    FAILED = "failed"


class CompositeValidatedPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal[COMPOSITE_PLAN_CONTRACT_VERSION] = (
        COMPOSITE_PLAN_CONTRACT_VERSION
    )
    plan_id: UUID
    base_state_token: DocumentStateToken
    intention: str = Field(min_length=1, max_length=500)
    assumptions: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    steps: tuple[str, ...] = Field(min_length=1, max_length=32)
    calls: tuple[ValidatedPlanCall, ...] = Field(
        min_length=2,
        max_length=MAX_COMPOSITE_CALLS,
    )
    plan_hash: PlanHash

    @model_validator(mode="after")
    def validate_plan(self) -> CompositeValidatedPlan:
        ids = [call.call_id for call in self.calls]
        if len(ids) != len(set(ids)):
            raise ValueError("Composite plan call IDs must be unique.")
        if self.plan_hash != self.calculate_hash(self.model_dump(mode="json")):
            raise ValueError("The composite plan hash is invalid.")
        return self

    @classmethod
    def build(
        cls,
        plan: OrchestrationPlan,
        base_state_token: DocumentStateToken,
        registry: ToolRegistry,
        *,
        plan_id: UUID | None = None,
    ) -> CompositeValidatedPlan:
        if base_state_token.document_id is None:
            raise ValueError("Composite plans require an active baseline document.")
        if not 2 <= len(plan.tool_calls) <= MAX_COMPOSITE_CALLS:
            raise ValueError("A composite plan requires between two and eight calls.")
        calls: list[ValidatedPlanCall] = []
        for proposed in plan.tool_calls:
            spec = registry.get_spec(proposed.name)
            if proposed.name == "cad.undo":
                raise ValueError("Undo cannot be a compensatable composite step.")
            if spec.risk is not ToolRisk.MODIFY or proposed.risk is not ToolRisk.MODIFY:
                raise ValueError("Every composite step must be a registered mutation.")
            calls.append(
                ValidatedPlanCall(
                    call_id=proposed.call_id,
                    name=proposed.name,
                    arguments=registry.validate_arguments(
                        proposed.name,
                        proposed.arguments,
                    ),
                    risk=ToolRisk.MODIFY,
                )
            )
        payload: dict[str, Any] = {
            "contract_version": COMPOSITE_PLAN_CONTRACT_VERSION,
            "plan_id": str(plan_id or uuid4()),
            "base_state_token": base_state_token.model_dump(mode="json"),
            "intention": plan.intention,
            "assumptions": list(plan.assumptions),
            "steps": list(plan.steps),
            "calls": [call.model_dump(mode="json") for call in calls],
        }
        payload["plan_hash"] = cls.calculate_hash(payload)
        return cls.model_validate(payload)

    @staticmethod
    def calculate_hash(payload: Mapping[str, Any]) -> str:
        checked = dict(payload)
        checked.pop("plan_hash", None)
        encoded = json.dumps(
            checked,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class CompositeApprovalGrant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    grant_id: UUID
    plan_id: UUID
    plan_hash: PlanHash
    authorized_call_ids: tuple[str, ...] = Field(
        min_length=2,
        max_length=MAX_COMPOSITE_CALLS,
    )
    source: Literal["ui", "mcp"]
    issued_monotonic: float = Field(ge=0)
    expires_monotonic: float = Field(gt=0)

    @classmethod
    def issue(
        cls,
        plan: CompositeValidatedPlan,
        *,
        source: Literal["ui", "mcp"] = "ui",
        now: float | None = None,
        ttl_seconds: float = DEFAULT_APPROVAL_TTL_SECONDS,
    ) -> CompositeApprovalGrant:
        issued = perf_counter() if now is None else now
        if ttl_seconds <= 0:
            raise ValueError("The approval lifetime must be positive.")
        return cls(
            grant_id=uuid4(),
            plan_id=plan.plan_id,
            plan_hash=plan.plan_hash,
            authorized_call_ids=tuple(call.call_id for call in plan.calls),
            source=source,
            issued_monotonic=issued,
            expires_monotonic=issued + ttl_seconds,
        )

    def authorize(
        self,
        plan: CompositeValidatedPlan,
        *,
        now: float,
    ) -> None:
        if now > self.expires_monotonic:
            raise PlanApprovalError("The composite plan approval expired.")
        if self.plan_id != plan.plan_id or self.plan_hash != plan.plan_hash:
            raise PlanApprovalError("The approval belongs to another composite plan.")
        if self.authorized_call_ids != tuple(call.call_id for call in plan.calls):
            raise PlanApprovalError("The approval does not cover every plan call.")


class CompositeExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_id: UUID
    plan_hash: PlanHash
    results: tuple[JsonValue, ...]
    validation_results: tuple[dict[str, JsonValue], ...]
    state_before: DocumentStateToken
    state_after: DocumentStateToken


class PlanStatusSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_id: UUID
    plan_hash: PlanHash
    status: CompositePlanStatus
    completed_calls: int = Field(ge=0, le=MAX_COMPOSITE_CALLS)
    total_calls: int = Field(ge=2, le=MAX_COMPOSITE_CALLS)
    error_code: str | None = Field(default=None, max_length=64)


ContextReader = Callable[[], Mapping[str, Any]]
CancellationCheck = Callable[[], bool]
CallScope = Callable[[str], AbstractContextManager[None]]


class CompositePlanExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        context_reader: ContextReader,
        *,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self._registry = registry
        self._context_reader = context_reader
        self._clock = clock

    def execute(
        self,
        plan: CompositeValidatedPlan,
        grant: CompositeApprovalGrant,
        *,
        is_cancelled: CancellationCheck | None = None,
        on_progress: Callable[[int], None] | None = None,
        call_scope: CallScope | None = None,
    ) -> CompositeExecutionResult:
        grant.authorize(plan, now=self._clock())
        self._prevalidate(plan)
        baseline = self._read_state_token()
        if baseline != plan.base_state_token:
            raise StalePlanError("The CAD state changed after planning.")

        results: list[JsonValue] = []
        validations: list[dict[str, JsonValue]] = []
        committed: list[ValidatedPlanCall] = []
        try:
            for call in plan.calls:
                if is_cancelled is not None and is_cancelled():
                    raise CompositePlanError("The composite plan was cancelled.")
                scope = (
                    call_scope(call.call_id)
                    if call_scope is not None
                    else nullcontext()
                )
                with scope:
                    result = self._registry.execute(
                        call.name,
                        call.arguments,
                        confirmed=True,
                    )
                committed.append(call)
                validation = self._registry.execute("cad.validate_document")
                if (
                    not isinstance(validation, Mapping)
                    or validation.get("valid") is not True
                ):
                    raise CompositePlanError(
                        "A composite post-condition validation failed."
                    )
                results.append(result)
                validations.append(dict(validation))
                if on_progress is not None:
                    on_progress(len(committed))
            state_after = self._read_state_token()
            if state_after.document_fingerprint == baseline.document_fingerprint:
                raise CompositePlanError("The composite plan did not change CAD state.")
            return CompositeExecutionResult(
                plan_id=plan.plan_id,
                plan_hash=plan.plan_hash,
                results=tuple(results),
                validation_results=tuple(validations),
                state_before=baseline,
                state_after=state_after,
            )
        except Exception as exc:
            if committed:
                self._rollback(tuple(committed), baseline, call_scope)
            if isinstance(exc, (PlanApprovalError, StalePlanError)):
                raise
            if isinstance(exc, CompositeRollbackError):
                raise
            raise CompositePlanError(
                "The composite plan failed and its committed steps were rolled back."
            ) from exc

    def _prevalidate(self, plan: CompositeValidatedPlan) -> None:
        for call in plan.calls:
            spec = self._registry.get_spec(call.name)
            if spec.risk is not ToolRisk.MODIFY or call.name == "cad.undo":
                raise PlanExecutionError("A composite call is not compensatable.")
            self._registry.validate_arguments(call.name, call.arguments)
            if not self._registry.has_handler(call.name):
                raise PlanExecutionError("A composite call has no connected handler.")
        if not self._registry.has_handler("cad.undo"):
            raise PlanExecutionError("Composite rollback is unavailable.")

    def _rollback(
        self,
        committed: tuple[ValidatedPlanCall, ...],
        baseline: DocumentStateToken,
        call_scope: CallScope | None,
    ) -> None:
        for call in reversed(committed):
            scope = (
                call_scope(f"rollback:{call.call_id}")
                if call_scope is not None
                else nullcontext()
            )
            with scope:
                result = self._registry.execute("cad.undo", confirmed=True)
            if not isinstance(result, Mapping) or result.get("undone") is not True:
                raise CompositeRollbackError("A composite rollback step failed.")
        validation = self._registry.execute("cad.validate_document")
        restored = self._read_state_token()
        if (
            not isinstance(validation, Mapping)
            or validation.get("valid") is not True
            or restored.document_id != baseline.document_id
            or restored.document_fingerprint != baseline.document_fingerprint
            or restored.selection_fingerprint != baseline.selection_fingerprint
        ):
            raise CompositeRollbackError(
                "The CAD baseline was not restored after composite rollback."
            )

    def _read_state_token(self) -> DocumentStateToken:
        try:
            return DocumentStateToken.model_validate(
                self._context_reader()["state_token"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PlanExecutionError("The CAD state could not be verified.") from exc


class PlanService:
    """In-memory idempotent plan status service suitable for chat or MCP polling."""

    def __init__(
        self,
        audit_service: Any | None = None,
        registry: ToolRegistry | None = None,
    ) -> None:
        self._lock = RLock()
        self._plans: dict[UUID, CompositeValidatedPlan] = {}
        self._status: dict[UUID, PlanStatusSnapshot] = {}
        self._cancelled: set[UUID] = set()
        self._audit_service = audit_service
        self._registry = registry
        if audit_service is not None and registry is None:
            raise ValueError("An audited plan service requires the shared registry.")

    def submit(
        self,
        plan: CompositeValidatedPlan,
        *,
        audit_source: Any = "system",
        original_request: str | None = None,
        parent_action_id: UUID | None = None,
    ) -> PlanStatusSnapshot:
        with self._lock:
            existing = self._plans.get(plan.plan_id)
            if existing is not None:
                if existing.plan_hash != plan.plan_hash:
                    raise ValueError("A plan ID cannot be reused with another hash.")
                return self._status[plan.plan_id]
            status = PlanStatusSnapshot(
                plan_id=plan.plan_id,
                plan_hash=plan.plan_hash,
                status=CompositePlanStatus.AWAITING_APPROVAL,
                completed_calls=0,
                total_calls=len(plan.calls),
            )
            if self._audit_service is not None:
                self._audit_service.begin_plan(
                    plan,
                    self._registry,
                    source=audit_source,
                    original_request=original_request,
                    parent_action_id=parent_action_id,
                )
            self._plans[plan.plan_id] = plan
            self._status[plan.plan_id] = status
            return status

    def get_status(self, plan_id: UUID) -> PlanStatusSnapshot:
        with self._lock:
            if plan_id not in self._status:
                raise KeyError("Unknown composite plan.")
            return self._status[plan_id]

    def cancel(
        self,
        plan_id: UUID,
        *,
        audit_source: str = "system",
        denied: bool = False,
        error_code: str = "cancelled",
    ) -> PlanStatusSnapshot:
        with self._lock:
            current = self.get_status(plan_id)
            if current.status in {
                CompositePlanStatus.COMPLETED,
                CompositePlanStatus.ROLLED_BACK,
                CompositePlanStatus.FAILED,
            }:
                return current
            self._cancelled.add(plan_id)
            if current.status is CompositePlanStatus.AWAITING_APPROVAL:
                if self._audit_service is not None:
                    self._audit_service.cancel_plan(
                        plan_id,
                        source=audit_source,
                        denied=denied,
                        error_code=error_code,
                    )
                current = current.model_copy(
                    update={"status": CompositePlanStatus.CANCELLED}
                )
                self._status[plan_id] = current
            return current

    def execute(
        self,
        plan_id: UUID,
        grant: CompositeApprovalGrant,
        executor: CompositePlanExecutor,
        *,
        on_progress: Callable[[PlanStatusSnapshot], None] | None = None,
        approval_automatic: bool = False,
        approval_source: str = "ui",
    ) -> CompositeExecutionResult:
        with self._lock:
            plan = self._plans[plan_id]
            current = self._status[plan_id]
            if current.status is CompositePlanStatus.COMPLETED:
                raise ValueError("A completed plan cannot execute again.")
            if plan_id in self._cancelled:
                raise ValueError("A cancelled plan cannot execute.")
            if self._audit_service is not None:
                self._audit_service.approve_plan(
                    plan_id,
                    automatic=approval_automatic,
                    source=approval_source,
                    grant_id=grant.grant_id,
                )
            self._status[plan_id] = current.model_copy(
                update={"status": CompositePlanStatus.RUNNING}
            )

        def progress(completed: int) -> None:
            with self._lock:
                snapshot = self._status[plan_id]
                self._status[plan_id] = snapshot.model_copy(
                    update={"completed_calls": completed}
                )
                updated = self._status[plan_id]
            if on_progress is not None:
                on_progress(updated)

        try:
            result = executor.execute(
                plan,
                grant,
                is_cancelled=lambda: plan_id in self._cancelled,
                on_progress=progress,
                call_scope=(
                    lambda call_id: self._audit_service.plan_call_scope(
                        plan_id,
                        call_id,
                    )
                )
                if self._audit_service is not None
                else None,
            )
        except CompositeRollbackError:
            with self._lock:
                snapshot = self._status[plan_id]
                self._status[plan_id] = snapshot.model_copy(
                    update={
                        "status": CompositePlanStatus.FAILED,
                        "error_code": "rollback_failed",
                    }
                )
            if self._audit_service is not None:
                from aicad.audit.models import AuditActionStatus

                self._audit_service.finish_plan_failure(
                    plan_id,
                    status=AuditActionStatus.FAILED,
                    error_code="rollback_failed",
                )
            raise
        except CompositePlanError:
            with self._lock:
                snapshot = self._status[plan_id]
                cancelled = plan_id in self._cancelled
                self._status[plan_id] = snapshot.model_copy(
                    update={
                        "status": (
                            CompositePlanStatus.CANCELLED
                            if cancelled
                            else CompositePlanStatus.ROLLED_BACK
                        ),
                        "error_code": (
                            "cancelled" if cancelled else "execution_failed"
                        ),
                    }
                )
            if self._audit_service is not None:
                from aicad.audit.models import AuditActionStatus

                self._audit_service.finish_plan_failure(
                    plan_id,
                    status=(
                        AuditActionStatus.CANCELLED
                        if cancelled
                        else AuditActionStatus.ROLLED_BACK
                    ),
                    error_code=("cancelled" if cancelled else "execution_failed"),
                )
            raise
        except Exception:
            with self._lock:
                snapshot = self._status[plan_id]
                self._status[plan_id] = snapshot.model_copy(
                    update={
                        "status": CompositePlanStatus.FAILED,
                        "error_code": "precondition_failed",
                    }
                )
            if self._audit_service is not None:
                from aicad.audit.models import AuditActionStatus

                self._audit_service.finish_plan_failure(
                    plan_id,
                    status=AuditActionStatus.FAILED,
                    error_code="precondition_failed",
                )
            raise
        with self._lock:
            snapshot = self._status[plan_id]
            self._status[plan_id] = snapshot.model_copy(
                update={
                    "status": CompositePlanStatus.COMPLETED,
                    "completed_calls": len(plan.calls),
                }
            )
        if self._audit_service is not None:
            self._audit_service.finish_plan_success(plan_id, result)
        return result

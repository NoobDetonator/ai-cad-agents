from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

from aicad.core.tool_registry import ToolRisk


AUDIT_SCHEMA_VERSION = "1.0"
AuditText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2_048),
]
AuditLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]


class AuditSource(StrEnum):
    LOCAL_CHAT = "local_chat"
    AI_CHAT = "ai_chat"
    MCP = "mcp"
    SYSTEM = "system"


class AuditActionKind(StrEnum):
    TOOL = "tool"
    PLAN = "plan"
    TURN = "turn"


class AuditApprovalDecision(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED_MANUAL = "approved_manual"
    APPROVED_AUTOMATIC = "approved_automatic"
    DENIED = "denied"
    CANCELLED = "cancelled"


class AuditActionStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class AuditValidationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_RUN = "not_run"


class AuditTransactionOutcome(StrEnum):
    COMMITTED = "committed"
    ABORTED = "aborted"
    UNDONE = "undone"
    UNKNOWN = "unknown"


class AuditPlanRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: str = Field(min_length=1, max_length=32)
    plan_id: UUID
    plan_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    base_state_token: dict[str, JsonValue]
    steps: tuple[AuditText, ...] = Field(min_length=1, max_length=32)


class AuditToolCallRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    call_id: str = Field(min_length=1, max_length=128)
    tool_name: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^cad\.[a-z][a-z0-9_]*$",
    )
    arguments: dict[str, JsonValue]
    risk: ToolRisk
    expected_validations: tuple[AuditLabel, ...] = Field(
        default_factory=tuple,
        max_length=16,
    )


class AuditApprovalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: AuditApprovalDecision
    decided_at: datetime | None = None
    source: str | None = Field(default=None, max_length=32)
    grant_id: UUID | None = None

    @model_validator(mode="after")
    def validate_decision(self) -> AuditApprovalRecord:
        if self.decision is AuditApprovalDecision.PENDING:
            if (
                self.decided_at is not None
                or self.source is not None
                or self.grant_id is not None
            ):
                raise ValueError("A pending approval cannot have a decision timestamp.")
        else:
            _require_aware(self.decided_at, "approval decision")
            if not self.source:
                raise ValueError("An approval decision requires a source.")
        if self.grant_id is not None and self.decision not in {
            AuditApprovalDecision.APPROVED_MANUAL,
            AuditApprovalDecision.APPROVED_AUTOMATIC,
        }:
            raise ValueError("Only an approved action can reference a grant.")
        return self


class AuditValidationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=128)
    status: AuditValidationStatus
    details: dict[str, JsonValue] = Field(default_factory=dict)


class AuditTransactionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: str = Field(min_length=1, max_length=128)
    call_id: str = Field(min_length=1, max_length=128)
    sequence: int = Field(ge=1, le=32)
    label: str | None = Field(default=None, max_length=256)
    outcome: AuditTransactionOutcome = AuditTransactionOutcome.UNKNOWN


class AuditActionRecord(BaseModel):
    """Versioned action snapshot describing intent, authorization, and outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    schema_version: Literal[AUDIT_SCHEMA_VERSION] = AUDIT_SCHEMA_VERSION
    session_id: UUID
    action_id: UUID
    parent_action_id: UUID | None = None
    revision: int = Field(default=1, ge=1)
    source: AuditSource
    kind: AuditActionKind
    started_at: datetime
    finished_at: datetime | None = None
    original_request: str | None = Field(default=None, max_length=32_768)
    intention: str | None = Field(default=None, max_length=2_048)
    assumptions: tuple[AuditText, ...] = Field(default_factory=tuple, max_length=16)
    plan: AuditPlanRecord | None = None
    tool_calls: tuple[AuditToolCallRecord, ...] = Field(
        default_factory=tuple,
        max_length=16,
    )
    approval: AuditApprovalRecord
    status: AuditActionStatus = AuditActionStatus.PENDING
    result: JsonValue | None = None
    error_code: str | None = Field(
        default=None,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    duration_ms: int | None = Field(default=None, ge=0)
    validations: tuple[AuditValidationRecord, ...] = Field(
        default_factory=tuple,
        max_length=64,
    )
    transactions: tuple[AuditTransactionRecord, ...] = Field(
        default_factory=tuple,
        max_length=32,
    )
    redaction_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> AuditActionRecord:
        _require_aware(self.started_at, "action start")
        terminal = self.status is not AuditActionStatus.PENDING
        if terminal:
            _require_aware(self.finished_at, "action finish")
            if self.duration_ms is None:
                raise ValueError("A terminal audit action requires a duration.")
        elif self.finished_at is not None or self.duration_ms is not None:
            raise ValueError("A pending audit action cannot be finished.")
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("The audit finish timestamp precedes its start.")
        if self.status is AuditActionStatus.COMPLETED and self.error_code is not None:
            raise ValueError("A completed audit action cannot contain an error code.")
        if (
            self.status is AuditActionStatus.COMPLETED
            and self.approval.decision is AuditApprovalDecision.PENDING
            and all(call.risk is ToolRisk.READ for call in self.tool_calls)
        ):
            raise ValueError("A completed audit action requires an approval decision.")
        if self.status in {
            AuditActionStatus.FAILED,
            AuditActionStatus.ROLLED_BACK,
        } and self.error_code is None:
            raise ValueError("A failed or rolled-back audit action needs an error code.")
        if self.status in {
            AuditActionStatus.CANCELLED,
            AuditActionStatus.ROLLED_BACK,
            AuditActionStatus.FAILED,
        } and self.result is not None:
            raise ValueError("An unsuccessful audit action cannot contain a result.")
        if self.kind is AuditActionKind.PLAN and self.plan is None:
            raise ValueError("A plan audit action requires plan metadata.")
        if self.kind is AuditActionKind.TOOL and len(self.tool_calls) != 1:
            raise ValueError("A tool audit action requires exactly one tool call.")
        if self.kind is AuditActionKind.TURN and self.plan is not None:
            raise ValueError("A turn audit action cannot contain immutable plan metadata.")
        if self.plan is not None and not self.tool_calls:
            raise ValueError("An audited plan must contain validated tool calls.")
        if (
            self.status is AuditActionStatus.COMPLETED
            and any(call.risk is not ToolRisk.READ for call in self.tool_calls)
            and self.approval.decision
            not in {
                AuditApprovalDecision.APPROVED_MANUAL,
                AuditApprovalDecision.APPROVED_AUTOMATIC,
            }
        ):
            raise ValueError("A completed mutation requires an explicit approval.")
        return self


class AuditExportBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[AUDIT_SCHEMA_VERSION] = AUDIT_SCHEMA_VERSION
    session_id: UUID
    exported_at: datetime
    records: tuple[AuditActionRecord, ...]

    @model_validator(mode="after")
    def validate_bundle(self) -> AuditExportBundle:
        _require_aware(self.exported_at, "audit export")
        if any(record.session_id != self.session_id for record in self.records):
            raise ValueError("An audit export cannot mix sessions.")
        return self


def _require_aware(value: datetime | None, label: str) -> None:
    if value is None or value.utcoffset() is None:
        raise ValueError(f"The {label} timestamp must include a timezone.")

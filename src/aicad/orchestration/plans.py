from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager, nullcontext
from enum import StrEnum
import hashlib
import json
from time import perf_counter
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

from aicad.core.context import DocumentStateToken
from aicad.core.tool_registry import ToolRegistry, ToolRisk
from aicad.orchestration.models import OrchestrationPlan


PLAN_CONTRACT_VERSION = "1.0"
DEFAULT_APPROVAL_TTL_SECONDS = 30.0

PlanHash = Annotated[
    str,
    StringConstraints(pattern=r"^[a-f0-9]{64}$"),
]


class PlanApprovalError(PermissionError):
    """The approval does not authorize the exact immutable plan."""


class StalePlanError(PlanApprovalError):
    """The CAD state changed after the plan was formed."""


class PlanExecutionError(RuntimeError):
    """The authorized mutation or its post-condition failed safely."""


class ValidatedPlanCall(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    call_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$",
    )
    name: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^cad\.[a-z][a-z0-9_]*$",
    )
    arguments: dict[str, JsonValue]
    risk: Literal[ToolRisk.MODIFY]
    expected_validations: tuple[str, ...] = Field(
        default=("registry.arguments", "document.valid", "state.advanced"),
        min_length=1,
        max_length=8,
    )


class ValidatedPlan(BaseModel):
    """One locally validated mutation frozen against a CAD state token."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal[PLAN_CONTRACT_VERSION] = PLAN_CONTRACT_VERSION
    plan_id: UUID
    base_state_token: DocumentStateToken
    intention: str = Field(min_length=1, max_length=500)
    assumptions: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    steps: tuple[str, ...] = Field(min_length=1, max_length=32)
    call: ValidatedPlanCall
    max_calls: Literal[1] = 1
    plan_hash: PlanHash

    @model_validator(mode="after")
    def validate_hash(self) -> ValidatedPlan:
        if self.plan_hash != self.calculate_hash(self.model_dump(mode="json")):
            raise ValueError("The immutable plan hash is invalid.")
        return self

    @classmethod
    def build(
        cls,
        plan: OrchestrationPlan,
        base_state_token: DocumentStateToken,
        registry: ToolRegistry,
        *,
        plan_id: UUID | None = None,
    ) -> ValidatedPlan:
        if len(plan.tool_calls) != 1:
            raise ValueError("A single-mutation plan requires exactly one call.")
        proposed = plan.tool_calls[0]
        spec = registry.get_spec(proposed.name)
        if spec.risk is not ToolRisk.MODIFY or proposed.risk is not ToolRisk.MODIFY:
            raise ValueError("Only one registered mutation can be frozen.")
        arguments = registry.validate_arguments(proposed.name, proposed.arguments)
        payload: dict[str, Any] = {
            "contract_version": PLAN_CONTRACT_VERSION,
            "plan_id": str(plan_id or uuid4()),
            "base_state_token": base_state_token.model_dump(mode="json"),
            "intention": plan.intention,
            "assumptions": list(plan.assumptions),
            "steps": list(plan.steps),
            "call": ValidatedPlanCall(
                call_id=proposed.call_id,
                name=proposed.name,
                arguments=arguments,
                risk=ToolRisk.MODIFY,
            ).model_dump(mode="json"),
            "max_calls": 1,
        }
        payload["plan_hash"] = cls.calculate_hash(payload)
        return cls.model_validate(payload)

    @staticmethod
    def calculate_hash(payload: Mapping[str, Any]) -> str:
        executable = dict(payload)
        executable.pop("plan_hash", None)
        encoded = json.dumps(
            executable,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class ApprovalGrant(BaseModel):
    """Short-lived permission for exactly one displayed plan hash and call."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    grant_id: UUID
    plan_id: UUID
    plan_hash: PlanHash
    authorized_call_ids: tuple[str, ...] = Field(min_length=1, max_length=1)
    source: Literal["ui"] = "ui"
    decision: Literal["approved"] = "approved"
    issued_monotonic: float = Field(ge=0)
    expires_monotonic: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_window(self) -> ApprovalGrant:
        if self.expires_monotonic <= self.issued_monotonic:
            raise ValueError("The approval expiry must follow its issue time.")
        return self

    @classmethod
    def issue(
        cls,
        plan: ValidatedPlan,
        *,
        now: float | None = None,
        ttl_seconds: float = DEFAULT_APPROVAL_TTL_SECONDS,
    ) -> ApprovalGrant:
        issued = perf_counter() if now is None else now
        if ttl_seconds <= 0:
            raise ValueError("The approval lifetime must be positive.")
        return cls(
            grant_id=uuid4(),
            plan_id=plan.plan_id,
            plan_hash=plan.plan_hash,
            authorized_call_ids=(plan.call.call_id,),
            issued_monotonic=issued,
            expires_monotonic=issued + ttl_seconds,
        )

    def authorize(self, plan: ValidatedPlan, *, now: float | None = None) -> None:
        checked_now = perf_counter() if now is None else now
        if checked_now > self.expires_monotonic:
            raise PlanApprovalError("The plan approval expired.")
        if self.plan_id != plan.plan_id or self.plan_hash != plan.plan_hash:
            raise PlanApprovalError("The approval belongs to another plan.")
        if self.authorized_call_ids != (plan.call.call_id,):
            raise PlanApprovalError("The approval does not authorize this call.")


class PlanExecutionStatus(StrEnum):
    COMPLETED = "completed"


class PlanExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal[PlanExecutionStatus.COMPLETED] = PlanExecutionStatus.COMPLETED
    plan_id: UUID
    plan_hash: PlanHash
    call_id: str
    tool_name: str
    tool_result: JsonValue
    validation_result: dict[str, JsonValue]
    state_before: DocumentStateToken
    state_after: DocumentStateToken


ContextReader = Callable[[], Mapping[str, Any]]
CallScope = Callable[[str], AbstractContextManager[None]]


class SingleMutationPlanExecutor:
    """Execute one exact approved mutation, never a generated or changed call."""

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
        plan: ValidatedPlan,
        grant: ApprovalGrant,
        *,
        call_scope: CallScope | None = None,
    ) -> PlanExecutionResult:
        grant.authorize(plan, now=self._clock())
        current = self._read_state_token()
        if current != plan.base_state_token:
            raise StalePlanError(
                "The CAD document changed after the plan was prepared."
            )
        spec = self._registry.get_spec(plan.call.name)
        if spec.risk is not ToolRisk.MODIFY:
            raise PlanExecutionError("The frozen call is no longer a mutation.")
        arguments = self._registry.validate_arguments(
            plan.call.name,
            plan.call.arguments,
        )
        try:
            scope = (
                call_scope(plan.call.call_id)
                if call_scope is not None
                else nullcontext()
            )
            with scope:
                result = self._registry.execute(
                    plan.call.name,
                    arguments,
                    confirmed=True,
                )
            validation = self._registry.execute("cad.validate_document")
            if not isinstance(validation, Mapping) or validation.get("valid") is not True:
                raise PlanExecutionError(
                    "The CAD post-condition validation did not pass."
                )
            state_after = self._read_state_token()
        except PlanExecutionError:
            raise
        except Exception as exc:
            raise PlanExecutionError(
                "The approved CAD mutation could not be completed."
            ) from exc
        if state_after == current:
            raise PlanExecutionError("The CAD state did not advance after mutation.")
        return PlanExecutionResult(
            plan_id=plan.plan_id,
            plan_hash=plan.plan_hash,
            call_id=plan.call.call_id,
            tool_name=plan.call.name,
            tool_result=result,
            validation_result=dict(validation),
            state_before=current,
            state_after=state_after,
        )

    def _read_state_token(self) -> DocumentStateToken:
        snapshot = self._context_reader()
        try:
            return DocumentStateToken.model_validate(snapshot["state_token"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PlanExecutionError(
                "The current CAD state could not be verified."
            ) from exc

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Any, Literal, TypeAlias
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from aicad.core.tool_registry import ToolInputError, ToolRegistry, ToolRisk
from aicad.orchestration.plan_service import CompositeValidatedPlan


PROTOCOL_VERSION = "1.0"


class BridgeRequestSource(StrEnum):
    MCP = "mcp"


class BridgePlanOperation(StrEnum):
    SUBMIT = "submit_plan"
    STATUS = "get_plan_status"
    CANCEL = "cancel_plan"


class BridgeResponseStatus(StrEnum):
    COMPLETED = "completed"
    PENDING_CONFIRMATION = "pending_confirmation"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class BridgeErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    UNSUPPORTED_VERSION = "unsupported_version"
    UNKNOWN_TOOL = "unknown_tool"
    INVALID_ARGUMENTS = "invalid_arguments"
    UNAUTHORIZED = "unauthorized"
    CONFIRMATION_DENIED = "confirmation_denied"
    TIMEOUT = "timeout"
    EXECUTION_ERROR = "execution_error"
    GUI_UNAVAILABLE = "gui_unavailable"
    QUEUE_FULL = "queue_full"


class BridgeError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: BridgeErrorCode
    message: str = Field(min_length=1, max_length=500)
    details: dict[str, JsonValue] = Field(default_factory=dict)


class BridgeRequest(BaseModel):
    """One versioned request accepted by the GUI-side bridge dispatcher."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal[PROTOCOL_VERSION] = PROTOCOL_VERSION
    request_id: UUID
    tool_name: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^cad\.[a-z][a-z0-9_]*$",
    )
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    source: BridgeRequestSource


class BridgePlanSubmitRequest(BaseModel):
    """Submit one immutable composite plan to the GUI-owned plan service."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal[PROTOCOL_VERSION] = PROTOCOL_VERSION
    request_id: UUID
    operation: Literal[BridgePlanOperation.SUBMIT] = BridgePlanOperation.SUBMIT
    plan: CompositeValidatedPlan
    source: BridgeRequestSource


class BridgePlanStatusRequest(BaseModel):
    """Read the current state of one previously submitted composite plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal[PROTOCOL_VERSION] = PROTOCOL_VERSION
    request_id: UUID
    operation: Literal[BridgePlanOperation.STATUS] = BridgePlanOperation.STATUS
    plan_id: UUID
    source: BridgeRequestSource


class BridgePlanCancelRequest(BaseModel):
    """Request cooperative cancellation of one composite plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal[PROTOCOL_VERSION] = PROTOCOL_VERSION
    request_id: UUID
    operation: Literal[BridgePlanOperation.CANCEL] = BridgePlanOperation.CANCEL
    plan_id: UUID
    source: BridgeRequestSource


BridgePlanRequest: TypeAlias = Annotated[
    BridgePlanSubmitRequest | BridgePlanStatusRequest | BridgePlanCancelRequest,
    Field(discriminator="operation"),
]
BridgeTransportRequest: TypeAlias = BridgeRequest | BridgePlanRequest
_PLAN_REQUEST_ADAPTER = TypeAdapter(BridgePlanRequest)


class BridgeResponse(BaseModel):
    """Structured result, pending state or categorized failure for one request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal[PROTOCOL_VERSION] = PROTOCOL_VERSION
    request_id: UUID
    status: BridgeResponseStatus
    result: JsonValue | None = None
    error: BridgeError | None = None

    @model_validator(mode="after")
    def validate_payload_for_status(self) -> BridgeResponse:
        if self.status is BridgeResponseStatus.COMPLETED:
            if self.result is None or self.error is not None:
                raise ValueError(
                    "A completed bridge response requires a result and no error."
                )
            return self
        if self.status is BridgeResponseStatus.PENDING_CONFIRMATION:
            if self.result is not None or self.error is not None:
                raise ValueError(
                    "A pending bridge response cannot contain a result or error."
                )
            return self
        if self.result is not None or self.error is None:
            raise ValueError(
                "A terminal non-success bridge response requires an error and no result."
            )
        return self


class BridgeProtocolError(ValueError):
    """Categorized failure raised before a request reaches a CAD handler."""

    def __init__(
        self,
        code: BridgeErrorCode,
        message: str,
        *,
        details: dict[str, JsonValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.error = BridgeError(
            code=code,
            message=message,
            details=details or {},
        )

    @property
    def code(self) -> BridgeErrorCode:
        return self.error.code


def _validation_details(error: ValidationError) -> dict[str, JsonValue]:
    issues: list[JsonValue] = []
    for issue in error.errors(
        include_url=False,
        include_context=False,
        include_input=False,
    ):
        issues.append(
            {
                "location": ".".join(str(part) for part in issue["loc"]),
                "message": issue["msg"],
                "type": issue["type"],
            }
        )
    return {"issues": issues}


def validate_request_payload(
    payload: Mapping[str, Any], registry: ToolRegistry
) -> BridgeRequest:
    """Parse an envelope and validate its call through the shared ToolRegistry."""

    if not isinstance(payload, Mapping):
        raise BridgeProtocolError(
            BridgeErrorCode.INVALID_REQUEST,
            "The bridge request must be a JSON object.",
        )

    received_version = payload.get("protocol_version")
    if received_version != PROTOCOL_VERSION:
        raise BridgeProtocolError(
            BridgeErrorCode.UNSUPPORTED_VERSION,
            "The bridge protocol version is not supported.",
            details={
                "expected": PROTOCOL_VERSION,
                "received": received_version,
            },
        )

    try:
        request = BridgeRequest.model_validate(dict(payload))
    except ValidationError as exc:
        raise BridgeProtocolError(
            BridgeErrorCode.INVALID_REQUEST,
            "The bridge request envelope is invalid.",
            details=_validation_details(exc),
        ) from exc

    try:
        checked_arguments = registry.validate_arguments(
            request.tool_name,
            request.arguments,
        )
    except KeyError as exc:
        raise BridgeProtocolError(
            BridgeErrorCode.UNKNOWN_TOOL,
            "The requested CAD tool is not registered.",
            details={"tool_name": request.tool_name},
        ) from exc
    except ToolInputError as exc:
        raise BridgeProtocolError(
            BridgeErrorCode.INVALID_ARGUMENTS,
            str(exc),
            details={"tool_name": request.tool_name},
        ) from exc

    return request.model_copy(update={"arguments": checked_arguments})


def validate_plan_request_payload(
    payload: Mapping[str, Any], registry: ToolRegistry
) -> BridgePlanRequest:
    """Validate plan control envelopes and every submitted call against the registry."""

    if not isinstance(payload, Mapping):
        raise BridgeProtocolError(
            BridgeErrorCode.INVALID_REQUEST,
            "The bridge plan request must be a JSON object.",
        )
    received_version = payload.get("protocol_version")
    if received_version != PROTOCOL_VERSION:
        raise BridgeProtocolError(
            BridgeErrorCode.UNSUPPORTED_VERSION,
            "The bridge protocol version is not supported.",
            details={"expected": PROTOCOL_VERSION, "received": received_version},
        )
    try:
        request = _PLAN_REQUEST_ADAPTER.validate_python(dict(payload))
    except ValidationError as exc:
        raise BridgeProtocolError(
            BridgeErrorCode.INVALID_REQUEST,
            "The bridge plan request envelope is invalid.",
            details=_validation_details(exc),
        ) from exc

    if not isinstance(request, BridgePlanSubmitRequest):
        return request

    for call in request.plan.calls:
        try:
            spec = registry.get_spec(call.name)
        except KeyError as exc:
            raise BridgeProtocolError(
                BridgeErrorCode.UNKNOWN_TOOL,
                "A submitted plan tool is not registered.",
                details={"tool_name": call.name},
            ) from exc
        if spec.risk is not ToolRisk.MODIFY or call.name == "cad.undo":
            raise BridgeProtocolError(
                BridgeErrorCode.INVALID_REQUEST,
                "Every submitted plan call must be a compensatable mutation.",
                details={"tool_name": call.name},
            )
        try:
            registry.validate_arguments(call.name, call.arguments)
        except ToolInputError as exc:
            raise BridgeProtocolError(
                BridgeErrorCode.INVALID_ARGUMENTS,
                str(exc),
                details={"tool_name": call.name},
            ) from exc
    return request

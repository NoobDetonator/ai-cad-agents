from __future__ import annotations

from enum import StrEnum
import json
import re
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)


TOOL_RESULT_CONTRACT_VERSION = "1.0"
MAX_ERROR_DETAILS_BYTES = 8 * 1024
MAX_TOOL_RESULT_BYTES = 64 * 1024

ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
ObjectName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z][A-Za-z0-9_]*$",
    ),
]


class ToolResultStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ToolErrorCode(StrEnum):
    MISSING_CONTEXT = "missing_context"
    INVALID_ARGUMENTS = "invalid_arguments"
    PRECONDITION_FAILED = "precondition_failed"
    STALE_STATE = "stale_state"
    TRANSIENT_PROVIDER = "transient_provider"
    TRANSPORT_UNAVAILABLE = "transport_unavailable"
    EXECUTION_FAILED = "execution_failed"
    VALIDATION_FAILED = "validation_failed"
    CANCELLED = "cancelled"
    LIMIT_EXCEEDED = "limit_exceeded"
    INTERNAL_ERROR = "internal_error"


_SENSITIVE_KEYS = {
    "apikey",
    "authorization",
    "credential",
    "credentials",
    "password",
    "secret",
    "sessiontoken",
}


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def reject_sensitive_metadata_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if _normalized_key(str(key)) in _SENSITIVE_KEYS:
                raise ValueError("Structured result metadata cannot contain secrets.")
            reject_sensitive_metadata_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            reject_sensitive_metadata_keys(item)


def _json_size(value: Any) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )


class ToolError(BaseModel):
    """Safe, actionable failure information that can be shown to an AI."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ToolErrorCode
    message: ShortText
    retryable: bool = False
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_details(self) -> ToolError:
        reject_sensitive_metadata_keys(self.details)
        if _json_size(self.details) > MAX_ERROR_DETAILS_BYTES:
            raise ValueError("Tool error details are too large.")
        return self


class AffectedObjects(BaseModel):
    """Internal FreeCAD object names touched or observed by one operation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    read: tuple[ObjectName, ...] = Field(default_factory=tuple, max_length=256)
    created: tuple[ObjectName, ...] = Field(default_factory=tuple, max_length=256)
    modified: tuple[ObjectName, ...] = Field(default_factory=tuple, max_length=256)
    removed: tuple[ObjectName, ...] = Field(default_factory=tuple, max_length=256)

    @field_validator("read", "created", "modified", "removed")
    @classmethod
    def reject_duplicate_names(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("Affected object names must be unique in each group.")
        return value


class ToolValidation(BaseModel):
    """One explicit validation performed before accepting a tool result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=128,
            pattern=r"^[a-z][a-z0-9_.-]*$",
        ),
    ]
    passed: bool
    message: str = Field(default="", max_length=500)


class ToolResultEnvelope(BaseModel):
    """Versioned result contract shared by future chat and MCP execution paths."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    contract_version: Literal[TOOL_RESULT_CONTRACT_VERSION] = (
        TOOL_RESULT_CONTRACT_VERSION
    )
    tool_name: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^cad\.[a-z][a-z0-9_]*$",
    )
    status: ToolResultStatus
    summary: ShortText
    result: JsonValue = None
    error: ToolError | None = None
    affected_objects: AffectedObjects = Field(default_factory=AffectedObjects)
    validations: tuple[ToolValidation, ...] = Field(default_factory=tuple, max_length=64)
    duration_ms: float = Field(ge=0)
    state_before: dict[str, JsonValue] | None = None
    state_after: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def validate_status_and_size(self) -> ToolResultEnvelope:
        if self.status is ToolResultStatus.COMPLETED:
            if self.error is not None:
                raise ValueError("A completed tool result cannot contain an error.")
        else:
            if self.error is None:
                raise ValueError("A non-completed tool result requires an error.")
            if self.result is not None:
                raise ValueError("A failed or cancelled tool cannot return partial data.")
        if (
            self.status is ToolResultStatus.CANCELLED
            and self.error is not None
            and self.error.code is not ToolErrorCode.CANCELLED
        ):
            raise ValueError("A cancelled result requires the cancelled error code.")

        payload = self.model_dump(mode="json")
        reject_sensitive_metadata_keys(payload)
        if _json_size(payload) > MAX_TOOL_RESULT_BYTES:
            raise ValueError("The structured tool result is too large.")
        return self

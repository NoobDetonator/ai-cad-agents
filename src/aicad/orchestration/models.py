from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

from aicad.core.tool_registry import ToolRisk, ToolSpec


PROVIDER_CONTRACT_VERSION = "1.0"

ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
LongText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]


class ProviderToolDefinition(BaseModel):
    """Provider-neutral description of one allowed registry tool."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^cad\.[a-z][a-z0-9_]*$",
    )
    description: ShortText
    risk: ToolRisk
    input_schema: dict[str, JsonValue]
    output_schema: dict[str, JsonValue] | None = None


class ProviderToolCall(BaseModel):
    """Structured call proposed by a provider; never executable by itself."""

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
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class ProviderAssistantMessage(BaseModel):
    """One validated assistant turn retained for a bounded tool loop."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["assistant"] = "assistant"
    content: str = Field(default="", max_length=4000)
    tool_calls: tuple[ProviderToolCall, ...] = Field(max_length=8)


class ProviderToolResultMessage(BaseModel):
    """A safe structured tool result returned to the provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["tool"] = "tool"
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
    status: Literal["completed", "failed", "cancelled"]
    summary: ShortText
    result: JsonValue = None
    error_code: str | None = Field(
        default=None,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_]*$",
    )

    @model_validator(mode="after")
    def validate_status(self) -> ProviderToolResultMessage:
        if self.status == "completed" and self.error_code is not None:
            raise ValueError("A completed tool message cannot contain an error code.")
        if self.status != "completed" and self.error_code is None:
            raise ValueError("A failed tool message requires an error code.")
        if self.status != "completed" and self.result is not None:
            raise ValueError("A failed tool message cannot contain partial results.")
        return self


ProviderHistoryMessage = Annotated[
    ProviderAssistantMessage | ProviderToolResultMessage,
    Field(discriminator="role"),
]


class ProviderRequest(BaseModel):
    """One bounded planning request sent to an AI provider adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal[PROVIDER_CONTRACT_VERSION] = PROVIDER_CONTRACT_VERSION
    instructions: LongText
    user_message: LongText
    context: dict[str, JsonValue] = Field(default_factory=dict)
    tools: tuple[ProviderToolDefinition, ...] = Field(max_length=128)
    history: tuple[ProviderHistoryMessage, ...] = Field(
        default_factory=tuple,
        max_length=24,
    )
    max_tool_calls: int = Field(ge=0, le=64)


class ProviderResponse(BaseModel):
    """Provider-neutral structured planning response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intention: ShortText
    assumptions: tuple[ShortText, ...] = Field(default_factory=tuple, max_length=16)
    plan: tuple[ShortText, ...] = Field(min_length=1, max_length=32)
    message: str = Field(default="", max_length=4000)
    tool_calls: tuple[ProviderToolCall, ...] = Field(
        default_factory=tuple,
        max_length=64,
    )


class PlannedToolCall(BaseModel):
    """A provider call validated against the authoritative ToolRegistry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    call_id: str
    name: str
    arguments: dict[str, JsonValue]
    risk: ToolRisk
    requires_confirmation: bool


class OrchestrationPlan(BaseModel):
    """Display-ready plan whose calls are validated but not executed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intention: ShortText
    assumptions: tuple[ShortText, ...]
    steps: tuple[ShortText, ...]
    message: str
    tool_calls: tuple[PlannedToolCall, ...]


def tool_definition_from_spec(spec: ToolSpec) -> ProviderToolDefinition:
    return ProviderToolDefinition(
        name=spec.name,
        description=spec.description,
        risk=spec.risk,
        input_schema=deepcopy(spec.input_schema),
        output_schema=deepcopy(spec.output_schema),
    )

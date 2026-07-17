from __future__ import annotations

from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    JsonValue,
    StringConstraints,
)

from aicad.core.tool_registry import ToolRisk


ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]


class PlannedToolCall(BaseModel):
    """A proposed call validated against the authoritative ToolRegistry."""

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

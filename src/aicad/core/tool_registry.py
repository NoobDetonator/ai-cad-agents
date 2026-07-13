from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable


class ToolRisk(StrEnum):
    READ = "read"
    MODIFY = "modify"
    EXPORT = "export"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    risk: ToolRisk
    input_schema: dict[str, Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}

    def register(
        self, spec: ToolSpec, handler: Callable[..., Any] | None = None
    ) -> None:
        if spec.name in self._specs:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._specs[spec.name] = spec
        if handler is not None:
            self._handlers[spec.name] = handler

    def list_specs(self) -> tuple[ToolSpec, ...]:
        return tuple(self._specs.values())

    def execute(self, name: str, **arguments: Any) -> Any:
        if name not in self._specs:
            raise KeyError(f"Unknown tool: {name}")
        if name not in self._handlers:
            raise RuntimeError(f"Tool has no connected handler: {name}")
        return self._handlers[name](**arguments)


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    empty_object = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    registry.register(
        ToolSpec(
            name="cad.get_document_summary",
            description="Read the active CAD document and its object tree.",
            risk=ToolRisk.READ,
            input_schema=empty_object,
        )
    )
    registry.register(
        ToolSpec(
            name="cad.get_selection",
            description="Read the objects, faces and edges selected by the user.",
            risk=ToolRisk.READ,
            input_schema=empty_object,
        )
    )
    registry.register(
        ToolSpec(
            name="cad.create_box",
            description="Create a parametric box in a reversible transaction.",
            risk=ToolRisk.MODIFY,
            input_schema={
                "type": "object",
                "properties": {
                    "length": {"type": "number", "exclusiveMinimum": 0},
                    "width": {"type": "number", "exclusiveMinimum": 0},
                    "height": {"type": "number", "exclusiveMinimum": 0},
                    "name": {"type": "string"},
                },
                "required": ["length", "width", "height", "name"],
                "additionalProperties": False,
            },
        )
    )
    registry.register(
        ToolSpec(
            name="cad.validate_document",
            description="Recompute and report document and shape errors.",
            risk=ToolRisk.READ,
            input_schema=empty_object,
        )
    )
    registry.register(
        ToolSpec(
            name="cad.undo",
            description="Undo the last committed CAD transaction.",
            risk=ToolRisk.MODIFY,
            input_schema=empty_object,
        )
    )
    return registry

from __future__ import annotations

from typing import Any, Protocol

from aicad.core.tool_registry import ToolRegistry, build_default_registry


class CadAdapter(Protocol):
    """CAD boundary expected by the application layer."""

    def get_document_summary(self) -> dict[str, Any]: ...

    def get_selection(self) -> dict[str, Any]: ...

    def get_context_snapshot(
        self,
        detail_level: str = "work",
        max_objects: int = 25,
        cursor: int = 0,
    ) -> dict[str, Any]: ...

    def create_box(
        self, length: float, width: float, height: float, name: str = "AIBox"
    ) -> dict[str, Any]: ...

    def create_cylinder(
        self, diameter: float, height: float, name: str = "AICylinder"
    ) -> dict[str, Any]: ...

    def validate_document(self) -> dict[str, Any]: ...

    def undo(self) -> dict[str, bool]: ...


def build_cad_tool_registry(adapter: CadAdapter) -> ToolRegistry:
    """Connect the provider-independent catalog to one explicit CAD adapter."""

    registry = build_default_registry()
    registry.bind("cad.get_document_summary", adapter.get_document_summary)
    registry.bind("cad.get_selection", adapter.get_selection)
    registry.bind("cad.get_context_snapshot", adapter.get_context_snapshot)
    registry.bind("cad.create_box", adapter.create_box)
    registry.bind("cad.create_cylinder", adapter.create_cylinder)
    registry.bind("cad.validate_document", adapter.validate_document)
    registry.bind("cad.undo", adapter.undo)
    return registry

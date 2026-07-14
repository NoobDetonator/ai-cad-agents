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

    def get_object_details(self, object: str) -> dict[str, Any]: ...

    def measure_object(self, object: str) -> dict[str, Any]: ...

    def get_dependencies(self, object: str) -> dict[str, Any]: ...

    def resolve_object(self, reference: str = "") -> dict[str, Any]: ...

    def get_editable_parameters(self, object: str) -> dict[str, Any]: ...

    def capture_view(self, width: int = 960, height: int = 640) -> dict[str, Any]: ...

    def create_box(
        self, length: float, width: float, height: float, name: str = "AIBox"
    ) -> dict[str, Any]: ...

    def create_cylinder(
        self, diameter: float, height: float, name: str = "AICylinder"
    ) -> dict[str, Any]: ...

    def rename_object(self, object: str, name: str) -> dict[str, Any]: ...

    def set_parameter(
        self, object: str, parameter: str, value: float
    ) -> dict[str, Any]: ...

    def transform_object(
        self,
        object: str,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
        roll: float | None = None,
        pitch: float | None = None,
        yaw: float | None = None,
    ) -> dict[str, Any]: ...

    def create_plate(
        self, length: float, width: float, thickness: float, name: str = "AIPlate"
    ) -> dict[str, Any]: ...

    def create_through_hole(
        self,
        object: str,
        diameter: float,
        x: float,
        y: float,
        name: str = "AIThroughHole",
    ) -> dict[str, Any]: ...

    def create_rectangular_hole_pattern(self, **arguments: Any) -> dict[str, Any]: ...

    def create_circular_hole_pattern(self, **arguments: Any) -> dict[str, Any]: ...

    def create_rectangular_sketch(
        self, width: float, height: float, name: str = "AIRectangleSketch"
    ) -> dict[str, Any]: ...

    def pad_sketch(
        self, sketch: str, length: float, name: str = "AIPad"
    ) -> dict[str, Any]: ...

    def boolean_operation(
        self, left: str, right: str, operation: str, name: str = "AIBoolean"
    ) -> dict[str, Any]: ...

    def fillet_edges(
        self, object: str, radius: float, edge_reference: str, name: str = "AIFillet"
    ) -> dict[str, Any]: ...

    def chamfer_edges(
        self, object: str, size: float, edge_reference: str, name: str = "AIChamfer"
    ) -> dict[str, Any]: ...

    def validate_document(self) -> dict[str, Any]: ...

    def undo(self) -> dict[str, bool]: ...


def build_cad_tool_registry(adapter: CadAdapter) -> ToolRegistry:
    """Connect the provider-independent catalog to one explicit CAD adapter."""

    registry = build_default_registry()

    def bind(tool_name: str, method_name: str) -> None:
        handler = getattr(adapter, method_name, None)
        if handler is None:
            def unavailable(**_: Any) -> Any:
                raise RuntimeError(
                    f"The active CAD adapter does not provide {tool_name}."
                )

            handler = unavailable
        registry.bind(tool_name, handler)

    bindings = {
        "cad.get_document_summary": "get_document_summary",
        "cad.get_selection": "get_selection",
        "cad.get_context_snapshot": "get_context_snapshot",
        "cad.get_object_details": "get_object_details",
        "cad.measure_object": "measure_object",
        "cad.get_dependencies": "get_dependencies",
        "cad.resolve_object": "resolve_object",
        "cad.get_editable_parameters": "get_editable_parameters",
        "cad.capture_view": "capture_view",
        "cad.create_box": "create_box",
        "cad.create_cylinder": "create_cylinder",
        "cad.rename_object": "rename_object",
        "cad.set_parameter": "set_parameter",
        "cad.transform_object": "transform_object",
        "cad.create_plate": "create_plate",
        "cad.create_through_hole": "create_through_hole",
        "cad.create_rectangular_hole_pattern": "create_rectangular_hole_pattern",
        "cad.create_circular_hole_pattern": "create_circular_hole_pattern",
        "cad.create_rectangular_sketch": "create_rectangular_sketch",
        "cad.pad_sketch": "pad_sketch",
        "cad.boolean_operation": "boolean_operation",
        "cad.fillet_edges": "fillet_edges",
        "cad.chamfer_edges": "chamfer_edges",
        "cad.validate_document": "validate_document",
        "cad.undo": "undo",
    }
    for tool_name, method_name in bindings.items():
        bind(tool_name, method_name)
    return registry

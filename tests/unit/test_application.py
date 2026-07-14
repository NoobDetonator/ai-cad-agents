from typing import Any

from aicad.application import build_cad_tool_registry


class FakeCadAdapter:
    def get_document_summary(self) -> dict[str, Any]:
        return {"active": False}

    def get_selection(self) -> dict[str, Any]:
        return {"selection": []}

    def get_context_snapshot(
        self,
        detail_level: str = "work",
        max_objects: int = 25,
        cursor: int = 0,
    ) -> dict[str, Any]:
        return {
            "detail_level": detail_level,
            "max_objects": max_objects,
            "cursor": cursor,
        }

    def create_box(
        self, length: float, width: float, height: float, name: str = "AIBox"
    ) -> dict[str, Any]:
        return {"name": name, "dimensions": [length, width, height]}

    def create_cylinder(
        self, diameter: float, height: float, name: str = "AICylinder"
    ) -> dict[str, Any]:
        return {"name": name, "diameter": diameter, "height": height}

    def validate_document(self) -> dict[str, Any]:
        return {"valid": True, "errors": []}

    def undo(self) -> dict[str, bool]:
        return {"undone": True}


def test_application_connects_cad_tools_while_runtime_owns_audit_handlers() -> None:
    registry = build_cad_tool_registry(FakeCadAdapter())
    runtime_tools = {"cad.get_audit_history", "cad.export_audit_history"}
    assert all(
        registry.has_handler(spec.name)
        for spec in registry.list_specs()
        if spec.name not in runtime_tools
    )
    assert all(not registry.has_handler(name) for name in runtime_tools)
    result = registry.execute(
        "cad.create_box",
        {"length": 1, "width": 2, "height": 3, "name": "TestBox"},
        confirmed=True,
    )
    assert result == {"name": "TestBox", "dimensions": [1, 2, 3]}

    cylinder = registry.execute(
        "cad.create_cylinder",
        {"diameter": 20, "height": 50, "name": "TestCylinder"},
        confirmed=True,
    )
    assert cylinder == {"name": "TestCylinder", "diameter": 20, "height": 50}

    context = registry.execute(
        "cad.get_context_snapshot",
        {"detail_level": "minimal", "max_objects": 10, "cursor": 0},
    )
    assert context == {
        "detail_level": "minimal",
        "max_objects": 10,
        "cursor": 0,
    }

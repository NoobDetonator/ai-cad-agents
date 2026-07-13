import pytest

from aicad.core.tool_registry import ToolRegistry, ToolRisk, ToolSpec, build_default_registry


def test_default_registry_has_unique_tools() -> None:
    names = [spec.name for spec in build_default_registry().list_specs()]
    assert len(names) == len(set(names))
    assert "cad.create_box" in names


def test_registry_executes_connected_handler() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="test.add",
            description="Add two numbers.",
            risk=ToolRisk.READ,
            input_schema={},
        ),
        handler=lambda left, right: left + right,
    )
    assert registry.execute("test.add", left=2, right=3) == 5


def test_registry_rejects_duplicate_names() -> None:
    registry = ToolRegistry()
    spec = ToolSpec("test.duplicate", "Duplicate", ToolRisk.READ, {})
    registry.register(spec)
    with pytest.raises(ValueError):
        registry.register(spec)

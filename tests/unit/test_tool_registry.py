import pytest

from aicad.core.tool_registry import (
    ToolConfirmationRequired,
    ToolInputError,
    ToolRegistry,
    ToolRisk,
    ToolSpec,
    build_default_registry,
)


def test_default_registry_has_unique_tools() -> None:
    specs = build_default_registry().list_specs()
    names = [spec.name for spec in specs]
    assert len(names) == len(set(names))
    assert len({spec.canonical_order for spec in specs}) == len(specs)
    assert "cad.create_box" in names
    assert "cad.create_cylinder" in names
    assert "cad.get_context_snapshot" in names
    assert all(spec.aliases and spec.tags and spec.examples for spec in specs)
    assert [spec.name for spec in specs if spec.essential] == [
        "cad.get_context_snapshot"
    ]


def test_registry_executes_connected_handler() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="test.add",
            description="Add two numbers.",
            risk=ToolRisk.READ,
            input_schema={
                "type": "object",
                "properties": {
                    "left": {"type": "number"},
                    "right": {"type": "number"},
                },
                "required": ["left", "right"],
                "additionalProperties": False,
            },
        ),
        handler=lambda left, right: left + right,
    )
    assert registry.execute("test.add", {"left": 2, "right": 3}) == 5


def test_registry_rejects_duplicate_names() -> None:
    registry = ToolRegistry()
    spec = ToolSpec("test.duplicate", "Duplicate", ToolRisk.READ, {})
    registry.register(spec)
    with pytest.raises(ValueError):
        registry.register(spec)


def test_registry_validates_arguments_before_calling_handler() -> None:
    registry = build_default_registry()
    registry.bind("cad.create_box", lambda **arguments: arguments)
    with pytest.raises(ToolInputError):
        registry.execute(
            "cad.create_box",
            {"length": 10, "width": 20, "height": -1},
            confirmed=True,
        )
    with pytest.raises(ToolInputError):
        registry.execute(
            "cad.create_box",
            {"length": 10, "width": 20, "height": 30, "python": "print(1)"},
            confirmed=True,
        )


def test_registry_rejects_invalid_cylinder_dimensions() -> None:
    registry = build_default_registry()
    registry.bind("cad.create_cylinder", lambda **arguments: arguments)

    with pytest.raises(ToolInputError):
        registry.execute(
            "cad.create_cylinder",
            {"diameter": 0, "height": 60},
            confirmed=True,
        )


def test_registry_requires_confirmation_for_modifications() -> None:
    registry = build_default_registry()
    registry.bind("cad.undo", lambda: {"undone": True})
    with pytest.raises(ToolConfirmationRequired):
        registry.execute("cad.undo")
    assert registry.execute("cad.undo", confirmed=True) == {"undone": True}


def test_registry_can_validate_a_call_without_a_handler() -> None:
    registry = build_default_registry()

    assert registry.validate_arguments(
        "cad.create_box",
        {"length": 10, "width": 20, "height": 30},
    ) == {"length": 10, "width": 20, "height": 30}

    assert registry.validate_arguments(
        "cad.create_cylinder",
        {"diameter": 30, "height": 60, "name": "Shaft"},
    ) == {"diameter": 30, "height": 60, "name": "Shaft"}

    with pytest.raises(ToolInputError):
        registry.validate_arguments("cad.undo", ["not", "an", "object"])


def test_registry_validates_context_pagination_and_detail_level() -> None:
    registry = build_default_registry()

    assert registry.validate_arguments(
        "cad.get_context_snapshot",
        {"detail_level": "work", "max_objects": 25, "cursor": 0},
    ) == {"detail_level": "work", "max_objects": 25, "cursor": 0}

    for arguments in (
        {"detail_level": "full"},
        {"max_objects": 0},
        {"max_objects": 101},
        {"max_objects": 1.5},
        {"cursor": -1},
        {"cursor": True},
    ):
        with pytest.raises(ToolInputError):
            registry.validate_arguments("cad.get_context_snapshot", arguments)

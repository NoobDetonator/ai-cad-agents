import pytest

from aicad.core.tool_catalog import CATALOG_BUILDERS, default_tool_specs
from aicad.core.tool_registry import (
    ToolConfirmationRequired,
    ToolInputError,
    ToolRegistry,
    ToolRisk,
    ToolSpec,
    build_default_registry,
)


EXPECTED_CATALOG_FAMILIES = {
    "aicad.core.tool_catalog.assembly": {"analysis", "assembly"},
    "aicad.core.tool_catalog.bearings": {"bearing"},
    "aicad.core.tool_catalog.context": {"context", "measurement"},
    "aicad.core.tool_catalog.documents": {"document", "export"},
    "aicad.core.tool_catalog.editing": {"edit"},
    "aicad.core.tool_catalog.governance": {"history", "validation"},
    "aicad.core.tool_catalog.mechanical": {"mechanical"},
    "aicad.core.tool_catalog.modeling": {
        "boolean",
        "feature",
        "finish",
        "sketch",
    },
    "aicad.core.tool_catalog.objects": {"object"},
    "aicad.core.tool_catalog.patterns": {"pattern"},
    "aicad.core.tool_catalog.primitives": {"primitive"},
    "aicad.core.tool_catalog.sketching": {"sketch"},
}


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
    assert len(specs) == 90
    audit_names = {"cad.get_audit_history", "cad.export_audit_history"}
    assert {spec.name for spec in specs if spec.name in audit_names} == audit_names
    export_names = {spec.name for spec in specs if spec.family == "export"}
    assert export_names == {"cad.export_stl", "cad.export_step"}
    document_names = {spec.name for spec in specs if spec.family == "document"}
    assert document_names == {
        "cad.list_documents",
        "cad.new_document",
        "cad.set_active_document",
        "cad.save_document",
    }
    mechanical_families = {
        "measurement",
        "edit",
        "mechanical",
        "feature",
        "pattern",
        "sketch",
        "boolean",
        "finish",
        "assembly",
        "analysis",
        "bearing",
    }
    mechanical_specs = [
        spec for spec in specs if spec.family in mechanical_families
    ]
    assert len(mechanical_specs) == 65
    assert all(spec.output_schema is not None for spec in mechanical_specs)
    assert any(
        spec.name == "cad.create_external_thread" and spec.family == "mechanical"
        for spec in specs
    )


def test_tool_catalog_is_split_into_domain_modules() -> None:
    modules = {builder.__module__: builder for builder in CATALOG_BUILDERS}

    assert modules.keys() == EXPECTED_CATALOG_FAMILIES.keys()
    for module_name, builder in modules.items():
        specs = builder()
        assert specs
        assert {spec.family for spec in specs} == EXPECTED_CATALOG_FAMILIES[module_name]

    catalog_names = [spec.name for spec in default_tool_specs()]
    registry_names = [spec.name for spec in build_default_registry().list_specs()]
    assert catalog_names == registry_names


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


def test_registry_rejects_invalid_spur_gear_parameters() -> None:
    registry = build_default_registry()

    for arguments in (
        {"teeth": 5, "module": 2, "thickness": 8, "bore_diameter": 8},
        {"teeth": 20, "module": 0, "thickness": 8, "bore_diameter": 8},
        {"teeth": 20, "module": 2, "thickness": 8, "bore_diameter": -1},
        {
            "teeth": 20,
            "module": 2,
            "thickness": 8,
            "bore_diameter": 8,
            "pressure_angle": 30,
        },
    ):
        with pytest.raises(ToolInputError):
            registry.validate_arguments("cad.create_spur_gear", arguments)


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

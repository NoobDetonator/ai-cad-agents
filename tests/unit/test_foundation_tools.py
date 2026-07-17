import pytest

from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.core.tool_registry import ToolInputError, ToolRisk, build_default_registry
from aicad.ui.talos_panel import automatic_approval_default


FOUNDATION_TOOLS = (
    "cad.create_cone",
    "cad.create_sphere",
    "cad.create_torus",
    "cad.measure_distance",
    "cad.duplicate_object",
    "cad.delete_object",
    "cad.translate_object",
    "cad.rotate_object",
)


def test_foundation_specs_have_risk_and_output_contracts() -> None:
    registry = build_default_registry()

    assert len(registry.list_specs()) == 115
    for name in FOUNDATION_TOOLS:
        spec = registry.get_spec(name)
        assert spec.output_schema is not None
        expected = ToolRisk.READ if name == "cad.measure_distance" else ToolRisk.MODIFY
        assert spec.risk is expected


def test_foundation_primitive_schemas_bound_dimensions() -> None:
    registry = build_default_registry()

    assert registry.validate_arguments(
        "cad.create_cone",
        {"bottom_diameter": 30, "top_diameter": 0, "height": 50},
    ) == {"bottom_diameter": 30, "top_diameter": 0, "height": 50}
    assert registry.validate_arguments(
        "cad.create_sphere", {"diameter": 20}
    ) == {"diameter": 20}
    assert registry.validate_arguments(
        "cad.create_torus", {"major_diameter": 40, "tube_diameter": 8}
    ) == {"major_diameter": 40, "tube_diameter": 8}

    for name, arguments in (
        (
            "cad.create_cone",
            {"bottom_diameter": -1, "top_diameter": 0, "height": 50},
        ),
        ("cad.create_sphere", {"diameter": 0}),
        ("cad.create_torus", {"major_diameter": 40, "tube_diameter": 0}),
    ):
        with pytest.raises(ToolInputError):
            registry.validate_arguments(name, arguments)


def test_foundation_edit_schemas_are_explicit() -> None:
    registry = build_default_registry()

    assert registry.validate_arguments(
        "cad.measure_distance", {"left": "Base", "right": "Tampa"}
    ) == {"left": "Base", "right": "Tampa"}
    assert registry.validate_arguments(
        "cad.duplicate_object",
        {"object": "Base", "name": "BaseCopy", "offset_x": 20},
    )["offset_x"] == 20
    assert registry.validate_arguments(
        "cad.translate_object", {"object": "Base", "dx": 10}
    )["dx"] == 10
    assert registry.validate_arguments(
        "cad.rotate_object",
        {"object": "Base", "axis": "z", "angle": 90, "pivot": "object_center"},
    )["pivot"] == "object_center"

    for name, arguments in (
        ("cad.measure_distance", {"left": "Base"}),
        ("cad.duplicate_object", {"object": "Base", "name": "bad name"}),
        ("cad.rotate_object", {"object": "Base", "axis": "w", "angle": 90}),
        ("cad.rotate_object", {"object": "Base", "axis": "z", "angle": 361}),
    ):
        with pytest.raises(ToolInputError):
            registry.validate_arguments(name, arguments)


def test_adapter_rejects_invalid_foundation_arguments_before_freecad() -> None:
    adapter = FreeCadAdapter()

    with pytest.raises(ValueError, match="At least one cone diameter"):
        adapter.create_cone(0, 0, 20)
    with pytest.raises(ValueError, match="major diameter"):
        adapter.create_torus(8, 8)
    with pytest.raises(ValueError, match="non-zero"):
        adapter.translate_object("Base", 0, 0, 0)
    with pytest.raises(ValueError, match="axis"):
        adapter.rotate_object("Base", "w", 90)
    with pytest.raises(ValueError, match="non-zero rotation"):
        adapter.rotate_object("Base", "z", 360)
    with pytest.raises(ValueError, match="finite"):
        adapter.duplicate_object("Base", "BaseCopy", offset_x=float("nan"))


def test_automatic_approval_is_the_visible_default_with_explicit_opt_out() -> None:
    assert automatic_approval_default({}) is False
    assert automatic_approval_default({"TALOS_AUTO_APPROVE": "1"}) is True
    assert automatic_approval_default({"TALOS_AUTO_APPROVE": "0"}) is False

import pytest

from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.core.tool_registry import ToolInputError, ToolRisk, build_default_registry


SKETCH_ENVIRONMENT_TOOLS = {
    "cad.create_empty_sketch",
    "cad.add_sketch_line",
    "cad.add_sketch_polyline",
    "cad.add_sketch_circle",
    "cad.add_sketch_arc",
    "cad.add_sketch_ellipse",
    "cad.add_sketch_rectangle",
    "cad.add_sketch_slot",
    "cad.add_sketch_regular_polygon",
    "cad.add_sketch_external_geometry",
    "cad.add_sketch_geometric_constraint",
    "cad.add_sketch_dimensional_constraint",
    "cad.set_sketch_constraint_value",
    "cad.set_sketch_constraint_driving",
    "cad.move_sketch_point",
    "cad.toggle_sketch_construction",
    "cad.delete_sketch_geometry",
    "cad.delete_sketch_constraint",
    "cad.trim_sketch_geometry",
    "cad.extend_sketch_geometry",
    "cad.fillet_sketch_corner",
    "cad.copy_sketch_geometry",
    "cad.mirror_sketch_geometry",
    "cad.get_sketch_info",
}


def test_sketch_environment_is_a_complete_catalog_family() -> None:
    registry = build_default_registry()
    specs = {spec.name: spec for spec in registry.list_specs()}

    assert len(registry.list_specs()) == 91
    assert SKETCH_ENVIRONMENT_TOOLS <= specs.keys()
    assert len(SKETCH_ENVIRONMENT_TOOLS) == 24
    for name in SKETCH_ENVIRONMENT_TOOLS:
        spec = specs[name]
        assert spec.family == "sketch"
        assert spec.output_schema is not None
        expected_risk = ToolRisk.READ if name == "cad.get_sketch_info" else ToolRisk.MODIFY
        assert spec.risk is expected_risk


def test_sketch_creation_and_constraint_schemas_accept_structured_calls() -> None:
    registry = build_default_registry()

    assert registry.validate_arguments(
        "cad.create_empty_sketch", {"plane": "xz", "offset": 12.5, "name": "Profile"}
    )["plane"] == "xz"
    assert registry.validate_arguments(
        "cad.add_sketch_polyline",
        {"sketch": "Profile", "points": ["0,0", "40,0", "20,25"], "closed": True},
    )["closed"] is True
    assert registry.validate_arguments(
        "cad.add_sketch_geometric_constraint",
        {
            "sketch": "Profile",
            "constraint_type": "coincident",
            "first_geometry": 0,
            "first_position": "end",
            "second_geometry": 1,
            "second_position": "start",
        },
    )["constraint_type"] == "coincident"
    assert registry.validate_arguments(
        "cad.add_sketch_dimensional_constraint",
        {"sketch": "Profile", "constraint_type": "diameter", "geometry": 4, "value": 20},
    )["value"] == 20


@pytest.mark.parametrize(
    ("name", "arguments"),
    (
        ("cad.create_empty_sketch", {"plane": "oblique"}),
        ("cad.add_sketch_polyline", {"sketch": "S", "points": ["0,0", "not-a-point"]}),
        ("cad.add_sketch_regular_polygon", {"sketch": "S", "center_x": 0, "center_y": 0, "radius": 5, "sides": 2}),
        ("cad.add_sketch_geometric_constraint", {"sketch": "S", "constraint_type": "fixed-ish", "first_geometry": 0}),
        ("cad.add_sketch_dimensional_constraint", {"sketch": "S", "constraint_type": "radius", "geometry": 0, "value": 0}),
        ("cad.toggle_sketch_construction", {"sketch": "S", "geometry_indices": [0, 0]}),
        ("cad.delete_sketch_geometry", {"sketch": "S", "geometry_indices": [-1]}),
        ("cad.copy_sketch_geometry", {"sketch": "S", "geometry_indices": [True], "dx": 5, "dy": 0}),
        ("cad.delete_sketch_constraint", {"sketch": "S", "constraint_indices": [8192]}),
    ),
)
def test_sketch_schemas_reject_unsafe_or_ambiguous_calls(
    name: str, arguments: dict
) -> None:
    with pytest.raises(ToolInputError):
        build_default_registry().validate_arguments(name, arguments)


def test_adapter_rejects_invalid_sketch_geometry_before_loading_freecad() -> None:
    adapter = FreeCadAdapter()

    with pytest.raises(ValueError, match="plane"):
        adapter.create_empty_sketch("oblique")
    with pytest.raises(ValueError, match="finite"):
        adapter.create_empty_sketch(offset=float("nan"))
    with pytest.raises(ValueError, match="distinct points"):
        adapter.add_sketch_line("S", 1, 2, 1, 2)
    with pytest.raises(ValueError, match="sweep"):
        adapter.add_sketch_arc("S", 0, 0, 5, 30, 390)
    with pytest.raises(ValueError, match="major radius"):
        adapter.add_sketch_ellipse("S", 0, 0, 5, 5)
    with pytest.raises(ValueError, match="distinct center points"):
        adapter.add_sketch_slot("S", 0, 0, 0, 0, 6)
    with pytest.raises(ValueError, match="3 to 128"):
        adapter.add_sketch_regular_polygon("S", 0, 0, 5, 129)

import pytest

from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.core.tool_registry import ToolInputError, ToolRisk, build_default_registry


ASSEMBLY_TOOLS = (
    "cad.create_internal_gear",
    "cad.create_planetary_carrier",
    "cad.create_ball_bearing",
    "cad.apply_gear_backlash",
    "cad.align_concentric",
    "cad.analyze_interferences",
)


def test_assembly_specs_are_complete_and_safely_classified() -> None:
    registry = build_default_registry()

    assert len(registry.list_specs()) == 91
    for name in ASSEMBLY_TOOLS:
        spec = registry.get_spec(name)
        assert spec.output_schema is not None
        expected = ToolRisk.READ if name == "cad.analyze_interferences" else ToolRisk.MODIFY
        assert spec.risk is expected


def test_assembly_schemas_accept_realistic_planetary_values() -> None:
    registry = build_default_registry()

    assert registry.validate_arguments(
        "cad.create_internal_gear",
        {"teeth": 48, "module": 2, "thickness": 12, "rim_thickness": 8},
    )["teeth"] == 48
    assert registry.validate_arguments(
        "cad.create_planetary_carrier",
        {
            "plate_diameter": 92,
            "thickness": 6,
            "center_bore_diameter": 12,
            "planet_count": 3,
            "planet_pitch_diameter": 72,
            "pin_hole_diameter": 6.2,
        },
    )["planet_count"] == 3
    assert registry.validate_arguments(
        "cad.create_ball_bearing",
        {
            "bore_diameter": 12,
            "outer_diameter": 32,
            "width": 10,
            "ball_count": 8,
            "ball_diameter": 5,
            "radial_clearance": 0.05,
        },
    )["radial_clearance"] == 0.05
    assert registry.validate_arguments(
        "cad.analyze_interferences",
        {
            "objects": ["Sun", "Planet", "Ring"],
            "minimum_clearance": 0.1,
            "volume_tolerance": 0.05,
        },
    )["objects"] == ["Sun", "Planet", "Ring"]


def test_assembly_schemas_reject_unsafe_or_ambiguous_inputs() -> None:
    registry = build_default_registry()

    for name, arguments in (
        (
            "cad.create_internal_gear",
            {"teeth": 8, "module": 2, "thickness": 12, "rim_thickness": 8},
        ),
        (
            "cad.create_planetary_carrier",
            {
                "plate_diameter": 90,
                "thickness": 6,
                "center_bore_diameter": 12,
                "planet_count": 1,
                "planet_pitch_diameter": 72,
                "pin_hole_diameter": 6,
            },
        ),
        (
            "cad.align_concentric",
            {"moving": "Bearing", "reference": "Shaft", "z_alignment": "side"},
        ),
        (
            "cad.analyze_interferences",
            {"objects": ["OnlyOne"]},
        ),
    ):
        with pytest.raises(ToolInputError):
            registry.validate_arguments(name, arguments)


def test_adapter_rejects_invalid_assembly_geometry_before_freecad() -> None:
    adapter = FreeCadAdapter()

    with pytest.raises(ValueError, match="rim"):
        adapter.create_internal_gear(48, 2, 12, 1)
    with pytest.raises(ValueError, match="edge wall"):
        adapter.create_planetary_carrier(70, 6, 12, 3, 72, 6)
    with pytest.raises(ValueError, match="outer diameter"):
        adapter.create_ball_bearing(32, 12, 10, 8, 5)
    with pytest.raises(ValueError, match="between 4 and 64"):
        adapter.create_ball_bearing(12, 32, 10, 3, 5)
    with pytest.raises(ValueError, match="2 to 32"):
        adapter.analyze_interferences(["OnlyOne"])

from __future__ import annotations

import pytest

from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.core.tool_registry import ToolInputError, ToolRisk, build_default_registry


BEARING_TOOLS = (
    "cad.create_deep_groove_ball_bearing",
    "cad.create_thrust_ball_bearing",
    "cad.create_cylindrical_roller_bearing",
    "cad.create_print_in_place_roller_bearing",
    "cad.create_printed_plain_bushing",
)


def test_bearing_specs_are_complete_and_modifying() -> None:
    registry = build_default_registry()

    assert len(registry.list_specs()) == 117
    for name in BEARING_TOOLS:
        spec = registry.get_spec(name)
        assert spec.family == "bearing"
        assert spec.risk is ToolRisk.MODIFY
        assert spec.output_schema is not None


def test_bearing_schemas_accept_conventional_and_printed_designs() -> None:
    registry = build_default_registry()

    deep = registry.validate_arguments(
        "cad.create_deep_groove_ball_bearing",
        {
            "bore_diameter": 12,
            "outer_diameter": 32,
            "width": 10,
            "ball_count": 8,
            "ball_diameter": 5,
            "radial_clearance": 0.05,
            "groove_conformity": 1.04,
            "cage": True,
        },
    )
    assert deep["groove_conformity"] == 1.04

    thrust = registry.validate_arguments(
        "cad.create_thrust_ball_bearing",
        {
            "bore_diameter": 20,
            "outer_diameter": 42,
            "height": 14,
            "ball_count": 8,
            "ball_diameter": 6,
        },
    )
    assert thrust["height"] == 14

    roller = registry.validate_arguments(
        "cad.create_cylindrical_roller_bearing",
        {
            "bore_diameter": 20,
            "outer_diameter": 47,
            "width": 14,
            "roller_count": 12,
            "roller_diameter": 6,
            "roller_length": 11,
        },
    )
    assert roller["roller_count"] == 12

    printed = registry.validate_arguments(
        "cad.create_print_in_place_roller_bearing",
        {
            "bore_diameter": 20,
            "outer_diameter": 50,
            "width": 16,
            "roller_count": 12,
            "roller_diameter": 6,
            "print_clearance": 0.4,
            "axial_clearance": 1.8,
        },
    )
    assert printed["print_clearance"] == 0.4

    bushing = registry.validate_arguments(
        "cad.create_printed_plain_bushing",
        {
            "shaft_diameter": 12,
            "outer_diameter": 18,
            "length": 20,
            "running_clearance": 0.4,
            "channel_count": 6,
        },
    )
    assert bushing["channel_count"] == 6


def test_bearing_schemas_reject_invalid_ranges_and_unknown_parameters() -> None:
    registry = build_default_registry()

    for name, arguments in (
        (
            "cad.create_deep_groove_ball_bearing",
            {
                "bore_diameter": 12,
                "outer_diameter": 32,
                "width": 10,
                "ball_count": 3,
                "ball_diameter": 5,
            },
        ),
        (
            "cad.create_thrust_ball_bearing",
            {
                "bore_diameter": 20,
                "outer_diameter": 42,
                "height": 14,
                "ball_count": 8,
                "ball_diameter": 6,
                "groove_conformity": 1.5,
            },
        ),
        (
            "cad.create_printed_plain_bushing",
            {
                "shaft_diameter": 12,
                "outer_diameter": 18,
                "length": 20,
                "python": "print('unsafe')",
            },
        ),
    ):
        with pytest.raises(ToolInputError):
            registry.validate_arguments(name, arguments)


def test_adapter_rejects_impossible_bearings_before_loading_freecad() -> None:
    adapter = FreeCadAdapter()

    with pytest.raises(ValueError, match="outer diameter"):
        adapter.create_deep_groove_ball_bearing(32, 12, 10, 8, 5)
    with pytest.raises(ValueError, match="height"):
        adapter.create_thrust_ball_bearing(20, 42, 6, 8, 6, 0.1)
    with pytest.raises(ValueError, match="Roller length"):
        adapter.create_cylindrical_roller_bearing(20, 47, 14, 12, 6, 14)
    with pytest.raises(ValueError, match="retaining-rim"):
        adapter.create_print_in_place_roller_bearing(20, 50, 16, 12, 6, 0.4, 1)
    with pytest.raises(ValueError, match="insufficient bushing wall"):
        adapter.create_printed_plain_bushing(12, 18, 20, 0.4, 6, 0.8, 2)

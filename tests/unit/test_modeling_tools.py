import pytest

from aicad.adapters.freecad.sweeps import _planned_corner_arcs
from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.core.tool_registry import (
    ToolInputError,
    ToolRisk,
    build_default_registry,
)


def test_modeling_specs_are_reversible_mutations() -> None:
    registry = build_default_registry()
    for name in (
        "cad.create_circular_sketch",
        "cad.revolve_sketch",
        "cad.loft_sketches",
        "cad.create_helical_gear",
        "cad.create_external_thread",
    ):
        spec = registry.get_spec(name)
        assert spec.risk is ToolRisk.MODIFY
        assert spec.output_schema is not None


def test_loft_schema_validates_the_sketch_list() -> None:
    registry = build_default_registry()
    with pytest.raises(ToolInputError):
        registry.validate_arguments("cad.loft_sketches", {"sketches": "Perfil"})
    with pytest.raises(ToolInputError):
        registry.validate_arguments("cad.loft_sketches", {"sketches": ["Perfil"]})
    with pytest.raises(ToolInputError):
        registry.validate_arguments(
            "cad.loft_sketches", {"sketches": ["A", "B", 3]}
        )
    with pytest.raises(ToolInputError):
        registry.validate_arguments(
            "cad.loft_sketches", {"sketches": [f"S{i}" for i in range(9)]}
        )
    checked = registry.validate_arguments(
        "cad.loft_sketches", {"sketches": ["Base", "Topo"], "ruled": True}
    )
    assert checked["sketches"] == ["Base", "Topo"]


def test_revolve_schema_bounds_angle_and_axis() -> None:
    registry = build_default_registry()
    for arguments in (
        {"sketch": "Perfil", "angle": 0},
        {"sketch": "Perfil", "angle": 361},
        {"sketch": "Perfil", "axis": "z"},
    ):
        with pytest.raises(ToolInputError):
            registry.validate_arguments("cad.revolve_sketch", arguments)


def test_helical_gear_schema_bounds_parameters() -> None:
    registry = build_default_registry()
    base = {
        "teeth": 24,
        "module": 2,
        "thickness": 8,
        "helix_angle": 15,
        "bore_diameter": 8,
    }
    assert registry.validate_arguments("cad.create_helical_gear", base) == base
    for overrides in (
        {"teeth": 5},
        {"helix_angle": 46},
        {"helix_angle": -46},
        {"bore_diameter": -1},
        {"pressure_angle": 30},
    ):
        with pytest.raises(ToolInputError):
            registry.validate_arguments(
                "cad.create_helical_gear", {**base, **overrides}
            )


def test_adapter_validates_modeling_arguments_before_freecad() -> None:
    adapter = FreeCadAdapter()
    with pytest.raises(ValueError, match="within"):
        adapter.revolve_sketch("Perfil", angle=0)
    with pytest.raises(ValueError, match="axis"):
        adapter.revolve_sketch("Perfil", axis="z")
    with pytest.raises(ValueError, match="at least two"):
        adapter.loft_sketches(["Perfil"])
    with pytest.raises(ValueError, match="helix angle"):
        adapter.create_helical_gear(24, 2, 8, 0.5, 8)
    with pytest.raises(ValueError, match="root diameter"):
        adapter.create_helical_gear(10, 1, 5, 15, 20)
    with pytest.raises(ValueError, match="quarter"):
        adapter.create_external_thread(8, 3, 10)
    with pytest.raises(ValueError, match="one pitch"):
        adapter.create_external_thread(8, 1.25, 1)
    with pytest.raises(ValueError, match="64 turns"):
        adapter.create_external_thread(8, 0.5, 100)


def test_counterbore_and_countersink_specs_are_reversible_mutations() -> None:
    registry = build_default_registry()
    for name in (
        "cad.create_counterbore_hole",
        "cad.create_countersunk_hole",
        "cad.create_sweep_path",
        "cad.sweep_sketch",
    ):
        spec = registry.get_spec(name)
        assert spec.risk is ToolRisk.MODIFY
        assert spec.output_schema is not None


def test_counterbore_schema_bounds_parameters() -> None:
    registry = build_default_registry()
    base = {
        "object": "Base",
        "diameter": 6,
        "x": 20,
        "y": 20,
        "counterbore_diameter": 11,
        "counterbore_depth": 4,
    }
    assert registry.validate_arguments("cad.create_counterbore_hole", base) == base
    for overrides in (
        {"diameter": 0},
        {"counterbore_diameter": 0},
        {"counterbore_depth": -1},
    ):
        with pytest.raises(ToolInputError):
            registry.validate_arguments(
                "cad.create_counterbore_hole", {**base, **overrides}
            )


def test_countersink_schema_bounds_angle() -> None:
    registry = build_default_registry()
    base = {
        "object": "Base",
        "diameter": 6,
        "x": 20,
        "y": 20,
        "countersink_diameter": 12,
    }
    assert registry.validate_arguments("cad.create_countersunk_hole", base) == base
    for overrides in ({"countersink_angle": 59}, {"countersink_angle": 121}):
        with pytest.raises(ToolInputError):
            registry.validate_arguments(
                "cad.create_countersunk_hole", {**base, **overrides}
            )


def test_adapter_validates_recessed_holes_before_freecad() -> None:
    adapter = FreeCadAdapter()
    with pytest.raises(ValueError, match="exceed the hole diameter"):
        adapter.create_counterbore_hole("Base", 6, 0, 0, 6, 4)
    with pytest.raises(ValueError, match="finite"):
        adapter.create_counterbore_hole("Base", 6, float("nan"), 0, 11, 4)
    with pytest.raises(ValueError, match="exceed the hole diameter"):
        adapter.create_countersunk_hole("Base", 6, 0, 0, 5)
    with pytest.raises(ValueError, match="between 60 and 120"):
        adapter.create_countersunk_hole("Base", 6, 0, 0, 12, countersink_angle=45)


def test_sweep_path_schema_validates_the_point_list() -> None:
    registry = build_default_registry()
    with pytest.raises(ToolInputError):
        registry.validate_arguments("cad.create_sweep_path", {"points": "0,0,0"})
    with pytest.raises(ToolInputError):
        registry.validate_arguments("cad.create_sweep_path", {"points": ["0,0,0"]})
    with pytest.raises(ToolInputError):
        registry.validate_arguments(
            "cad.create_sweep_path",
            {"points": [f"0,0,{index}" for index in range(17)]},
        )
    checked = registry.validate_arguments(
        "cad.create_sweep_path",
        {"points": ["0,0,0", "0,0,40"], "corner_radius": 5},
    )
    assert checked["points"] == ["0,0,0", "0,0,40"]


def test_adapter_validates_sweep_paths_before_freecad() -> None:
    adapter = FreeCadAdapter()
    with pytest.raises(ValueError, match="between 2 and 16"):
        adapter.create_sweep_path(["0,0,0"])
    with pytest.raises(ValueError, match="x,y,z"):
        adapter.create_sweep_path(["0,0,0", "banana"])
    with pytest.raises(ValueError, match="x,y,z"):
        adapter.create_sweep_path(["0,0,0", "1,2"])
    with pytest.raises(ValueError, match="must be open"):
        adapter.create_sweep_path(["0,0,0", "0,0,40", "0,0,0"])
    with pytest.raises(ValueError, match="distinct"):
        adapter.create_sweep_path(["0,0,0", "0,0,0", "0,0,40"])
    with pytest.raises(ValueError, match="folds back"):
        adapter.create_sweep_path(["0,0,0", "0,0,40", "0,0,10"])
    with pytest.raises(ValueError, match="must fit in half of the adjacent"):
        adapter.create_sweep_path(
            ["0,0,0", "0,0,30", "30,0,30"],
            corner_radius=20,
        )
    with pytest.raises(ValueError, match="cannot be negative"):
        adapter.create_sweep_path(["0,0,0", "0,0,40"], corner_radius=-1)


def test_through_hole_accepts_a_z_window_to_scope_the_cutter() -> None:
    registry = build_default_registry()
    checked = registry.validate_arguments(
        "cad.create_through_hole",
        {
            "object": "Boss",
            "diameter": 40,
            "x": 46,
            "y": -12,
            "z_min": 90,
            "z_max": 120,
        },
    )
    assert checked["z_min"] == 90
    assert checked["z_max"] == 120

    adapter = FreeCadAdapter()
    assert adapter._checked_z_window(None, None) is None
    assert adapter._checked_z_window(90, 120) == (90.0, 120.0)
    with pytest.raises(ValueError, match="both z_min and z_max"):
        adapter._checked_z_window(90, None)
    with pytest.raises(ValueError, match="z_max above z_min"):
        adapter._checked_z_window(120, 90)


def test_corner_radius_that_exactly_fits_is_accepted() -> None:
    # 36 / tan(45 deg) is 36.000000000000014, a few ulps over half of these
    # 72 mm segments, so a bare ">" rejected radii that do fit.
    arcs = _planned_corner_arcs(((0, 0, 0), (0, 0, 72), (72, 0, 72)), 36)

    assert len(arcs) == 1
    assert arcs[0] is not None


def test_threaded_hole_and_pattern_specs_are_reversible_mutations() -> None:
    registry = build_default_registry()
    for name in (
        "cad.create_threaded_hole",
        "cad.mirror_object",
        "cad.linear_pattern",
        "cad.polar_pattern",
    ):
        spec = registry.get_spec(name)
        assert spec.risk is ToolRisk.MODIFY
        assert spec.output_schema is not None


def test_gear_phase_is_an_optional_bounded_parameter() -> None:
    registry = build_default_registry()
    base = {"teeth": 20, "module": 2, "thickness": 8, "bore_diameter": 8}
    assert registry.validate_arguments(
        "cad.create_spur_gear", {**base, "phase": 9}
    ) == {**base, "phase": 9}
    for overrides in ({"phase": 361}, {"phase": -361}):
        with pytest.raises(ToolInputError):
            registry.validate_arguments("cad.create_spur_gear", {**base, **overrides})
    helical = {**base, "helix_angle": 15}
    assert registry.validate_arguments(
        "cad.create_helical_gear", {**helical, "phase": -9}
    ) == {**helical, "phase": -9}


def test_threaded_hole_schema_requires_object_and_depth() -> None:
    registry = build_default_registry()
    base = {"object": "Base", "diameter": 8, "pitch": 1.25, "x": 0, "y": 0, "depth": 12}
    assert registry.validate_arguments("cad.create_threaded_hole", base) == base
    for overrides in ({"diameter": 0}, {"pitch": 0}, {"depth": -1}):
        with pytest.raises(ToolInputError):
            registry.validate_arguments(
                "cad.create_threaded_hole", {**base, **overrides}
            )


def test_adapter_validates_threaded_hole_before_freecad() -> None:
    adapter = FreeCadAdapter()
    with pytest.raises(ValueError, match="quarter"):
        adapter.create_threaded_hole("Base", 8, 3, 0, 0, 12)
    with pytest.raises(ValueError, match="at least one pitch"):
        adapter.create_threaded_hole("Base", 8, 1.25, 0, 0, 1)
    with pytest.raises(ValueError, match="64 turns"):
        adapter.create_threaded_hole("Base", 8, 0.5, 0, 0, 40)
    with pytest.raises(ValueError, match="finite"):
        adapter.create_threaded_hole("Base", 8, 1.25, float("inf"), 0, 12)


def test_pattern_schemas_bound_counts_and_axes() -> None:
    registry = build_default_registry()
    assert registry.validate_arguments(
        "cad.mirror_object", {"object": "Base", "plane": "xz"}
    ) == {"object": "Base", "plane": "xz"}
    with pytest.raises(ToolInputError):
        registry.validate_arguments(
            "cad.mirror_object", {"object": "Base", "plane": "diagonal"}
        )
    linear = {"object": "Base", "count": 4, "spacing": 15, "direction": "y"}
    assert registry.validate_arguments("cad.linear_pattern", linear) == linear
    for overrides in ({"count": 1}, {"count": 65}, {"spacing": 0}, {"direction": "w"}):
        with pytest.raises(ToolInputError):
            registry.validate_arguments("cad.linear_pattern", {**linear, **overrides})
    polar = {"object": "Base", "count": 6, "angle": 360, "axis": "z"}
    assert registry.validate_arguments("cad.polar_pattern", polar) == polar
    for overrides in ({"count": 1}, {"angle": 0}, {"angle": 361}, {"axis": "q"}):
        with pytest.raises(ToolInputError):
            registry.validate_arguments("cad.polar_pattern", {**polar, **overrides})


def test_adapter_validates_patterns_before_freecad() -> None:
    adapter = FreeCadAdapter()
    with pytest.raises(ValueError, match="mirror plane"):
        adapter.mirror_object("Base", plane="diagonal")
    with pytest.raises(ValueError, match="between 2 and 64"):
        adapter.linear_pattern("Base", 1, 15)
    with pytest.raises(ValueError, match="direction"):
        adapter.linear_pattern("Base", 3, 15, direction="w")
    with pytest.raises(ValueError, match="between 2 and 64"):
        adapter.polar_pattern("Base", 1)
    with pytest.raises(ValueError, match="within"):
        adapter.polar_pattern("Base", 4, angle=0)
    with pytest.raises(ValueError, match="axis"):
        adapter.polar_pattern("Base", 4, axis="q")

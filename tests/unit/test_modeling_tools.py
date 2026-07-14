import pytest

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
    with pytest.raises(ValueError, match="does not fit"):
        adapter.create_sweep_path(
            ["0,0,0", "0,0,30", "30,0,30"],
            corner_radius=20,
        )
    with pytest.raises(ValueError, match="cannot be negative"):
        adapter.create_sweep_path(["0,0,0", "0,0,40"], corner_radius=-1)

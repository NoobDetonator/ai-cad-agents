from __future__ import annotations

from aicad.core.tool_catalog import default_tool_specs
from aicad.core.tool_registry import ToolSpec


_LEGACY_MECHANICAL_TOOL_NAMES = frozenset(
    (
        "cad.get_object_details",
        "cad.measure_object",
        "cad.get_dependencies",
        "cad.resolve_object",
        "cad.get_editable_parameters",
        "cad.capture_view",
        "cad.capture_views",
        "cad.rename_object",
        "cad.set_parameter",
        "cad.transform_object",
        "cad.create_plate",
        "cad.create_through_hole",
        "cad.create_rectangular_hole_pattern",
        "cad.create_circular_hole_pattern",
        "cad.create_counterbore_hole",
        "cad.create_countersunk_hole",
        "cad.create_threaded_hole",
        "cad.create_rectangular_sketch",
        "cad.pad_sketch",
        "cad.create_circular_sketch",
        "cad.revolve_sketch",
        "cad.loft_sketches",
        "cad.create_sweep_path",
        "cad.sweep_sketch",
        "cad.boolean_operation",
        "cad.fillet_edges",
        "cad.chamfer_edges",
        "cad.mirror_object",
        "cad.linear_pattern",
        "cad.polar_pattern",
        "cad.create_spur_gear",
        "cad.create_helical_gear",
        "cad.create_external_thread",
    )
)


def mechanical_tool_specs() -> tuple[ToolSpec, ...]:
    """Compatibility view of the catalog that historically lived here."""

    return tuple(
        spec
        for spec in default_tool_specs()
        if spec.name in _LEGACY_MECHANICAL_TOOL_NAMES
    )

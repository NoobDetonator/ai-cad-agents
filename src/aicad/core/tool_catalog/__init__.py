from __future__ import annotations

from collections.abc import Callable

from aicad.core.tool_catalog.assembly import assembly_tool_specs
from aicad.core.tool_catalog.bearings import bearing_tool_specs
from aicad.core.tool_catalog.context import context_tool_specs
from aicad.core.tool_catalog.documents import document_tool_specs
from aicad.core.tool_catalog.editing import editing_tool_specs
from aicad.core.tool_catalog.governance import governance_tool_specs
from aicad.core.tool_catalog.mechanical import mechanical_part_tool_specs
from aicad.core.tool_catalog.modeling import modeling_tool_specs
from aicad.core.tool_catalog.objects import object_tool_specs
from aicad.core.tool_catalog.patterns import pattern_tool_specs
from aicad.core.tool_catalog.primitives import primitive_tool_specs
from aicad.core.tool_catalog.sketching import sketch_tool_specs
from aicad.core.tool_registry import ToolSpec


ToolSpecBuilder = Callable[[], tuple[ToolSpec, ...]]

CATALOG_BUILDERS: tuple[ToolSpecBuilder, ...] = (
    context_tool_specs,
    primitive_tool_specs,
    editing_tool_specs,
    object_tool_specs,
    sketch_tool_specs,
    modeling_tool_specs,
    pattern_tool_specs,
    mechanical_part_tool_specs,
    assembly_tool_specs,
    bearing_tool_specs,
    governance_tool_specs,
    document_tool_specs,
)

_FOUNDATION_REGISTRATION_ORDER = (
    "cad.get_document_summary",
    "cad.get_selection",
    "cad.get_context_snapshot",
    "cad.create_box",
    "cad.create_cylinder",
    "cad.validate_document",
    "cad.undo",
    "cad.get_audit_history",
    "cad.export_audit_history",
    "cad.list_documents",
    "cad.new_document",
    "cad.set_active_document",
    "cad.save_document",
    "cad.export_stl",
    "cad.export_step",
)

_EXTENSION_REGISTRATION_ORDER = (
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


def default_tool_specs() -> tuple[ToolSpec, ...]:
    """Build the complete provider-neutral CAD catalog in stable API order."""

    specs = tuple(spec for builder in CATALOG_BUILDERS for spec in builder())
    specs_by_name = {spec.name: spec for spec in specs}
    if len(specs_by_name) != len(specs):
        raise ValueError("The CAD tool catalog contains duplicate names.")
    stable_order = _FOUNDATION_REGISTRATION_ORDER + _EXTENSION_REGISTRATION_ORDER
    stable_names = set(stable_order)
    stable_specs = tuple(specs_by_name[name] for name in stable_order)
    additions = tuple(
        sorted(
            (spec for spec in specs if spec.name not in stable_names),
            key=lambda spec: spec.canonical_order,
        )
    )
    return stable_specs + additions

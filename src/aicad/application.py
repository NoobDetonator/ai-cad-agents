from __future__ import annotations

from functools import partial
from typing import Any, Protocol

from aicad.core.partdesign_registry import PARTDESIGN_FEATURES
from aicad.core.tool_registry import ToolRegistry, build_default_registry


class CadAdapter(Protocol):
    """CAD boundary expected by the application layer."""

    def get_document_summary(self) -> dict[str, Any]: ...

    def get_selection(self) -> dict[str, Any]: ...

    def get_context_snapshot(
        self,
        detail_level: str = "work",
        max_objects: int = 25,
        cursor: int = 0,
    ) -> dict[str, Any]: ...

    def get_object_details(self, object: str) -> dict[str, Any]: ...

    def measure_object(self, object: str) -> dict[str, Any]: ...

    def measure_mass_properties(
        self, object: str, density: float
    ) -> dict[str, Any]: ...

    def analyze_print_readiness(
        self,
        object: str,
        max_overhang_angle_deg: float = 45.0,
    ) -> dict[str, Any]: ...

    def measure_distance(self, left: str, right: str) -> dict[str, Any]: ...

    def get_dependencies(self, object: str) -> dict[str, Any]: ...

    def resolve_object(self, reference: str = "") -> dict[str, Any]: ...

    def get_editable_parameters(self, object: str) -> dict[str, Any]: ...

    def capture_view(
        self,
        width: int = 960,
        height: int = 640,
        view: str = "current",
        fit: bool = False,
    ) -> dict[str, Any]: ...

    def capture_views(
        self,
        views: list[str] | None = None,
        width: int = 640,
        height: int = 480,
        fit: bool = True,
    ) -> dict[str, Any]: ...

    def capture_section_view(
        self,
        plane: str = "xy",
        offset: float = 0.0,
        flip: bool = False,
        width: int = 640,
        height: int = 480,
        view: str = "isometric",
        fit: bool = True,
    ) -> dict[str, Any]: ...

    def create_box(
        self, length: float, width: float, height: float, name: str = "AIBox"
    ) -> dict[str, Any]: ...

    def create_cylinder(
        self, diameter: float, height: float, name: str = "AICylinder"
    ) -> dict[str, Any]: ...

    def create_cone(
        self,
        bottom_diameter: float,
        top_diameter: float,
        height: float,
        name: str = "AICone",
    ) -> dict[str, Any]: ...

    def create_sphere(
        self, diameter: float, name: str = "AISphere"
    ) -> dict[str, Any]: ...

    def create_torus(
        self,
        major_diameter: float,
        tube_diameter: float,
        name: str = "AITorus",
    ) -> dict[str, Any]: ...

    def duplicate_object(
        self,
        object: str,
        name: str,
        offset_x: float = 0,
        offset_y: float = 0,
        offset_z: float = 0,
    ) -> dict[str, Any]: ...

    def delete_object(self, object: str) -> dict[str, Any]: ...

    def rename_object(self, object: str, name: str) -> dict[str, Any]: ...

    def set_parameter(
        self, object: str, parameter: str, value: float
    ) -> dict[str, Any]: ...

    def transform_object(
        self,
        object: str,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
        roll: float | None = None,
        pitch: float | None = None,
        yaw: float | None = None,
    ) -> dict[str, Any]: ...

    def translate_object(
        self,
        object: str,
        dx: float = 0,
        dy: float = 0,
        dz: float = 0,
    ) -> dict[str, Any]: ...

    def rotate_object(
        self,
        object: str,
        axis: str,
        angle: float,
        pivot: str = "object_center",
    ) -> dict[str, Any]: ...

    def create_plate(
        self, length: float, width: float, thickness: float, name: str = "AIPlate"
    ) -> dict[str, Any]: ...

    def create_through_hole(
        self,
        object: str,
        diameter: float,
        x: float,
        y: float,
        name: str = "AIThroughHole",
        z_min: float | None = None,
        z_max: float | None = None,
    ) -> dict[str, Any]: ...

    def create_rectangular_hole_pattern(self, **arguments: Any) -> dict[str, Any]: ...

    def create_circular_hole_pattern(self, **arguments: Any) -> dict[str, Any]: ...

    def create_counterbore_hole(
        self,
        object: str,
        diameter: float,
        x: float,
        y: float,
        counterbore_diameter: float,
        counterbore_depth: float,
        name: str = "AICounterboreHole",
    ) -> dict[str, Any]: ...

    def create_countersunk_hole(
        self,
        object: str,
        diameter: float,
        x: float,
        y: float,
        countersink_diameter: float,
        countersink_angle: float = 90,
        name: str = "AICountersunkHole",
    ) -> dict[str, Any]: ...

    def create_threaded_hole(
        self,
        object: str,
        diameter: float,
        pitch: float,
        x: float,
        y: float,
        depth: float,
        name: str = "AIThreadedHole",
    ) -> dict[str, Any]: ...

    def mirror_object(
        self, object: str, plane: str = "yz", name: str = "AIMirror"
    ) -> dict[str, Any]: ...

    def linear_pattern(
        self,
        object: str,
        count: int,
        spacing: float,
        direction: str = "x",
        name: str = "AILinearPattern",
    ) -> dict[str, Any]: ...

    def polar_pattern(
        self,
        object: str,
        count: int,
        angle: float = 360.0,
        axis: str = "z",
        name: str = "AIPolarPattern",
    ) -> dict[str, Any]: ...

    def create_rectangular_sketch(
        self, width: float, height: float, name: str = "AIRectangleSketch"
    ) -> dict[str, Any]: ...

    def create_empty_sketch(self, **arguments: Any) -> dict[str, Any]: ...

    def add_sketch_line(self, **arguments: Any) -> dict[str, Any]: ...

    def add_sketch_polyline(self, **arguments: Any) -> dict[str, Any]: ...

    def add_sketch_circle(self, **arguments: Any) -> dict[str, Any]: ...

    def add_sketch_arc(self, **arguments: Any) -> dict[str, Any]: ...

    def add_sketch_ellipse(self, **arguments: Any) -> dict[str, Any]: ...

    def add_sketch_rectangle(self, **arguments: Any) -> dict[str, Any]: ...

    def add_sketch_slot(self, **arguments: Any) -> dict[str, Any]: ...

    def add_sketch_regular_polygon(self, **arguments: Any) -> dict[str, Any]: ...

    def add_sketch_external_geometry(self, **arguments: Any) -> dict[str, Any]: ...

    def add_sketch_geometric_constraint(self, **arguments: Any) -> dict[str, Any]: ...

    def add_sketch_dimensional_constraint(self, **arguments: Any) -> dict[str, Any]: ...

    def set_sketch_constraint_value(self, **arguments: Any) -> dict[str, Any]: ...

    def set_sketch_constraint_driving(self, **arguments: Any) -> dict[str, Any]: ...

    def move_sketch_point(self, **arguments: Any) -> dict[str, Any]: ...

    def toggle_sketch_construction(self, **arguments: Any) -> dict[str, Any]: ...

    def delete_sketch_geometry(self, **arguments: Any) -> dict[str, Any]: ...

    def delete_sketch_constraint(self, **arguments: Any) -> dict[str, Any]: ...

    def trim_sketch_geometry(self, **arguments: Any) -> dict[str, Any]: ...

    def extend_sketch_geometry(self, **arguments: Any) -> dict[str, Any]: ...

    def fillet_sketch_corner(self, **arguments: Any) -> dict[str, Any]: ...

    def copy_sketch_geometry(self, **arguments: Any) -> dict[str, Any]: ...

    def mirror_sketch_geometry(self, **arguments: Any) -> dict[str, Any]: ...

    def get_sketch_info(self, sketch: str) -> dict[str, Any]: ...

    def pad_sketch(
        self, sketch: str, length: float, name: str = "AIPad"
    ) -> dict[str, Any]: ...

    def boolean_operation(
        self, left: str, right: str, operation: str, name: str = "AIBoolean"
    ) -> dict[str, Any]: ...

    def fillet_edges(
        self, object: str, radius: float, edge_reference: str, name: str = "AIFillet"
    ) -> dict[str, Any]: ...

    def chamfer_edges(
        self, object: str, size: float, edge_reference: str, name: str = "AIChamfer"
    ) -> dict[str, Any]: ...

    def create_circular_sketch(
        self, diameter: float, name: str = "AICircleSketch"
    ) -> dict[str, Any]: ...

    def revolve_sketch(
        self,
        sketch: str,
        angle: float = 360.0,
        axis: str = "x",
        name: str = "AIRevolve",
    ) -> dict[str, Any]: ...

    def loft_sketches(
        self,
        sketches: list[str],
        ruled: bool = False,
        name: str = "AILoft",
    ) -> dict[str, Any]: ...

    def create_sweep_path(
        self,
        points: list[str],
        corner_radius: float = 0,
        name: str = "AISweepPath",
    ) -> dict[str, Any]: ...

    def sweep_sketch(
        self,
        profile: str,
        path: str,
        name: str = "AISweep",
    ) -> dict[str, Any]: ...

    def create_helical_gear(
        self,
        teeth: int,
        module: float,
        thickness: float,
        helix_angle: float,
        bore_diameter: float,
        pressure_angle: float = 20,
        phase: float = 0,
        name: str = "HelicalGear",
    ) -> dict[str, Any]: ...

    def create_external_thread(
        self,
        diameter: float,
        pitch: float,
        length: float,
        name: str = "AIThread",
    ) -> dict[str, Any]: ...

    def create_spur_gear(
        self,
        teeth: int,
        module: float,
        thickness: float,
        bore_diameter: float,
        pressure_angle: float = 20,
        phase: float = 0,
        name: str = "SpurGear",
    ) -> dict[str, Any]: ...

    def create_internal_gear(
        self,
        teeth: int,
        module: float,
        thickness: float,
        rim_thickness: float,
        pressure_angle: float = 20,
        phase: float = 0,
        name: str = "InternalGear",
    ) -> dict[str, Any]: ...

    def create_planetary_carrier(
        self,
        plate_diameter: float,
        thickness: float,
        center_bore_diameter: float,
        planet_count: int,
        planet_pitch_diameter: float,
        pin_hole_diameter: float,
        name: str = "PlanetaryCarrier",
    ) -> dict[str, Any]: ...

    def create_ball_bearing(
        self,
        bore_diameter: float,
        outer_diameter: float,
        width: float,
        ball_count: int,
        ball_diameter: float,
        radial_clearance: float = 0.05,
        name: str = "BallBearing",
    ) -> dict[str, Any]: ...

    def create_deep_groove_ball_bearing(self, **arguments: Any) -> dict[str, Any]: ...

    def create_thrust_ball_bearing(self, **arguments: Any) -> dict[str, Any]: ...

    def create_cylindrical_roller_bearing(self, **arguments: Any) -> dict[str, Any]: ...

    def create_print_in_place_roller_bearing(
        self, **arguments: Any
    ) -> dict[str, Any]: ...

    def create_printed_plain_bushing(self, **arguments: Any) -> dict[str, Any]: ...

    def apply_gear_backlash(
        self, object: str, backlash: float, name: str
    ) -> dict[str, Any]: ...

    def align_concentric(
        self,
        moving: str,
        reference: str,
        z_alignment: str = "center",
        axial_offset: float = 0,
    ) -> dict[str, Any]: ...

    def analyze_interferences(
        self,
        objects: list[str],
        minimum_clearance: float = 0,
        volume_tolerance: float = 1e-4,
    ) -> dict[str, Any]: ...

    def validate_document(self) -> dict[str, Any]: ...

    def list_documents(self) -> dict[str, Any]: ...

    def new_document(self, name: str = "AICadDoc") -> dict[str, Any]: ...

    def set_active_document(self, document: str) -> dict[str, Any]: ...

    def save_document(
        self, destination: str = "", overwrite: bool = False
    ) -> dict[str, Any]: ...

    def export_stl(
        self, destination: str, object: str, overwrite: bool = False
    ) -> dict[str, Any]: ...

    def export_step(
        self, destination: str, object: str, overwrite: bool = False
    ) -> dict[str, Any]: ...

    def undo(self) -> dict[str, bool]: ...


def build_cad_tool_registry(adapter: CadAdapter) -> ToolRegistry:
    """Connect the provider-independent catalog to one explicit CAD adapter."""

    registry = build_default_registry()

    def bind(tool_name: str, method_name: str) -> None:
        handler = getattr(adapter, method_name, None)
        if handler is None:
            def unavailable(**_: Any) -> Any:
                raise RuntimeError(
                    f"The active CAD adapter does not provide {tool_name}."
                )

            handler = unavailable
        registry.bind(tool_name, handler)

    bindings = {
        "cad.get_document_summary": "get_document_summary",
        "cad.get_selection": "get_selection",
        "cad.get_context_snapshot": "get_context_snapshot",
        "cad.get_object_details": "get_object_details",
        "cad.measure_object": "measure_object",
        "cad.measure_mass_properties": "measure_mass_properties",
        "cad.analyze_print_readiness": "analyze_print_readiness",
        "cad.measure_distance": "measure_distance",
        "cad.get_dependencies": "get_dependencies",
        "cad.resolve_object": "resolve_object",
        "cad.get_editable_parameters": "get_editable_parameters",
        "cad.capture_view": "capture_view",
        "cad.capture_views": "capture_views",
        "cad.capture_section_view": "capture_section_view",
        "cad.create_box": "create_box",
        "cad.create_cylinder": "create_cylinder",
        "cad.create_cone": "create_cone",
        "cad.create_sphere": "create_sphere",
        "cad.create_torus": "create_torus",
        "cad.duplicate_object": "duplicate_object",
        "cad.delete_object": "delete_object",
        "cad.rename_object": "rename_object",
        "cad.set_parameter": "set_parameter",
        "cad.transform_object": "transform_object",
        "cad.translate_object": "translate_object",
        "cad.rotate_object": "rotate_object",
        "cad.create_plate": "create_plate",
        "cad.create_through_hole": "create_through_hole",
        "cad.create_rectangular_hole_pattern": "create_rectangular_hole_pattern",
        "cad.create_circular_hole_pattern": "create_circular_hole_pattern",
        "cad.create_counterbore_hole": "create_counterbore_hole",
        "cad.create_countersunk_hole": "create_countersunk_hole",
        "cad.create_threaded_hole": "create_threaded_hole",
        "cad.mirror_object": "mirror_object",
        "cad.linear_pattern": "linear_pattern",
        "cad.polar_pattern": "polar_pattern",
        "cad.create_rectangular_sketch": "create_rectangular_sketch",
        "cad.create_empty_sketch": "create_empty_sketch",
        "cad.add_sketch_line": "add_sketch_line",
        "cad.add_sketch_polyline": "add_sketch_polyline",
        "cad.add_sketch_circle": "add_sketch_circle",
        "cad.add_sketch_arc": "add_sketch_arc",
        "cad.add_sketch_ellipse": "add_sketch_ellipse",
        "cad.add_sketch_rectangle": "add_sketch_rectangle",
        "cad.add_sketch_slot": "add_sketch_slot",
        "cad.add_sketch_regular_polygon": "add_sketch_regular_polygon",
        "cad.add_sketch_external_geometry": "add_sketch_external_geometry",
        "cad.add_sketch_geometric_constraint": "add_sketch_geometric_constraint",
        "cad.add_sketch_dimensional_constraint": "add_sketch_dimensional_constraint",
        "cad.set_sketch_constraint_value": "set_sketch_constraint_value",
        "cad.set_sketch_constraint_driving": "set_sketch_constraint_driving",
        "cad.move_sketch_point": "move_sketch_point",
        "cad.toggle_sketch_construction": "toggle_sketch_construction",
        "cad.delete_sketch_geometry": "delete_sketch_geometry",
        "cad.delete_sketch_constraint": "delete_sketch_constraint",
        "cad.trim_sketch_geometry": "trim_sketch_geometry",
        "cad.extend_sketch_geometry": "extend_sketch_geometry",
        "cad.fillet_sketch_corner": "fillet_sketch_corner",
        "cad.copy_sketch_geometry": "copy_sketch_geometry",
        "cad.mirror_sketch_geometry": "mirror_sketch_geometry",
        "cad.get_sketch_info": "get_sketch_info",
        "cad.pad_sketch": "pad_sketch",
        "cad.boolean_operation": "boolean_operation",
        "cad.fillet_edges": "fillet_edges",
        "cad.chamfer_edges": "chamfer_edges",
        "cad.create_spur_gear": "create_spur_gear",
        "cad.create_internal_gear": "create_internal_gear",
        "cad.create_planetary_carrier": "create_planetary_carrier",
        "cad.create_ball_bearing": "create_ball_bearing",
        "cad.create_deep_groove_ball_bearing": "create_deep_groove_ball_bearing",
        "cad.create_thrust_ball_bearing": "create_thrust_ball_bearing",
        "cad.create_cylindrical_roller_bearing": "create_cylindrical_roller_bearing",
        "cad.create_print_in_place_roller_bearing": "create_print_in_place_roller_bearing",
        "cad.create_printed_plain_bushing": "create_printed_plain_bushing",
        "cad.apply_gear_backlash": "apply_gear_backlash",
        "cad.align_concentric": "align_concentric",
        "cad.analyze_interferences": "analyze_interferences",
        "cad.create_circular_sketch": "create_circular_sketch",
        "cad.revolve_sketch": "revolve_sketch",
        "cad.loft_sketches": "loft_sketches",
        "cad.create_sweep_path": "create_sweep_path",
        "cad.sweep_sketch": "sweep_sketch",
        "cad.create_helical_gear": "create_helical_gear",
        "cad.create_external_thread": "create_external_thread",
        "cad.validate_document": "validate_document",
        "cad.list_documents": "list_documents",
        "cad.new_document": "new_document",
        "cad.set_active_document": "set_active_document",
        "cad.save_document": "save_document",
        "cad.export_stl": "export_stl",
        "cad.export_step": "export_step",
        "cad.undo": "undo",
        "cad.create_body": "create_body",
        "cad.create_body_sketch": "create_body_sketch",
        "cad.set_sketch_datum": "set_sketch_datum",
        "cad.get_sketch_status": "get_sketch_status",
        "cad.edit_feature": "edit_feature",
        "cad.resolve_body_reference": "resolve_body_reference",
        "cad.create_face_sketch": "create_face_sketch",
        "cad.add_fillet": "add_fillet_feature",
        "cad.add_chamfer": "add_chamfer_feature",
        "cad.create_parameter_set": "create_parameter_set",
        "cad.set_master_parameter": "set_master_parameter",
        "cad.list_master_parameters": "list_master_parameters",
        "cad.rename_sketch_constraint": "rename_sketch_constraint",
        "cad.bind_sketch_datum": "bind_sketch_datum",
        "cad.bind_feature_parameter": "bind_feature_parameter",
    }
    for tool_name, method_name in bindings.items():
        bind(tool_name, method_name)

    generic_feature = getattr(adapter, "create_partdesign_feature", None)
    for definition in PARTDESIGN_FEATURES:
        if generic_feature is None:
            bind(definition.tool_name, "create_partdesign_feature")
        else:
            registry.bind(
                definition.tool_name,
                partial(generic_feature, definition.tool_name),
            )
    return registry

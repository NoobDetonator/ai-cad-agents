from __future__ import annotations

import os
import sys
from pathlib import Path


project_root = Path(os.environ["AICAD_PROJECT_ROOT"])
sys.path.insert(0, str(project_root / "src"))

import FreeCAD as App

from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.application import build_cad_tool_registry


for document_name in list(App.listDocuments()):
    App.closeDocument(document_name)

document = App.newDocument("SketchEnvironmentSmoke")
document.UndoMode = 1
adapter = FreeCadAdapter()
registry = build_cad_tool_registry(adapter)


def modify(name: str, arguments: dict):
    return registry.execute(name, arguments, confirmed=True)


created = modify(
    "cad.create_empty_sketch", {"plane": "xy", "name": "MasterProfile"}
)
assert created["geometry_count"] == 0
rectangle = modify(
    "cad.add_sketch_rectangle",
    {
        "sketch": "MasterProfile",
        "x": -30,
        "y": -20,
        "width": 60,
        "height": 40,
    },
)
assert rectangle["added_geometry"] == [0, 1, 2, 3]
slot = modify(
    "cad.add_sketch_slot",
    {
        "sketch": "MasterProfile",
        "start_x": -14,
        "start_y": 0,
        "end_x": 14,
        "end_y": 0,
        "width": 8,
    },
)
assert slot["closed"] is True
circle = modify(
    "cad.add_sketch_circle",
    {
        "sketch": "MasterProfile",
        "center_x": 0,
        "center_y": 0,
        "radius": 5,
    },
)
assert circle["added_geometry"] == [8]
polygon = modify(
    "cad.add_sketch_regular_polygon",
    {
        "sketch": "MasterProfile",
        "center_x": 0,
        "center_y": 0,
        "radius": 12,
        "sides": 6,
        "rotation": 30,
        "construction": True,
    },
)
assert polygon["sides"] == 6
modify(
    "cad.toggle_sketch_construction",
    {"sketch": "MasterProfile", "geometry_indices": [9, 10, 11, 12, 13, 14]},
)

modify("cad.create_empty_sketch", {"plane": "xz", "offset": 5, "name": "XZProfile"})
modify(
    "cad.add_sketch_ellipse",
    {
        "sketch": "XZProfile",
        "center_x": 0,
        "center_y": 0,
        "major_radius": 18,
        "minor_radius": 8,
        "rotation": 25,
    },
)
modify("cad.create_empty_sketch", {"plane": "yz", "offset": 7, "name": "YZProfile"})
arc = modify(
    "cad.add_sketch_arc",
    {
        "sketch": "YZProfile",
        "center_x": 0,
        "center_y": 0,
        "radius": 15,
        "start_angle": 15,
        "end_angle": 220,
    },
)
assert abs(arc["sweep_angle_deg"] - 205) < 1e-9

modify("cad.create_empty_sketch", {"name": "ConstrainedLines"})
modify(
    "cad.add_sketch_line",
    {"sketch": "ConstrainedLines", "x1": 0, "y1": 0, "x2": 30, "y2": 2},
)
modify(
    "cad.add_sketch_line",
    {"sketch": "ConstrainedLines", "x1": 30, "y1": 2, "x2": 30, "y2": 20},
)
modify(
    "cad.add_sketch_geometric_constraint",
    {"sketch": "ConstrainedLines", "constraint_type": "horizontal", "first_geometry": 0},
)
modify(
    "cad.add_sketch_geometric_constraint",
    {"sketch": "ConstrainedLines", "constraint_type": "vertical", "first_geometry": 1},
)
modify(
    "cad.add_sketch_geometric_constraint",
    {
        "sketch": "ConstrainedLines",
        "constraint_type": "coincident",
        "first_geometry": 0,
        "first_position": "end",
        "second_geometry": 1,
        "second_position": "start",
    },
)
length = modify(
    "cad.add_sketch_dimensional_constraint",
    {
        "sketch": "ConstrainedLines",
        "constraint_type": "length",
        "geometry": 0,
        "value": 30,
    },
)
length_index = length["added_constraint"]
modify(
    "cad.set_sketch_constraint_value",
    {
        "sketch": "ConstrainedLines",
        "constraint_index": length_index,
        "value": 35,
        "unit": "mm",
    },
)
modify(
    "cad.set_sketch_constraint_driving",
    {
        "sketch": "ConstrainedLines",
        "constraint_index": length_index,
        "driving": False,
    },
)
modify(
    "cad.set_sketch_constraint_driving",
    {
        "sketch": "ConstrainedLines",
        "constraint_index": length_index,
        "driving": True,
    },
)
copied = modify(
    "cad.copy_sketch_geometry",
    {
        "sketch": "ConstrainedLines",
        "geometry_indices": [0, 1],
        "dx": 0,
        "dy": 30,
    },
)
assert copied["added_geometry"] == [2, 3]
mirrored = modify(
    "cad.mirror_sketch_geometry",
    {
        "sketch": "ConstrainedLines",
        "geometry_indices": [2, 3],
        "axis": "vertical",
    },
)
assert len(mirrored["added_geometry"]) == 2
modify(
    "cad.delete_sketch_geometry",
    {"sketch": "ConstrainedLines", "geometry_indices": mirrored["added_geometry"]},
)
info = registry.execute("cad.get_sketch_info", {"sketch": "ConstrainedLines"})
assert info["geometry_count"] == 4
assert info["constraint_count"] >= 4

modify("cad.create_empty_sketch", {"name": "EditableCurves"})
modify(
    "cad.add_sketch_rectangle",
    {"sketch": "EditableCurves", "x": 0, "y": 0, "width": 40, "height": 20},
)
modify(
    "cad.add_sketch_line",
    {"sketch": "EditableCurves", "x1": 20, "y1": -10, "x2": 20, "y2": 30},
)
trimmed = modify(
    "cad.trim_sketch_geometry",
    {"sketch": "EditableCurves", "geometry": 0, "x": 30, "y": 0},
)
assert trimmed["valid"] is True

modify("cad.create_empty_sketch", {"name": "ExtendSketch"})
modify(
    "cad.add_sketch_line",
    {"sketch": "ExtendSketch", "x1": 0, "y1": 0, "x2": 10, "y2": 0},
)
extended = modify(
    "cad.extend_sketch_geometry",
    {"sketch": "ExtendSketch", "geometry": 0, "position": "end", "increment": 8},
)
assert extended["increment_mm"] == 8
modify(
    "cad.move_sketch_point",
    {"sketch": "ExtendSketch", "geometry": 0, "position": "start", "x": -5, "y": 0},
)

modify("cad.create_empty_sketch", {"name": "FilletSketch"})
modify(
    "cad.add_sketch_line",
    {"sketch": "FilletSketch", "x1": 0, "y1": 0, "x2": 30, "y2": 0},
)
modify(
    "cad.add_sketch_line",
    {"sketch": "FilletSketch", "x1": 30, "y1": 0, "x2": 30, "y2": 30},
)
fillet = modify(
    "cad.fillet_sketch_corner",
    {
        "sketch": "FilletSketch",
        "first_geometry": 0,
        "second_geometry": 1,
        "first_x": 29,
        "first_y": 0,
        "second_x": 30,
        "second_y": 1,
        "radius": 5,
    },
)
assert fillet["geometry_count"] >= 3

modify(
    "cad.create_box",
    {"length": 20, "width": 15, "height": 8, "name": "ExternalSource"},
)
details = registry.execute("cad.get_object_details", {"object": "ExternalSource"})
edge_reference = details["edge_references"][0]["reference"]
modify("cad.create_empty_sketch", {"name": "ExternalSketch"})
external = modify(
    "cad.add_sketch_external_geometry",
    {
        "sketch": "ExternalSketch",
        "object": "ExternalSource",
        "edge_reference": edge_reference,
    },
)
assert external["external_geometry_index"] < 0

modify("cad.create_empty_sketch", {"name": "PadProfile"})
modify(
    "cad.add_sketch_rectangle",
    {"sketch": "PadProfile", "x": 0, "y": 0, "width": 25, "height": 15},
)
pad = modify(
    "cad.pad_sketch", {"sketch": "PadProfile", "length": 6, "name": "SketchPad"}
)
assert abs(pad["volume_mm3"] - 25 * 15 * 6) < 1e-6

before = registry.execute("cad.get_sketch_info", {"sketch": "ExtendSketch"})
modify(
    "cad.add_sketch_circle",
    {"sketch": "ExtendSketch", "center_x": 30, "center_y": 0, "radius": 3},
)
assert modify("cad.undo", {})["undone"] is True
after = registry.execute("cad.get_sketch_info", {"sketch": "ExtendSketch"})
assert after["geometry_count"] == before["geometry_count"]
assert registry.execute("cad.validate_document")["valid"] is True

print("FREECAD_SKETCH_SMOKE_OK")
App.closeDocument(document.Name)

from __future__ import annotations

import math
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

document = App.newDocument("PartDesignSmoke")
document.UndoMode = 1
adapter = FreeCadAdapter()
registry = build_cad_tool_registry(adapter)


def modify(name: str, arguments: dict):
    return registry.execute(name, arguments, confirmed=True)


def read(name: str, arguments: dict):
    return registry.execute(name, arguments)


def close(expected: float, actual: float, tolerance: float = 0.01) -> bool:
    return abs(actual - expected) <= abs(expected) * tolerance


# --- Body and attached base sketch ---------------------------------------

body = modify("cad.create_body", {"name": "MainBody"})
assert body["valid"] is True

base_sketch = modify(
    "cad.create_body_sketch",
    {"body": "MainBody", "plane": "xy", "name": "BaseSketch"},
)
assert base_sketch["body"] == "MainBody"
assert base_sketch["plane"] == "xy"

rectangle = modify(
    "cad.add_sketch_rectangle",
    {"sketch": "BaseSketch", "x": -30, "y": -20, "width": 60, "height": 40},
)
assert rectangle["closed_wire_count"] == 1

# --- Sketch status before and after dimensioning --------------------------

status = read("cad.get_sketch_status", {"sketch": "BaseSketch"})
assert status["fully_constrained"] is False
assert status["solver_status"] == 0
assert status["geometry_count"] == 4
if status["degrees_of_freedom"] is not None:
    assert status["degrees_of_freedom"] > 0
assert status["underconstrained_geometry"]

modify(
    "cad.add_sketch_dimensional_constraint",
    {
        "sketch": "BaseSketch",
        "constraint_type": "length",
        "geometry": 0,
        "value": 60,
    },
)
after_width = read("cad.get_sketch_status", {"sketch": "BaseSketch"})
if (
    status["degrees_of_freedom"] is not None
    and after_width["degrees_of_freedom"] is not None
):
    assert after_width["degrees_of_freedom"] < status["degrees_of_freedom"]

# --- Parametric pad -------------------------------------------------------

pad = modify("cad.add_pad", {"sketch": "BaseSketch", "length": 10})
assert pad["feature_type"] == "PartDesign::Pad"
assert pad["body"] == "MainBody"
assert close(60 * 40 * 10, pad["volume_mm3"]), pad["volume_mm3"]

# --- Through-all pocket from a second attached sketch ---------------------

modify(
    "cad.create_body_sketch",
    {"body": "MainBody", "plane": "xy", "name": "HoleSketch"},
)
modify(
    "cad.add_sketch_circle",
    {"sketch": "HoleSketch", "center_x": 10, "center_y": 10, "radius": 5},
)
radius_constraint = modify(
    "cad.add_sketch_dimensional_constraint",
    {
        "sketch": "HoleSketch",
        "constraint_type": "radius",
        "geometry": 0,
        "value": 5,
    },
)


def hole_area(radius: float) -> float:
    return math.pi * radius * radius


pocket = modify(
    "cad.add_pocket",
    {"sketch": "HoleSketch", "length": 1, "through_all": True, "reversed": True},
)
assert close(60 * 40 * 10 - hole_area(5) * 10, pocket["volume_mm3"]), pocket[
    "volume_mm3"
]

# --- Edit the pad by dimension: the whole tree recomputes -----------------

edited = modify(
    "cad.edit_feature", {"feature": "AIPad", "properties": {"length": 20}}
)
assert close(60 * 40 * 20 - hole_area(5) * 20, edited["volume_mm3"]), edited[
    "volume_mm3"
]

# --- Change the hole radius by datum: unique solution, deterministic ------

datum = modify(
    "cad.set_sketch_datum",
    {
        "sketch": "HoleSketch",
        "constraint": radius_constraint["added_constraint"],
        "value": 4,
    },
)
assert datum["constraint_type"] == "Radius"
after_datum = read("cad.measure_object", {"object": "MainBody"})
assert close(60 * 40 * 20 - hole_area(4) * 20, after_datum["volume_mm3"]), (
    after_datum["volume_mm3"]
)

# --- Linear pattern of the pocket along X ---------------------------------

pattern = modify(
    "cad.add_linear_pattern",
    {
        "features": ["AIPocket"],
        "direction": "x",
        "length": 15,
        "occurrences": 2,
    },
)
assert close(60 * 40 * 20 - 2 * hole_area(4) * 20, pattern["volume_mm3"]), (
    pattern["volume_mm3"]
)

# --- Mirrored pattern of the pocket across XZ -----------------------------

mirrored = modify(
    "cad.add_mirrored_pattern",
    {"features": ["AIPocket"], "plane": "xz"},
)
assert mirrored["volume_mm3"] < pattern["volume_mm3"], mirrored["volume_mm3"]

# --- Revolution in a second body around the sketch vertical axis ----------

modify("cad.create_body", {"name": "RingBody"})
modify(
    "cad.create_body_sketch",
    {"body": "RingBody", "plane": "xz", "name": "RingProfile"},
)
modify(
    "cad.add_sketch_rectangle",
    {"sketch": "RingProfile", "x": 10, "y": 0, "width": 4, "height": 6},
)
revolution = modify(
    "cad.add_revolution",
    {
        "body": "RingBody",
        "sketch": "RingProfile",
        "angle": 360,
        "axis": "vertical",
    },
)
ring_expected = 2 * math.pi * 12 * (4 * 6)
assert close(ring_expected, revolution["volume_mm3"]), revolution["volume_mm3"]

# --- Semantic references: face sketch, chamfer and fillet (P2) ------------

modify("cad.create_body", {"name": "DressupBody"})
modify(
    "cad.create_body_sketch",
    {"body": "DressupBody", "plane": "xy", "name": "DressupBase"},
)
modify(
    "cad.add_sketch_rectangle",
    {"sketch": "DressupBase", "x": -15, "y": -10, "width": 30, "height": 20},
)
dressup_pad = modify(
    "cad.add_pad",
    {"body": "DressupBody", "sketch": "DressupBase", "length": 10, "name": "DressupPad"},
)
assert close(30 * 20 * 10, dressup_pad["volume_mm3"]), dressup_pad["volume_mm3"]

top = read(
    "cad.resolve_body_reference",
    {
        "body": "DressupBody",
        "face": {"kind": "largest_planar_face", "normal": "+z"},
    },
)
assert close(30 * 20, top["face"]["area_mm2"]), top["face"]
assert close(10, top["face"]["center_mm"][2], 0.001), top["face"]
assert top["face"]["normal"][2] > 0.99, top["face"]

chamfer = modify(
    "cad.add_chamfer",
    {
        "body": "DressupBody",
        "edges": {
            "kind": "face_boundary",
            "face": {"kind": "largest_planar_face", "normal": "+z"},
        },
        "size": 1,
    },
)
assert len(chamfer["edges"]) == 4, chamfer["edges"]
assert close(6000 - 2 * (30 + 20) * 0.5, chamfer["volume_mm3"], 0.01), chamfer[
    "volume_mm3"
]

modify(
    "cad.create_face_sketch",
    {
        "body": "DressupBody",
        "face": {"kind": "largest_planar_face", "normal": "+z"},
        "name": "BossSketch",
    },
)
modify(
    "cad.add_sketch_circle",
    {"sketch": "BossSketch", "center_x": 0, "center_y": 0, "radius": 4},
)
boss = modify(
    "cad.add_pad",
    {"body": "DressupBody", "sketch": "BossSketch", "length": 5, "name": "Boss"},
)
assert close(
    chamfer["volume_mm3"] + math.pi * 16 * 5, boss["volume_mm3"], 0.005
), boss["volume_mm3"]

ring_edges = read(
    "cad.resolve_body_reference",
    {
        "body": "RingBody",
        "edges": {"kind": "circular_edges", "diameter": 28},
    },
)
assert ring_edges["edges"]["count"] == 2, ring_edges["edges"]

fillet = modify(
    "cad.add_fillet",
    {
        "body": "RingBody",
        "edges": {"kind": "circular_edges", "diameter": 28},
        "radius": 1,
    },
)
assert ring_expected - 60 < fillet["volume_mm3"] < ring_expected - 20, fillet[
    "volume_mm3"
]

try:
    read(
        "cad.resolve_body_reference",
        {
            "body": "DressupBody",
            "edges": {"kind": "circular_edges", "diameter": 99},
        },
    )
    raise AssertionError("A stale semantic reference must be rejected.")
except ValueError:
    pass

# --- Parametric counterbored holes ----------------------------------------

modify("cad.create_body", {"name": "HoleBody"})
modify(
    "cad.create_body_sketch",
    {"body": "HoleBody", "plane": "xy", "name": "HoleBase"},
)
modify(
    "cad.add_sketch_rectangle",
    {"sketch": "HoleBase", "x": -20, "y": -10, "width": 40, "height": 20},
)
hole_pad = modify(
    "cad.add_pad",
    {"body": "HoleBody", "sketch": "HoleBase", "length": 8, "name": "HolePad"},
)
assert close(40 * 20 * 8, hole_pad["volume_mm3"]), hole_pad["volume_mm3"]

modify(
    "cad.create_body_sketch",
    {"body": "HoleBody", "plane": "xy", "name": "HoleCenters"},
)
for center_x in (-10, 10):
    modify(
        "cad.add_sketch_circle",
        {"sketch": "HoleCenters", "center_x": center_x, "center_y": 0, "radius": 1},
    )
holes = modify(
    "cad.add_hole",
    {
        "body": "HoleBody",
        "sketch": "HoleCenters",
        "diameter": 5,
        "through_all": True,
        "reversed": True,
        "cut_type": "Counterbore",
        "cut_diameter": 10,
        "cut_depth": 3,
    },
)
drill = 2 * math.pi * 2.5 * 2.5 * 8
counterbore = 2 * math.pi * (5 * 5 - 2.5 * 2.5) * 3
assert close(
    40 * 20 * 8 - drill - counterbore, holes["volume_mm3"], 0.01
), holes["volume_mm3"]

resized = modify(
    "cad.edit_feature",
    {"feature": "AIHole", "properties": {"diameter": 6}},
)
resized_drill = 2 * math.pi * 3 * 3 * 8
resized_counterbore = 2 * math.pi * (5 * 5 - 3 * 3) * 3
assert close(
    40 * 20 * 8 - resized_drill - resized_counterbore,
    resized["volume_mm3"],
    0.01,
), resized["volume_mm3"]

# --- Master parameters driving the model (P3) ------------------------------

modify("cad.create_parameter_set", {"name": "Params"})
modify(
    "cad.set_master_parameter",
    {"name": "plate_width", "value": 30, "kind": "length"},
)
modify(
    "cad.set_master_parameter",
    {"name": "plate_height", "value": 6, "kind": "length"},
)

modify("cad.create_body", {"name": "ParamBody"})
modify(
    "cad.create_body_sketch",
    {"body": "ParamBody", "plane": "xy", "name": "ParamBase"},
)
modify(
    "cad.add_sketch_rectangle",
    {"sketch": "ParamBase", "x": 0, "y": 0, "width": 30, "height": 15},
)
width_dimension = modify(
    "cad.add_sketch_dimensional_constraint",
    {
        "sketch": "ParamBase",
        "constraint_type": "length",
        "geometry": 0,
        "value": 30,
    },
)
modify(
    "cad.rename_sketch_constraint",
    {
        "sketch": "ParamBase",
        "constraint": width_dimension["added_constraint"],
        "name": "plate_width",
    },
)
bound_datum = modify(
    "cad.bind_sketch_datum",
    {
        "sketch": "ParamBase",
        "constraint": "plate_width",
        "expression": "Params.plate_width",
    },
)
assert bound_datum["value"] == 30, bound_datum

param_pad = modify(
    "cad.add_pad",
    {"body": "ParamBody", "sketch": "ParamBase", "length": 6, "name": "ParamPad"},
)
assert close(30 * 15 * 6, param_pad["volume_mm3"]), param_pad["volume_mm3"]
bound_feature = modify(
    "cad.bind_feature_parameter",
    {
        "feature": "ParamPad",
        "parameter": "length",
        "expression": "Params.plate_height",
    },
)
assert bound_feature["value"] == 6, bound_feature

# One parameter change recomputes sketch AND feature: the money shot.
modify(
    "cad.set_master_parameter",
    {"name": "plate_width", "value": 50, "kind": "length"},
)
modify(
    "cad.set_master_parameter",
    {"name": "plate_height", "value": 10, "kind": "length"},
)
recomputed = read("cad.measure_object", {"object": "ParamBody"})
assert close(50 * 15 * 10, recomputed["volume_mm3"]), recomputed["volume_mm3"]

listing = read("cad.list_master_parameters", {})
assert listing["count"] == 1, listing
parameter_names = {
    item["name"] for item in listing["sets"][0]["parameters"]
}
assert parameter_names == {"plate_width", "plate_height"}, listing

# Unsafe expressions must be rejected before touching FreeCAD.
try:
    modify(
        "cad.bind_feature_parameter",
        {
            "feature": "ParamPad",
            "parameter": "length",
            "expression": "sin(Params.plate_height)",
        },
    )
    raise AssertionError("A function-call expression must be rejected.")
except ValueError:
    pass

# Clearing a binding restores direct dimensional editing.
cleared = modify(
    "cad.bind_feature_parameter",
    {"feature": "ParamPad", "parameter": "length", "expression": None},
)
assert cleared["expression"] is None, cleared
modify("cad.edit_feature", {"feature": "ParamPad", "properties": {"length": 4}})
direct = read("cad.measure_object", {"object": "ParamBody"})
assert close(50 * 15 * 4, direct["volume_mm3"]), direct["volume_mm3"]

# --- Guard rails ----------------------------------------------------------

try:
    modify("cad.add_pad", {"sketch": "RingProfile", "length": 5, "body": "MainBody"})
    raise AssertionError("A sketch outside the body must be rejected.")
except ValueError:
    pass

try:
    modify(
        "cad.edit_feature",
        {"feature": "AIPad", "properties": {"angle": 90}},
    )
    raise AssertionError("A property outside the type allowlist must be rejected.")
except ValueError:
    pass

undo = modify("cad.undo", {})
assert undo["undone"] is True

print("FREECAD_PARTDESIGN_SMOKE_OK")

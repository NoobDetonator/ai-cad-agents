from itertools import combinations
from pathlib import Path
import sys


project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

import FreeCAD as App

from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.application import build_cad_tool_registry


for document_name in list(App.listDocuments()):
    App.closeDocument(document_name)

document = App.newDocument("BearingToolSmoke")
document.UndoMode = 1
adapter = FreeCadAdapter()
registry = build_cad_tool_registry(adapter)


def modify(name: str, arguments: dict):
    return registry.execute(name, arguments, confirmed=True)


def assert_valid_non_interfering_compound(name: str, tolerance: float = 1e-5) -> None:
    item = document.getObject(name)
    assert item is not None
    assert not item.Shape.isNull()
    assert item.Shape.isValid()
    assert item.Shape.Volume > 0
    for left, right in combinations(item.Shape.Solids, 2):
        distance, _, _ = left.distToShape(right)
        if distance <= 1e-7:
            common = left.common(right)
            assert common.isNull() or common.Volume <= tolerance


deep = modify(
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
        "name": "DeepGroove6201Like",
    },
)
assert deep["bearing_type"] == "deep_groove_ball"
assert deep["ball_count"] == 8
assert deep["has_cage"] is True
assert_valid_non_interfering_compound("DeepGroove6201Like")

thrust = modify(
    "cad.create_thrust_ball_bearing",
    {
        "bore_diameter": 20,
        "outer_diameter": 42,
        "height": 14,
        "ball_count": 8,
        "ball_diameter": 6,
        "axial_clearance": 0.08,
        "groove_conformity": 1.04,
        "cage": True,
        "name": "SingleDirectionThrust",
    },
)
assert thrust["load_direction"] == "axial_z_single_direction"
assert thrust["ball_count"] == 8
assert_valid_non_interfering_compound("SingleDirectionThrust")

roller = modify(
    "cad.create_cylindrical_roller_bearing",
    {
        "bore_diameter": 20,
        "outer_diameter": 47,
        "width": 14,
        "roller_count": 12,
        "roller_diameter": 6,
        "roller_length": 11,
        "radial_clearance": 0.08,
        "cage": True,
        "name": "CylindricalRoller",
    },
)
assert roller["bearing_type"] == "cylindrical_roller"
assert roller["roller_count"] == 12
assert_valid_non_interfering_compound("CylindricalRoller")

printed = modify(
    "cad.create_print_in_place_roller_bearing",
    {
        "bore_diameter": 20,
        "outer_diameter": 50,
        "width": 16,
        "roller_count": 12,
        "roller_diameter": 6,
        "print_clearance": 0.4,
        "axial_clearance": 1.8,
        "name": "PrintInPlaceRoller",
    },
)
assert printed["print_orientation"] == "axis_z_upright"
assert printed["retaining_rim_angle_deg"] == 45
assert printed["solid_count"] == 14
assert_valid_non_interfering_compound("PrintInPlaceRoller")

bushing = modify(
    "cad.create_printed_plain_bushing",
    {
        "shaft_diameter": 12,
        "outer_diameter": 18,
        "length": 20,
        "running_clearance": 0.4,
        "channel_count": 6,
        "channel_width": 0.8,
        "channel_depth": 0.4,
        "elephant_foot_relief": 0.2,
        "name": "PrintedPolymerBushing",
    },
)
assert bushing["running_bore_diameter_mm"] == 12.4
assert bushing["channel_count"] == 6
assert bushing["solid_count"] == 1
assert_valid_non_interfering_compound("PrintedPolymerBushing")

assert adapter.validate_document()["valid"] is True
assert modify("cad.undo", {})["undone"] is True
assert document.getObject("PrintedPolymerBushing") is None
assert adapter.validate_document()["valid"] is True

print("FREECAD_BEARINGS_SMOKE_OK")
App.closeDocument(document.Name)

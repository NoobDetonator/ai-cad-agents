from pathlib import Path
import sys


project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

import FreeCAD as App

from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.application import build_cad_tool_registry


for document_name in list(App.listDocuments()):
    App.closeDocument(document_name)

document = App.newDocument("AssemblyToolSmoke")
document.UndoMode = 1
adapter = FreeCadAdapter()
registry = build_cad_tool_registry(adapter)


def modify(name: str, arguments: dict):
    return registry.execute(name, arguments, confirmed=True)


ring = modify(
    "cad.create_internal_gear",
    {
        "teeth": 24,
        "module": 2,
        "thickness": 12,
        "rim_thickness": 8,
        "pressure_angle": 20,
        "name": "SmokeRingRaw",
    },
)
assert ring["pitch_diameter_mm"] == 48
assert ring["outside_diameter_mm"] == 69
assert document.SmokeRingRaw.Shape.isValid()
assert len(document.SmokeRingRaw.Shape.Solids) == 1

ring_backlash = modify(
    "cad.apply_gear_backlash",
    {"object": "SmokeRingRaw", "backlash": 0.12, "name": "SmokeRing"},
)
assert ring_backlash["volume_removed_mm3"] > 0
assert document.SmokeRing.InternalGear is True
assert abs(document.SmokeRing.Backlash.Value - 0.12) < 1e-9

planet = modify(
    "cad.create_spur_gear",
    {
        "teeth": 6,
        "module": 2,
        "thickness": 10,
        "bore_diameter": 6,
        "pressure_angle": 20,
        "name": "SmokePlanetRaw",
    },
)
assert planet["pitch_diameter_mm"] == 12
modify(
    "cad.apply_gear_backlash",
    {"object": "SmokePlanetRaw", "backlash": 0.12, "name": "SmokePlanet"},
)
modify(
    "cad.translate_object",
    {"object": "SmokePlanet", "dx": 18, "dz": 1},
)
mesh_analysis = registry.execute(
    "cad.analyze_interferences",
    {
        "objects": ["SmokePlanet", "SmokeRing"],
        "minimum_clearance": 0,
        "volume_tolerance": 0.05,
    },
)
assert mesh_analysis["pair_count"] == 1
assert mesh_analysis["pairs"][0]["status"] in {
    "clear",
    "contact",
    "interference",
}

carrier = modify(
    "cad.create_planetary_carrier",
    {
        "plate_diameter": 96,
        "thickness": 6,
        "center_bore_diameter": 12,
        "planet_count": 3,
        "planet_pitch_diameter": 72,
        "pin_hole_diameter": 6.2,
        "name": "SmokeCarrier",
    },
)
assert carrier["planet_count"] == 3
assert document.SmokeCarrier.Shape.isValid()
assert len(document.SmokeCarrier.Shape.Solids) == 1

bearing = modify(
    "cad.create_ball_bearing",
    {
        "bore_diameter": 12,
        "outer_diameter": 32,
        "width": 10,
        "ball_count": 8,
        "ball_diameter": 5,
        "radial_clearance": 0.05,
        "name": "SmokeBearing",
    },
)
assert bearing["solid_count"] == 10
assert document.SmokeBearing.Shape.isValid()

modify(
    "cad.create_cylinder",
    {"diameter": 12, "height": 30, "name": "SmokeShaft"},
)
modify(
    "cad.translate_object",
    {"object": "SmokeShaft", "dx": 10, "dy": -6},
)
alignment = modify(
    "cad.align_concentric",
    {
        "moving": "SmokeBearing",
        "reference": "SmokeShaft",
        "z_alignment": "base",
        "axial_offset": 8,
    },
)
assert alignment["position_mm"] == [10.0, -6.0, 8.0]
assert document.SmokeBearing.AlignmentReference is document.SmokeShaft

bearing_analysis = registry.execute(
    "cad.analyze_interferences",
    {
        "objects": ["SmokeBearing", "SmokeShaft"],
        "minimum_clearance": 0,
        "volume_tolerance": 0.01,
    },
)
assert bearing_analysis["interference_count"] == 0
assert bearing_analysis["contact_count"] == 1
assert adapter.validate_document()["valid"] is True

assert modify("cad.undo", {})["undone"] is True
assert not hasattr(document.SmokeBearing, "AlignmentReference")
assert adapter.validate_document()["valid"] is True

print("FREECAD_ASSEMBLY_SMOKE_OK")
App.closeDocument(document.Name)

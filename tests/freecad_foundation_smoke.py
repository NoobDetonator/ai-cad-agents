from pathlib import Path
import math
import sys


project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.application import build_cad_tool_registry

import FreeCAD as App


def close_enough(actual: float, expected: float, *, tolerance: float = 1e-6) -> None:
    assert math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance), (
        actual,
        expected,
    )


for open_name in list(App.listDocuments()):
    App.closeDocument(open_name)

document = App.newDocument("AICadFoundationSmoke")
document.UndoMode = 1
adapter = FreeCadAdapter()
registry = build_cad_tool_registry(adapter)

cone = registry.execute(
    "cad.create_cone",
    {
        "bottom_diameter": 30,
        "top_diameter": 10,
        "height": 40,
        "name": "FoundationCone",
    },
    confirmed=True,
)
close_enough(
    cone["volume_mm3"],
    math.pi * 40 * (30**2 + 30 * 10 + 10**2) / 12,
)
assert document.getObject("FoundationCone").TypeId == "Part::Cone"

sphere = registry.execute(
    "cad.create_sphere",
    {"diameter": 20, "name": "FoundationSphere"},
    confirmed=True,
)
close_enough(sphere["volume_mm3"], math.pi * 20**3 / 6)
assert document.getObject("FoundationSphere").TypeId == "Part::Sphere"

torus = registry.execute(
    "cad.create_torus",
    {
        "major_diameter": 40,
        "tube_diameter": 8,
        "name": "FoundationTorus",
    },
    confirmed=True,
)
close_enough(torus["volume_mm3"], math.pi**2 * 40 * 8**2 / 4)
assert document.getObject("FoundationTorus").TypeId == "Part::Torus"

registry.execute(
    "cad.create_box",
    {"length": 20, "width": 10, "height": 5, "name": "FoundationBase"},
    confirmed=True,
)
duplicate = registry.execute(
    "cad.duplicate_object",
    {
        "object": "FoundationBase",
        "name": "FoundationCopy",
        "offset_x": 40,
    },
    confirmed=True,
)
assert duplicate["source"] == "FoundationBase"
assert document.getObject("FoundationCopy").TypeId == "Part::Feature"
assert document.getObject("FoundationCopy").CopiedFrom == "FoundationBase"
distance = registry.execute(
    "cad.measure_distance",
    {"left": "FoundationBase", "right": "FoundationCopy"},
)
close_enough(distance["minimum_distance_mm"], 20)
close_enough(distance["center_distance_mm"], 40)
assert len(distance["closest_points_mm"]) == 2
assert distance["intersects_or_touches"] is False

before_translate = adapter.measure_object("FoundationCopy")
translated = registry.execute(
    "cad.translate_object",
    {"object": "FoundationCopy", "dy": 20},
    confirmed=True,
)
assert translated["position_mm"] == [40.0, 20.0, 0.0]
assert adapter.undo()["undone"] is True
assert adapter.measure_object("FoundationCopy")["center_mm"] == before_translate["center_mm"]
registry.execute(
    "cad.translate_object",
    {"object": "FoundationCopy", "dy": 20},
    confirmed=True,
)

before_rotate = adapter.measure_object("FoundationCopy")
rotated = registry.execute(
    "cad.rotate_object",
    {
        "object": "FoundationCopy",
        "axis": "z",
        "angle": 90,
        "pivot": "object_center",
    },
    confirmed=True,
)
after_rotate = adapter.measure_object("FoundationCopy")
for actual, expected in zip(
    after_rotate["center_mm"], before_rotate["center_mm"], strict=True
):
    close_enough(actual, expected)
close_enough(after_rotate["length_mm"], before_rotate["width_mm"])
close_enough(after_rotate["width_mm"], before_rotate["length_mm"])
assert rotated["pivot"] == "object_center"
assert adapter.undo()["undone"] is True
after_rotate_undo = adapter.measure_object("FoundationCopy")
for actual, expected in zip(
    after_rotate_undo["bounds_mm"], before_rotate["bounds_mm"], strict=True
):
    close_enough(actual, expected)

registry.execute(
    "cad.create_through_hole",
    {
        "object": "FoundationBase",
        "diameter": 2,
        "x": 10,
        "y": 5,
        "name": "FoundationBaseHole",
    },
    confirmed=True,
)
undo_count = document.UndoCount
try:
    registry.execute(
        "cad.delete_object",
        {"object": "FoundationBase"},
        confirmed=True,
    )
except ValueError as exc:
    assert "used by other document objects" in str(exc)
else:
    raise AssertionError("A dependency-protected object was deleted.")
assert document.UndoCount == undo_count
assert document.getObject("FoundationBase") is not None
assert adapter.undo()["undone"] is True
assert document.getObject("FoundationBaseHole") is None

before_delete = adapter.get_context_snapshot()["state_token"]["document_fingerprint"]
deleted = registry.execute(
    "cad.delete_object",
    {"object": "FoundationCopy"},
    confirmed=True,
)
assert deleted == {
    "name": "FoundationCopy",
    "label": "FoundationCopy",
    "deleted": True,
}
assert document.getObject("FoundationCopy") is None
assert adapter.undo()["undone"] is True
assert document.getObject("FoundationCopy") is not None
after_delete_undo = adapter.get_context_snapshot()["state_token"]["document_fingerprint"]
assert after_delete_undo == before_delete

assert registry.execute("cad.validate_document", {})["valid"] is True
print("FREECAD_FOUNDATION_SMOKE_OK")
App.closeDocument(document.Name)

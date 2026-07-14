from __future__ import annotations

from pathlib import Path
import math
import os
import sys


project_root = Path(os.environ["AICAD_PROJECT_ROOT"])
sys.path.insert(0, str(project_root / "src"))

import FreeCAD as App

from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.application import build_cad_tool_registry
from aicad.core.context import DocumentStateToken
from aicad.orchestration.plan_service import (
    CompositeApprovalGrant,
    CompositePlanExecutor,
    CompositeValidatedPlan,
    PlanService,
)
from aicad.orchestration.recipes import default_recipe_catalog


for document_name in list(App.listDocuments()):
    App.closeDocument(document_name)

document = App.newDocument("AICadM4Smoke")
document.UndoMode = 1
adapter = FreeCadAdapter()
registry = build_cad_tool_registry(adapter)


def fingerprint() -> str:
    return adapter.get_context_snapshot()["state_token"]["document_fingerprint"]


def execute_and_undo(name: str, arguments: dict[str, object]):
    before = fingerprint()
    result = registry.execute(name, arguments, confirmed=True)
    assert result["valid"] is True
    assert adapter.validate_document()["valid"] is True
    assert fingerprint() != before
    undone = registry.execute("cad.undo", confirmed=True)
    assert undone["undone"] is True
    assert fingerprint() == before
    return result


plate = registry.execute(
    "cad.create_plate",
    {"length": 100, "width": 60, "thickness": 8, "name": "M4Plate"},
    confirmed=True,
)
assert plate["volume_mm3"] == 48000
details = registry.execute("cad.get_object_details", {"object": "M4Plate"})
assert details["status"] == "resolved"
assert len(details["edge_references"]) == 12
measure = registry.execute("cad.measure_object", {"object": "M4Plate"})
assert measure["length_mm"] == 100
assert measure["width_mm"] == 60
assert measure["height_mm"] == 8
editable = registry.execute("cad.get_editable_parameters", {"object": "M4Plate"})
assert {item["name"] for item in editable["parameters"]} == {
    "Length",
    "Width",
    "Height",
}
resolved = registry.execute("cad.resolve_object", {"reference": "M4Plate"})
assert resolved["object"]["name"] == "M4Plate"

execute_and_undo(
    "cad.rename_object",
    {"object": "M4Plate", "name": "MountingPlate"},
)
execute_and_undo(
    "cad.set_parameter",
    {"object": "M4Plate", "parameter": "Height", "value": 10},
)
execute_and_undo(
    "cad.transform_object",
    {"object": "M4Plate", "x": 5, "y": 2, "yaw": 15},
)

before_hole = fingerprint()
hole = registry.execute(
    "cad.create_through_hole",
    {
        "object": "M4Plate",
        "diameter": 10,
        "x": 50,
        "y": 30,
        "name": "M4CenterHole",
    },
    confirmed=True,
)
assert hole["hole_count"] == 1
dependencies = registry.execute(
    "cad.get_dependencies",
    {"object": "M4CenterHole"},
)
assert [item["name"] for item in dependencies["depends_on"]] == ["M4Plate"]
assert registry.execute("cad.undo", confirmed=True)["undone"] is True
assert fingerprint() == before_hole

pattern = registry.execute(
    "cad.create_rectangular_hole_pattern",
    {
        "object": "M4Plate",
        "diameter": 6,
        "rows": 2,
        "columns": 2,
        "spacing_x": 70,
        "spacing_y": 30,
        "origin_x": 15,
        "origin_y": 15,
        "name": "M4Grid",
    },
    confirmed=True,
)
assert pattern["hole_count"] == 4
assert registry.execute("cad.undo", confirmed=True)["undone"] is True

disc = registry.execute(
    "cad.create_cylinder",
    {"diameter": 100, "height": 10, "name": "M4FlangeBlank"},
    confirmed=True,
)
assert disc["valid"] is True
circular = registry.execute(
    "cad.create_circular_hole_pattern",
    {
        "object": "M4FlangeBlank",
        "diameter": 8,
        "count": 6,
        "pitch_diameter": 70,
        "start_angle": 0,
        "name": "M4BoltCircle",
    },
    confirmed=True,
)
assert circular["hole_count"] == 6
assert registry.execute("cad.undo", confirmed=True)["undone"] is True

sketch = registry.execute(
    "cad.create_rectangular_sketch",
    {"width": 40, "height": 20, "name": "M4Profile"},
    confirmed=True,
)
assert sketch["geometry_count"] == 4
pad = registry.execute(
    "cad.pad_sketch",
    {"sketch": "M4Profile", "length": 12, "name": "M4Pad"},
    confirmed=True,
)
assert math.isclose(pad["volume_mm3"], 9600, rel_tol=1e-9)
assert registry.execute("cad.undo", confirmed=True)["undone"] is True

left = registry.execute(
    "cad.create_box",
    {"length": 20, "width": 20, "height": 20, "name": "M4BoolLeft"},
    confirmed=True,
)
right = registry.execute(
    "cad.create_box",
    {"length": 20, "width": 20, "height": 20, "name": "M4BoolRight"},
    confirmed=True,
)
assert left["valid"] and right["valid"]
registry.execute(
    "cad.transform_object",
    {"object": "M4BoolRight", "x": 10},
    confirmed=True,
)
for operation in ("fuse", "cut", "common"):
    boolean = registry.execute(
        "cad.boolean_operation",
        {
            "left": "M4BoolLeft",
            "right": "M4BoolRight",
            "operation": operation,
            "name": "M4Boolean" + operation.title(),
        },
        confirmed=True,
    )
    assert boolean["volume_mm3"] > 0
    assert registry.execute("cad.undo", confirmed=True)["undone"] is True

finish_box = registry.execute(
    "cad.create_box",
    {"length": 30, "width": 20, "height": 10, "name": "M4FinishBox"},
    confirmed=True,
)
assert finish_box["valid"] is True
edge_reference = registry.execute(
    "cad.get_object_details",
    {"object": "M4FinishBox"},
)["edge_references"][0]["reference"]
execute_and_undo(
    "cad.fillet_edges",
    {
        "object": "M4FinishBox",
        "radius": 1,
        "edge_reference": edge_reference,
        "name": "M4Fillet",
    },
)
execute_and_undo(
    "cad.chamfer_edges",
    {
        "object": "M4FinishBox",
        "size": 1,
        "edge_reference": edge_reference,
        "name": "M4Chamfer",
    },
)

try:
    registry.execute(
        "cad.create_through_hole",
        {
            "object": "M4Plate",
            "diameter": 5,
            "x": 500,
            "y": 500,
            "name": "M4InvalidHole",
        },
        confirmed=True,
    )
except ValueError:
    pass
else:
    raise AssertionError("A non-intersecting hole was not rejected.")
assert document.getObject("M4InvalidHole") is None
assert adapter.validate_document()["valid"] is True

recipes = (
    (
        "mounting_plate",
        {
            "length": 80,
            "width": 50,
            "thickness": 6,
            "hole_diameter": 5,
            "edge_offset": 8,
            "name": "RecipePlateBlank",
            "result_name": "RecipePlate",
        },
    ),
    (
        "flange",
        {
            "outer_diameter": 90,
            "thickness": 10,
            "hole_diameter": 7,
            "hole_count": 6,
            "pitch_diameter": 65,
            "name": "RecipeFlangeBlank",
            "result_name": "RecipeFlange",
        },
    ),
    (
        "rectangular_pad",
        {
            "width": 25,
            "height": 15,
            "length": 9,
            "sketch_name": "RecipePadSketch",
            "result_name": "RecipePad",
        },
    ),
)
catalog = default_recipe_catalog()
for recipe_id, parameters in recipes:
    baseline = fingerprint()
    proposal = catalog.create_plan(recipe_id, parameters, registry)
    plan = CompositeValidatedPlan.build(
        proposal,
        DocumentStateToken.model_validate(
            adapter.get_context_snapshot()["state_token"]
        ),
        registry,
    )
    service = PlanService()
    service.submit(plan)
    execution = service.execute(
        plan.plan_id,
        CompositeApprovalGrant.issue(plan),
        CompositePlanExecutor(registry, adapter.get_context_snapshot),
    )
    assert len(execution.results) == 2
    assert registry.execute("cad.undo", confirmed=True)["undone"] is True
    assert registry.execute("cad.undo", confirmed=True)["undone"] is True
    assert fingerprint() == baseline

App.closeDocument(document.Name)
print("FREECAD_M4_SMOKE_OK")

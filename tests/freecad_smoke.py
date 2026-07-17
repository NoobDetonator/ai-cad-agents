from pathlib import Path
import math
import sys


project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.application import build_cad_tool_registry
from aicad.core.context import DocumentStateToken
from aicad.core.tool_registry import build_default_registry
from aicad.orchestration import OrchestrationPlan, PlannedToolCall
from aicad.orchestration.plan_service import (
    CompositeApprovalGrant,
    CompositePlanError,
    CompositePlanExecutor,
    CompositeValidatedPlan,
)
from aicad.orchestration.plans import (
    ApprovalGrant,
    SingleMutationPlanExecutor,
    ValidatedPlan,
)

import FreeCAD as App


for document_name in list(App.listDocuments()):
    App.closeDocument(document_name)
App.newDocument("AICadSmokeTest")
adapter = FreeCadAdapter()
result = adapter.create_box(10, 20, 30, "SmokeTestBox")
cylinder_result = adapter.create_cylinder(30, 60, "SmokeTestCylinder")
validation = adapter.validate_document()
context = adapter.get_context_snapshot()

assert result["valid"] is True
assert result["volume_mm3"] == 6000.0
assert cylinder_result["valid"] is True
assert math.isclose(
    cylinder_result["volume_mm3"],
    math.pi * 15**2 * 60,
    rel_tol=1e-9,
)
assert validation["valid"] is True, validation
assert context["active"] is True
assert context["summary"]["object_count"] == 2
assert set(context["recent_objects"]) == {"SmokeTestBox", "SmokeTestCylinder"}
assert context["state_token"]["revision"] == 1
stable_context = adapter.get_context_snapshot()
assert stable_context["state_token"] == context["state_token"]
App.ActiveDocument.getObject("SmokeTestBox").Length = 11
App.ActiveDocument.recompute()
manual_context = adapter.get_context_snapshot()
assert manual_context["state_token"]["revision"] == 2
assert manual_context["state_token"] != context["state_token"]
box_context = next(
    item for item in manual_context["objects"] if item["name"] == "SmokeTestBox"
)
assert box_context["parameters"]["Length"] == 11
assert len(App.ActiveDocument.Objects) == 2
assert App.ActiveDocument.UndoCount == 2
undo_result = adapter.undo()
assert undo_result["undone"] is True
assert len(App.ActiveDocument.Objects) == 1
assert App.ActiveDocument.Objects[0].Label == "SmokeTestBox"
undo_result = adapter.undo()
assert undo_result["undone"] is True
assert len(App.ActiveDocument.Objects) == 0

registry = build_cad_tool_registry(adapter)
base_context = adapter.get_context_snapshot()
proposed_plan = OrchestrationPlan(
    intention="Criar caixa aprovada.",
    assumptions=(),
    steps=("Criar e validar uma caixa.",),
    message="Plano transacional.",
    tool_calls=(
        PlannedToolCall(
            call_id="smoke-plan-box-1",
            name="cad.create_box",
            arguments={
                "length": 4,
                "width": 5,
                "height": 6,
                "name": "ApprovedSmokeBox",
            },
            risk="modify",
            requires_confirmation=True,
        ),
    ),
)
validated_plan = ValidatedPlan.build(
    proposed_plan,
    DocumentStateToken.model_validate(base_context["state_token"]),
    registry,
)
execution = SingleMutationPlanExecutor(
    registry,
    adapter.get_context_snapshot,
).execute(validated_plan, ApprovalGrant.issue(validated_plan))
assert execution.tool_result["label"] == "ApprovedSmokeBox"
assert execution.validation_result["valid"] is True
assert execution.state_after.revision > execution.state_before.revision
assert len(App.ActiveDocument.Objects) == 1
assert adapter.undo()["undone"] is True
assert len(App.ActiveDocument.Objects) == 0

composite_proposal = OrchestrationPlan(
    intention="Criar dois sólidos aprovados.",
    assumptions=(),
    steps=("Criar caixa.", "Criar cilindro."),
    message="Plano composto transacional.",
    tool_calls=(
        PlannedToolCall(
            call_id="smoke-composite-box-1",
            name="cad.create_box",
            arguments={
                "length": 3,
                "width": 4,
                "height": 5,
                "name": "CompositeBox",
            },
            risk="modify",
            requires_confirmation=True,
        ),
        PlannedToolCall(
            call_id="smoke-composite-cylinder-1",
            name="cad.create_cylinder",
            arguments={
                "diameter": 6,
                "height": 12,
                "name": "CompositeCylinder",
            },
            risk="modify",
            requires_confirmation=True,
        ),
    ),
)
composite_base = adapter.get_context_snapshot()
composite_plan = CompositeValidatedPlan.build(
    composite_proposal,
    DocumentStateToken.model_validate(composite_base["state_token"]),
    registry,
)
composite_result = CompositePlanExecutor(
    registry,
    adapter.get_context_snapshot,
).execute(composite_plan, CompositeApprovalGrant.issue(composite_plan))
assert len(composite_result.results) == 2
assert len(App.ActiveDocument.Objects) == 2
assert adapter.undo()["undone"] is True
assert adapter.undo()["undone"] is True
assert len(App.ActiveDocument.Objects) == 0

rollback_registry = build_default_registry()
rollback_registry.bind("cad.create_box", adapter.create_box)
rollback_registry.bind("cad.create_cylinder", adapter.create_cylinder)
validation_calls = [0]


def fail_second_validation():
    validation_calls[0] += 1
    if validation_calls[0] == 2:
        return {"valid": False, "errors": ["Injected smoke failure."]}
    return adapter.validate_document()


rollback_registry.bind("cad.validate_document", fail_second_validation)
rollback_registry.bind("cad.undo", adapter.undo)
rollback_base = adapter.get_context_snapshot()
rollback_plan = CompositeValidatedPlan.build(
    composite_proposal,
    DocumentStateToken.model_validate(rollback_base["state_token"]),
    rollback_registry,
)
try:
    CompositePlanExecutor(
        rollback_registry,
        adapter.get_context_snapshot,
    ).execute(rollback_plan, CompositeApprovalGrant.issue(rollback_plan))
except CompositePlanError:
    pass
else:
    raise AssertionError("Injected composite failure was not reported.")
assert len(App.ActiveDocument.Objects) == 0
restored_context = adapter.get_context_snapshot()
assert (
    restored_context["state_token"]["document_fingerprint"]
    == rollback_base["state_token"]["document_fingerprint"]
)
# P5 — massa com densidade e prontidão de impressão em geometria conhecida.
mass_box = adapter.create_box(10, 20, 30, "MassSampleBox")
assert mass_box["valid"] is True
mass = adapter.measure_mass_properties("MassSampleBox", 2.0)
assert math.isclose(mass["volume_mm3"], 6000.0, rel_tol=1e-9)
assert math.isclose(mass["mass_g"], 12.0, rel_tol=1e-9)
assert math.isclose(mass["mass_kg"], 0.012, rel_tol=1e-9)
assert math.isclose(mass["center_of_mass_mm"][0], 5.0, abs_tol=1e-6)
assert math.isclose(mass["center_of_mass_mm"][1], 10.0, abs_tol=1e-6)
assert math.isclose(mass["center_of_mass_mm"][2], 15.0, abs_tol=1e-6)
assert mass["solids"] == 1 and mass["valid"] is True

readiness = adapter.analyze_print_readiness("MassSampleBox")
assert readiness["needs_support"] is False, readiness
assert readiness["closed_solids"] == 1
assert math.isclose(readiness["bed_contact_area_mm2"], 200.0, rel_tol=1e-9)
assert readiness["overhang_faces"] == []
assert readiness["floating_solids"] == []

floating_box = adapter.create_box(10, 10, 10, "FloatingSampleBox")
assert floating_box["valid"] is True
adapter.translate_object("FloatingSampleBox", dz=40)
fused = adapter.boolean_operation(
    "MassSampleBox", "FloatingSampleBox", "fuse", "PrintSample"
)
assert fused["valid"] is True
floating_readiness = adapter.analyze_print_readiness("PrintSample")
assert floating_readiness["needs_support"] is True, floating_readiness
assert floating_readiness["solids"] == 2
assert len(floating_readiness["floating_solids"]) == 1
assert math.isclose(
    floating_readiness["floating_solids"][0]["gap_mm"], 40.0, abs_tol=1e-6
)
assert math.isclose(
    floating_readiness["overhang_area_mm2"], 100.0, rel_tol=1e-9
), floating_readiness
assert floating_readiness["overhang_faces"][0]["downward_angle_deg"] < 1e-6
compound_mass = adapter.measure_mass_properties("PrintSample", 1.24)
assert math.isclose(compound_mass["volume_mm3"], 7000.0, rel_tol=1e-9)
assert math.isclose(compound_mass["mass_g"], 8.68, rel_tol=1e-9)

print("FREECAD_SMOKE_OK")
App.closeDocument("AICadSmokeTest")

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
print("FREECAD_SMOKE_OK")
App.closeDocument("AICadSmokeTest")

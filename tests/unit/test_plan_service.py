from __future__ import annotations

import hashlib
import json
from uuid import UUID

import pytest

from aicad.core.context import DocumentStateToken
from aicad.core.tool_registry import build_default_registry
from aicad.orchestration import OrchestrationPlan, PlannedToolCall
from aicad.orchestration.plan_service import (
    CompositeApprovalGrant,
    CompositePlanError,
    CompositePlanExecutor,
    CompositePlanStatus,
    CompositeRollbackError,
    CompositeValidatedPlan,
    PlanService,
)


SESSION = UUID("12345678-1234-5678-1234-567812345678")


class FakeCad:
    def __init__(
        self,
        *,
        fail_cylinder: bool = False,
        fail_undo: bool = False,
    ) -> None:
        self.objects: list[str] = []
        self.history: list[str] = []
        self.revision = 1
        self.fail_cylinder = fail_cylinder
        self.fail_undo = fail_undo
        self.calls: list[str] = []

    def create_box(self, **arguments):
        self.calls.append("box")
        name = str(arguments.get("name", "Box"))
        self.objects.append(name)
        self.history.append(name)
        self.revision += 1
        return {"name": name, "valid": True}

    def create_cylinder(self, **arguments):
        self.calls.append("cylinder")
        if self.fail_cylinder:
            raise RuntimeError("injected failure")
        name = str(arguments.get("name", "Cylinder"))
        self.objects.append(name)
        self.history.append(name)
        self.revision += 1
        return {"name": name, "valid": True}

    def validate(self):
        self.calls.append("validate")
        return {"valid": True, "errors": []}

    def undo(self):
        self.calls.append("undo")
        if self.fail_undo:
            return {"undone": False}
        if not self.history:
            return {"undone": False}
        name = self.history.pop()
        self.objects.remove(name)
        self.revision += 1
        return {"undone": True}

    def context(self):
        encoded = json.dumps(self.objects, separators=(",", ":")).encode()
        fingerprint = hashlib.sha256(encoded).hexdigest()
        return {
            "state_token": DocumentStateToken(
                session_id=SESSION,
                document_id="Document",
                revision=self.revision,
                document_fingerprint=fingerprint,
                selection_fingerprint="f" * 64,
            ).model_dump(mode="json")
        }


def registry_for(cad: FakeCad):
    registry = build_default_registry()
    registry.bind("cad.create_box", cad.create_box)
    registry.bind("cad.create_cylinder", cad.create_cylinder)
    registry.bind("cad.validate_document", cad.validate)
    registry.bind("cad.undo", cad.undo)
    return registry


def proposed_plan() -> OrchestrationPlan:
    return OrchestrationPlan(
        intention="Criar dois sólidos.",
        assumptions=(),
        steps=("Criar caixa.", "Criar cilindro."),
        message="Plano composto.",
        tool_calls=(
            PlannedToolCall(
                call_id="box-1",
                name="cad.create_box",
                arguments={
                    "length": 10,
                    "width": 20,
                    "height": 30,
                    "name": "Base",
                },
                risk="modify",
                requires_confirmation=True,
            ),
            PlannedToolCall(
                call_id="cylinder-1",
                name="cad.create_cylinder",
                arguments={"diameter": 8, "height": 20, "name": "Pin"},
                risk="modify",
                requires_confirmation=True,
            ),
        ),
    )


def frozen(cad: FakeCad, registry) -> CompositeValidatedPlan:
    token = DocumentStateToken.model_validate(cad.context()["state_token"])
    return CompositeValidatedPlan.build(proposed_plan(), token, registry)


def test_composite_plan_executes_every_step_after_one_approval() -> None:
    cad = FakeCad()
    registry = registry_for(cad)
    plan = frozen(cad, registry)
    service = PlanService()
    service.submit(plan)

    result = service.execute(
        plan.plan_id,
        CompositeApprovalGrant.issue(plan, now=10.0),
        CompositePlanExecutor(registry, cad.context, clock=lambda: 11.0),
    )

    assert cad.objects == ["Base", "Pin"]
    assert [item["name"] for item in result.results] == ["Base", "Pin"]
    status = service.get_status(plan.plan_id)
    assert status.status is CompositePlanStatus.COMPLETED
    assert status.completed_calls == 2


def test_failure_rolls_back_only_committed_plan_steps_and_restores_baseline() -> None:
    cad = FakeCad(fail_cylinder=True)
    registry = registry_for(cad)
    plan = frozen(cad, registry)
    baseline = cad.context()["state_token"]["document_fingerprint"]
    service = PlanService()
    service.submit(plan)

    with pytest.raises(CompositePlanError, match="rolled back"):
        service.execute(
            plan.plan_id,
            CompositeApprovalGrant.issue(plan, now=10.0),
            CompositePlanExecutor(registry, cad.context, clock=lambda: 11.0),
        )

    assert cad.objects == []
    assert cad.calls.count("box") == 1
    assert cad.calls.count("undo") == 1
    assert cad.context()["state_token"]["document_fingerprint"] == baseline
    assert service.get_status(plan.plan_id).status is CompositePlanStatus.ROLLED_BACK


def test_submit_status_and_cancel_are_idempotent() -> None:
    cad = FakeCad()
    registry = registry_for(cad)
    plan = frozen(cad, registry)
    service = PlanService()

    first = service.submit(plan)
    second = service.submit(plan)
    cancelled = service.cancel(plan.plan_id)
    cancelled_again = service.cancel(plan.plan_id)

    assert first == second
    assert cancelled.status is CompositePlanStatus.CANCELLED
    assert cancelled_again == cancelled
    assert service.get_status(plan.plan_id) == cancelled


def test_unverified_rollback_is_reported_as_failed_not_rolled_back() -> None:
    cad = FakeCad(fail_cylinder=True, fail_undo=True)
    registry = registry_for(cad)
    plan = frozen(cad, registry)
    service = PlanService()
    service.submit(plan)

    with pytest.raises(CompositeRollbackError):
        service.execute(
            plan.plan_id,
            CompositeApprovalGrant.issue(plan, now=10.0),
            CompositePlanExecutor(registry, cad.context, clock=lambda: 11.0),
        )

    status = service.get_status(plan.plan_id)
    assert status.status is CompositePlanStatus.FAILED
    assert status.error_code == "rollback_failed"


def test_all_calls_are_prevalidated_before_any_handler_runs() -> None:
    cad = FakeCad()
    registry = registry_for(cad)
    payload = proposed_plan().model_dump(mode="json")
    payload["tool_calls"][1]["arguments"]["diameter"] = 0
    invalid = OrchestrationPlan.model_validate(payload)
    token = DocumentStateToken.model_validate(cad.context()["state_token"])

    with pytest.raises(ValueError):
        CompositeValidatedPlan.build(invalid, token, registry)

    assert cad.calls == []

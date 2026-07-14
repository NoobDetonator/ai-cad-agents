from __future__ import annotations

import hashlib
import json
from uuid import UUID, uuid4

from aicad.bridge.plan_dispatcher import PlanBridgeDispatcher
from aicad.bridge.protocol import (
    BridgeErrorCode,
    BridgePlanCancelRequest,
    BridgePlanStatusRequest,
    BridgePlanSubmitRequest,
    BridgeResponseStatus,
)
from aicad.bridge.transport import LocalTcpBridgeServer, TcpBridgeClient
from aicad.core.context import DocumentStateToken
from aicad.core.tool_registry import build_default_registry
from aicad.orchestration import OrchestrationPlan, PlannedToolCall
from aicad.orchestration.plan_service import (
    CompositePlanStatus,
    CompositeValidatedPlan,
    PlanService,
)


SESSION_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


class FakeCad:
    def __init__(self) -> None:
        self.objects: list[str] = []
        self.history: list[str] = []
        self.revision = 1

    def create_box(self, **arguments):
        return self._create(str(arguments.get("name", "Box")))

    def create_cylinder(self, **arguments):
        return self._create(str(arguments.get("name", "Cylinder")))

    def _create(self, name: str):
        self.objects.append(name)
        self.history.append(name)
        self.revision += 1
        return {"name": name, "valid": True}

    def undo(self):
        if not self.history:
            return {"undone": False}
        self.objects.remove(self.history.pop())
        self.revision += 1
        return {"undone": True}

    def validate(self):
        return {"valid": True, "errors": []}

    def context(self):
        fingerprint = hashlib.sha256(
            json.dumps(self.objects, separators=(",", ":")).encode()
        ).hexdigest()
        return {
            "state_token": DocumentStateToken(
                session_id=SESSION_ID,
                document_id="Document",
                revision=self.revision,
                document_fingerprint=fingerprint,
                selection_fingerprint="f" * 64,
            ).model_dump(mode="json")
        }


def build_runtime():
    cad = FakeCad()
    registry = build_default_registry()
    registry.bind("cad.create_box", cad.create_box)
    registry.bind("cad.create_cylinder", cad.create_cylinder)
    registry.bind("cad.validate_document", cad.validate)
    registry.bind("cad.undo", cad.undo)
    proposal = OrchestrationPlan(
        intention="Criar uma base e um pino.",
        assumptions=(),
        steps=("Criar base.", "Criar pino."),
        message="Plano MCP.",
        tool_calls=(
            PlannedToolCall(
                call_id="box-1",
                name="cad.create_box",
                arguments={
                    "length": 10,
                    "width": 10,
                    "height": 4,
                    "name": "Base",
                },
                risk="modify",
                requires_confirmation=True,
            ),
            PlannedToolCall(
                call_id="pin-1",
                name="cad.create_cylinder",
                arguments={"diameter": 4, "height": 8, "name": "Pin"},
                risk="modify",
                requires_confirmation=True,
            ),
        ),
    )
    plan = CompositeValidatedPlan.build(
        proposal,
        DocumentStateToken.model_validate(cad.context()["state_token"]),
        registry,
    )
    confirmations: list[CompositeValidatedPlan] = []
    dispatcher = PlanBridgeDispatcher(
        registry,
        PlanService(),
        on_confirmation_requested=confirmations.append,
        context_reader=cad.context,
    )
    return cad, plan, confirmations, dispatcher


def test_submit_poll_and_confirm_use_one_gui_owned_plan_service() -> None:
    cad, plan, confirmations, dispatcher = build_runtime()
    submit = BridgePlanSubmitRequest(
        request_id=uuid4(),
        plan=plan,
        source="mcp",
    )

    first = dispatcher.submit(submit.model_dump(mode="json"))
    duplicate = dispatcher.submit(submit.model_dump(mode="json"))
    assert first == duplicate
    assert first.status is BridgeResponseStatus.COMPLETED
    assert first.result["status"] == CompositePlanStatus.AWAITING_APPROVAL
    assert cad.objects == []

    status_request = BridgePlanStatusRequest(
        request_id=uuid4(),
        plan_id=plan.plan_id,
        source="mcp",
    )
    awaiting = dispatcher.submit(status_request.model_dump(mode="json"))
    assert awaiting.result["status"] == CompositePlanStatus.AWAITING_APPROVAL

    assert dispatcher.process_next() is True
    assert confirmations == [plan]
    completed = dispatcher.resolve_confirmation(plan.plan_id, approved=True)
    assert completed.status is CompositePlanStatus.COMPLETED
    assert completed.completed_calls == 2
    assert cad.objects == ["Base", "Pin"]

    status = dispatcher.submit(status_request.model_dump(mode="json"))
    assert status.result["status"] == CompositePlanStatus.COMPLETED


def test_cancel_and_request_id_conflicts_are_idempotent() -> None:
    cad, plan, _, dispatcher = build_runtime()
    submit = BridgePlanSubmitRequest(
        request_id=uuid4(),
        plan=plan,
        source="mcp",
    )
    dispatcher.submit(submit.model_dump(mode="json"))
    dispatcher.process_next()

    cancel = BridgePlanCancelRequest(
        request_id=uuid4(),
        plan_id=plan.plan_id,
        source="mcp",
    )
    first = dispatcher.submit(cancel.model_dump(mode="json"))
    second = dispatcher.submit(cancel.model_dump(mode="json"))
    assert first == second
    assert first.result["status"] == CompositePlanStatus.CANCELLED
    assert dispatcher.resolve_confirmation(plan.plan_id, approved=True).status is (
        CompositePlanStatus.CANCELLED
    )
    assert cad.objects == []

    conflicting = cancel.model_copy(update={"plan_id": uuid4()})
    rejected = dispatcher.submit(conflicting.model_dump(mode="json"))
    assert rejected.status is BridgeResponseStatus.REJECTED
    assert rejected.error.code is BridgeErrorCode.INVALID_REQUEST


def test_plan_envelopes_round_trip_through_authenticated_transport() -> None:
    _, plan, _, dispatcher = build_runtime()
    request = BridgePlanSubmitRequest(
        request_id=uuid4(),
        plan=plan,
        source="mcp",
    )
    with LocalTcpBridgeServer(dispatcher.submit) as server:
        response = TcpBridgeClient(server.endpoint).request(request)

    assert response.status is BridgeResponseStatus.COMPLETED
    assert response.result["plan_id"] == str(plan.plan_id)
    assert response.result["status"] == CompositePlanStatus.AWAITING_APPROVAL

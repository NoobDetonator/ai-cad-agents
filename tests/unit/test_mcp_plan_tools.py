from uuid import UUID, uuid4

from aicad.bridge.protocol import (
    BridgePlanCancelRequest,
    BridgePlanStatusRequest,
    BridgePlanSubmitRequest,
    BridgeRequest,
    BridgeResponse,
    BridgeResponseStatus,
)
from aicad.core.context import DocumentStateToken
from aicad import mcp_server


def test_submit_cad_plan_freezes_the_gui_baseline_and_sends_one_plan(monkeypatch) -> None:
    sent = []
    token = DocumentStateToken(
        session_id=uuid4(),
        document_id="Document",
        revision=3,
        document_fingerprint="a" * 64,
        selection_fingerprint="b" * 64,
    )

    def send(request):
        sent.append(request)
        if isinstance(request, BridgeRequest):
            return BridgeResponse(
                request_id=request.request_id,
                status=BridgeResponseStatus.COMPLETED,
                result={"state_token": token.model_dump(mode="json")},
            )
        assert isinstance(request, BridgePlanSubmitRequest)
        return BridgeResponse(
            request_id=request.request_id,
            status=BridgeResponseStatus.COMPLETED,
            result={
                "plan_id": str(request.plan.plan_id),
                "status": "awaiting_approval",
            },
        )

    monkeypatch.setattr(mcp_server, "_send_bridge_request", send)
    response = mcp_server.submit_cad_plan(
        "Criar base e pino.",
        ["Criar a base.", "Criar o pino."],
        [
            {
                "name": "cad.create_box",
                "arguments": {
                    "length": 10,
                    "width": 8,
                    "height": 3,
                    "name": "Base",
                },
            },
            {
                "name": "cad.create_cylinder",
                "arguments": {"diameter": 4, "height": 7, "name": "Pin"},
            },
        ],
    )

    assert response["result"]["status"] == "awaiting_approval"
    assert len(sent) == 2
    submitted = sent[1]
    assert isinstance(submitted, BridgePlanSubmitRequest)
    assert submitted.plan.base_state_token == token
    assert [call.name for call in submitted.plan.calls] == [
        "cad.create_box",
        "cad.create_cylinder",
    ]


def test_mcp_status_and_cancel_tools_send_typed_control_envelopes(monkeypatch) -> None:
    plan_id = UUID("12345678-1234-4678-9234-567812345678")
    sent = []

    def send(request):
        sent.append(request)
        return BridgeResponse(
            request_id=request.request_id,
            status=BridgeResponseStatus.COMPLETED,
            result={"plan_id": str(plan_id), "status": "cancelled"},
        )

    monkeypatch.setattr(mcp_server, "_send_bridge_request", send)
    mcp_server.get_cad_plan_status(str(plan_id))
    mcp_server.cancel_cad_plan(str(plan_id))

    assert isinstance(sent[0], BridgePlanStatusRequest)
    assert isinstance(sent[1], BridgePlanCancelRequest)
    assert sent[0].plan_id == sent[1].plan_id == plan_id

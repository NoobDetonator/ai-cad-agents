import asyncio

import pytest

from aicad import mcp_server
from aicad.bridge.dispatcher import GUI_REQUEST_TIMEOUT_SECONDS
from aicad.bridge.protocol import (
    BridgeError,
    BridgeErrorCode,
    BridgeResponse,
    BridgeResponseStatus,
)
from aicad.bridge.session import BridgeSessionError
from aicad.bridge.transport import BridgeTransportError
from aicad.mcp_server import (
    available_cad_tools,
    describe_cad_capabilities,
    execute_cad_read_tool,
    request_cad_tool,
    search_cad_capabilities,
    tool_registry,
)
from aicad.runtime import get_tool_registry


def test_bridge_client_outwaits_the_gui_dispatcher() -> None:
    # The transport default is 5 s, but the GUI works a request for 120 s. A
    # client that hangs up first reports the bridge as unavailable while
    # FreeCAD is still busy succeeding.
    assert mcp_server.BRIDGE_CLIENT_TIMEOUT_SECONDS >= GUI_REQUEST_TIMEOUT_SECONDS


def test_mcp_uses_the_shared_runtime_registry() -> None:
    assert tool_registry is get_tool_registry()
    assert [tool["name"] for tool in available_cad_tools()] == [
        spec.name for spec in tool_registry.list_specs()
    ]


def test_mcp_exposes_compact_discovery_and_on_demand_contracts() -> None:
    search = search_cad_capabilities("crie um cilindro", limit=4)
    names = [item["name"] for item in search["capabilities"]]

    assert "cad.create_cylinder" in names
    details = describe_cad_capabilities(["cad.create_cylinder"])
    assert details["capabilities"][0]["name"] == "cad.create_cylinder"
    assert "input_schema" in details["capabilities"][0]

    published = {
        tool.name: tool for tool in asyncio.run(mcp_server.mcp.list_tools())
    }
    assert published["search_cad_capabilities"].outputSchema["properties"]
    assert published["describe_cad_capabilities"].outputSchema["properties"]

    _, structured = asyncio.run(
        mcp_server.mcp.call_tool(
            "search_cad_capabilities",
            {"query": "crie um cilindro", "limit": 4},
        )
    )
    assert structured is not None
    assert structured["capabilities"][0]["name"] == "cad.create_cylinder"


def test_read_entrypoint_directs_modifications_to_confirmed_bridge_tool() -> None:
    with pytest.raises(PermissionError, match="request_cad_tool"):
        execute_cad_read_tool("cad.undo", {})


def test_generic_mcp_tool_returns_pending_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = []

    def send(request):
        captured.append(request)
        return BridgeResponse(
            request_id=request.request_id,
            status=BridgeResponseStatus.PENDING_CONFIRMATION,
        )

    monkeypatch.setattr(mcp_server, "_send_bridge_request", send)
    result = request_cad_tool(
        "cad.create_box",
        {"length": 10, "width": 20, "height": 30},
    )

    assert result["status"] == "pending_confirmation"
    assert captured[0].tool_name == "cad.create_box"
    assert captured[0].source == "mcp"


def test_read_entrypoint_returns_gui_bridge_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def send(request):
        return BridgeResponse(
            request_id=request.request_id,
            status=BridgeResponseStatus.COMPLETED,
            result={"active": False, "objects": []},
        )

    monkeypatch.setattr(mcp_server, "_send_bridge_request", send)

    assert execute_cad_read_tool("cad.get_document_summary", {}) == {
        "active": False,
        "objects": [],
    }


def test_read_entrypoint_preserves_structured_bridge_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def send(request):
        return BridgeResponse(
            request_id=request.request_id,
            status=BridgeResponseStatus.FAILED,
            error=BridgeError(
                code=BridgeErrorCode.EXECUTION_ERROR,
                message="The CAD read failed safely.",
                safe_state_restored=True,
            ),
        )

    monkeypatch.setattr(mcp_server, "_send_bridge_request", send)
    result = execute_cad_read_tool("cad.get_document_summary", {})

    assert result["status"] == "failed"
    assert result["error"]["code"] == "execution_error"
    assert result["error"]["safe_state_restored"] is True


def test_missing_gui_session_returns_structured_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MissingSessionStore:
        def load(self):
            raise BridgeSessionError("No session.")

    monkeypatch.setattr(
        mcp_server,
        "default_session_store",
        lambda: MissingSessionStore(),
    )
    result = request_cad_tool(
        "cad.create_box",
        {"length": 10, "width": 20, "height": 30},
    )

    assert result["status"] == "failed"
    assert result["error"]["code"] == "gui_unavailable"
    assert result["error"]["retryable"] is True
    assert result["error"]["safe_state_restored"] is True


def test_ambiguous_transport_failure_does_not_claim_safe_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SessionStore:
        def load(self):
            return type("Session", (), {"endpoint": object()})()

    class FailingClient:
        def __init__(self, endpoint, *, timeout):
            del endpoint, timeout

        def request(self, request):
            del request
            raise BridgeTransportError("Disconnected mid-frame.")

    monkeypatch.setattr(mcp_server, "default_session_store", lambda: SessionStore())
    monkeypatch.setattr(mcp_server, "TcpBridgeClient", FailingClient)
    result = request_cad_tool(
        "cad.create_box",
        {"length": 10, "width": 20, "height": 30},
    )

    assert result["error"]["code"] == "transport_unavailable"
    assert result["error"]["retryable"] is True
    assert result["error"]["safe_state_restored"] is None
    assert result["error"]["suggested_actions"][0]["action"] == "refresh_context"

    read_result = request_cad_tool("cad.get_document_summary", {})
    assert read_result["error"]["safe_state_restored"] is True


def test_methodology_prompt_covers_the_professional_workflow() -> None:
    from aicad.mcp_server import PART_DESIGN_METHODOLOGY

    text = PART_DESIGN_METHODOLOGY
    for stage_tool in (
        "cad.create_parameter_set",
        "cad.create_body",
        "cad.get_sketch_status",
        "cad.bind_sketch_datum",
        "cad.add_hole",
        "cad.resolve_body_reference",
        "cad.add_fillet",
        "cad.inspect_cad_model",
    ):
        assert stage_tool in text, stage_tool
    assert "cad.pad_sketch" in text  # warns against the legacy static path

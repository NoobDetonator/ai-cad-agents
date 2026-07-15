import pytest

from aicad import mcp_server
from aicad.bridge.dispatcher import GUI_REQUEST_TIMEOUT_SECONDS
from aicad.bridge.protocol import BridgeResponse, BridgeResponseStatus
from aicad.mcp_server import (
    available_cad_tools,
    execute_cad_read_tool,
    request_cad_tool,
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

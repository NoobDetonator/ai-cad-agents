from __future__ import annotations

from dataclasses import asdict
from uuid import UUID, uuid4

from mcp.server.fastmcp import FastMCP

from aicad.bridge.protocol import (
    BridgePlanCancelRequest,
    BridgePlanStatusRequest,
    BridgePlanSubmitRequest,
    BridgeRequest,
    BridgeResponse,
    BridgeResponseStatus,
    BridgeTransportRequest,
)
from aicad.bridge.session import BridgeSessionError, default_session_store
from aicad.bridge.transport import BridgeTransportError, TcpBridgeClient
from aicad.core.tool_registry import ToolRisk
from aicad.core.context import DocumentStateToken
from aicad.orchestration.models import OrchestrationPlan, PlannedToolCall
from aicad.orchestration.plan_service import CompositeValidatedPlan
from aicad.runtime import get_tool_registry


mcp = FastMCP("AI CAD Workbench")
tool_registry = get_tool_registry()


@mcp.tool()
def health() -> dict[str, str]:
    """Check whether the AI CAD MCP process is available."""
    return {"status": "ok", "phase": "mcp-gui-bridge"}


@mcp.tool()
def available_cad_tools() -> list[dict[str, object]]:
    """List the deterministic CAD tools from the shared runtime registry."""
    return [asdict(spec) for spec in tool_registry.list_specs()]


def _build_bridge_request(
    name: str,
    arguments: dict[str, object],
    request_id: str | None = None,
) -> BridgeRequest:
    checked_arguments = tool_registry.validate_arguments(name, arguments)
    identifier = UUID(request_id) if request_id is not None else uuid4()
    return BridgeRequest(
        request_id=identifier,
        tool_name=name,
        arguments=checked_arguments,
        source="mcp",
    )


def _send_bridge_request(request: BridgeTransportRequest) -> BridgeResponse:
    try:
        session = default_session_store().load()
        return TcpBridgeClient(session.endpoint).request(request)
    except (BridgeSessionError, BridgeTransportError) as exc:
        raise RuntimeError(
            "The FreeCAD GUI bridge is unavailable or did not respond."
        ) from exc


@mcp.tool()
def request_cad_tool(
    name: str,
    arguments: dict[str, object],
    request_id: str | None = None,
) -> dict[str, object]:
    """Request any registered CAD tool through the authenticated GUI bridge."""

    request = _build_bridge_request(name, arguments, request_id)
    return _send_bridge_request(request).model_dump(mode="json")


@mcp.tool()
def execute_cad_read_tool(name: str, arguments: dict[str, object]) -> object:
    """Execute a read-only CAD tool through the active FreeCAD GUI bridge."""
    spec = tool_registry.get_spec(name)
    if spec.risk is not ToolRisk.READ:
        raise PermissionError(
            "Use request_cad_tool for modifications that require GUI confirmation."
        )
    request = _build_bridge_request(name, arguments)
    response = _send_bridge_request(request)
    if response.status is BridgeResponseStatus.COMPLETED:
        return response.result
    message = (
        response.error.message
        if response.error is not None
        else "The CAD read did not complete."
    )
    raise RuntimeError(message)


@mcp.tool()
def submit_cad_plan(
    intention: str,
    steps: list[str],
    calls: list[dict[str, object]],
    assumptions: list[str] | None = None,
    plan_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, object]:
    """Freeze and submit a 2-8 step mutation plan for one visual approval."""

    if not 2 <= len(calls) <= 8:
        raise ValueError("A CAD plan requires between two and eight calls.")
    planned_calls: list[PlannedToolCall] = []
    for index, raw_call in enumerate(calls, start=1):
        if set(raw_call) - {"call_id", "name", "arguments"}:
            raise ValueError("A CAD plan call contains unsupported fields.")
        name = raw_call.get("name")
        arguments = raw_call.get("arguments", {})
        if not isinstance(name, str) or not isinstance(arguments, dict):
            raise ValueError("Each CAD plan call requires a name and arguments.")
        spec = tool_registry.get_spec(name)
        if spec.risk is not ToolRisk.MODIFY or name == "cad.undo":
            raise ValueError("Every CAD plan call must be a reversible mutation.")
        checked = tool_registry.validate_arguments(name, arguments)
        call_id = raw_call.get("call_id", f"mcp-step-{index}")
        planned_calls.append(
            PlannedToolCall(
                call_id=call_id,
                name=name,
                arguments=checked,
                risk=spec.risk,
                requires_confirmation=True,
            )
        )

    context_request = _build_bridge_request(
        "cad.get_context_snapshot",
        {"detail_level": "work", "max_objects": 25, "cursor": 0},
    )
    context_response = _send_bridge_request(context_request)
    if context_response.status is not BridgeResponseStatus.COMPLETED:
        raise RuntimeError("The active CAD baseline could not be read safely.")
    if not isinstance(context_response.result, dict):
        raise RuntimeError("The active CAD baseline response is invalid.")
    base_state = DocumentStateToken.model_validate(
        context_response.result["state_token"]
    )
    proposal = OrchestrationPlan(
        intention=intention,
        assumptions=tuple(assumptions or ()),
        steps=tuple(steps),
        message="Composite plan submitted through MCP.",
        tool_calls=tuple(planned_calls),
    )
    frozen = CompositeValidatedPlan.build(
        proposal,
        base_state,
        tool_registry,
        plan_id=UUID(plan_id) if plan_id is not None else None,
    )
    request = BridgePlanSubmitRequest(
        request_id=UUID(request_id) if request_id is not None else uuid4(),
        plan=frozen,
        source="mcp",
    )
    return _send_bridge_request(request).model_dump(mode="json")


@mcp.tool()
def get_cad_plan_status(
    plan_id: str,
    request_id: str | None = None,
) -> dict[str, object]:
    """Poll the GUI-owned status of a submitted composite CAD plan."""

    request = BridgePlanStatusRequest(
        request_id=UUID(request_id) if request_id is not None else uuid4(),
        plan_id=UUID(plan_id),
        source="mcp",
    )
    return _send_bridge_request(request).model_dump(mode="json")


@mcp.tool()
def cancel_cad_plan(
    plan_id: str,
    request_id: str | None = None,
) -> dict[str, object]:
    """Cancel a submitted plan before or between its safe transaction steps."""

    request = BridgePlanCancelRequest(
        request_id=UUID(request_id) if request_id is not None else uuid4(),
        plan_id=UUID(plan_id),
        source="mcp",
    )
    return _send_bridge_request(request).model_dump(mode="json")


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

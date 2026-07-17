from __future__ import annotations

from dataclasses import asdict
import json
from time import perf_counter
from uuid import UUID, uuid4

from mcp.server.fastmcp import FastMCP

from aicad.bridge.protocol import (
    BridgeError,
    BridgeErrorCode,
    BridgePlanCancelRequest,
    BridgePlanStatusRequest,
    BridgePlanSubmitRequest,
    BridgeRequest,
    BridgeResponse,
    BridgeResponseStatus,
    BridgeTransportRequest,
)
from aicad.bridge.dispatcher import GUI_REQUEST_TIMEOUT_SECONDS
from aicad.bridge.session import BridgeSessionError, default_session_store
from aicad.bridge.transport import BridgeTransportError, TcpBridgeClient
from aicad.core.capabilities import (
    CapabilityCatalog,
    CapabilityDescriptions,
    CapabilitySearchResult,
)
from aicad.core.inspection import CadModelInspection, inspect_model
from aicad.core.tool_registry import ToolRisk
from aicad.core.context import DocumentStateToken
from aicad.core.tool_results import (
    ToolErrorCategory,
    ToolRecoveryAction,
    ToolRecoveryActionType,
)
from aicad.core.visual_cache import read_capture
from aicad.mcp_telemetry import (
    McpPerformanceSnapshot,
    mcp_telemetry,
    serialized_size,
)
from aicad.orchestration.models import OrchestrationPlan, PlannedToolCall
from aicad.orchestration.plan_service import CompositeValidatedPlan
from aicad.orchestration.recipes import default_recipe_catalog
from aicad.runtime import get_tool_registry


mcp = FastMCP("TALOS FreeCAD MCP")
tool_registry = get_tool_registry()
capability_catalog = CapabilityCatalog(tool_registry)
recipe_catalog = default_recipe_catalog()

# The GUI dispatcher works a request for GUI_REQUEST_TIMEOUT_SECONDS before it
# expires it, and real CAD work (a 54-tooth ring, an interference analysis)
# routinely runs for a minute. The transport default of 5 s would hang up long
# before that and report the bridge as unavailable while FreeCAD is still busy
# succeeding, so wait at least as long as the far side is willing to work.
BRIDGE_CLIENT_TIMEOUT_SECONDS = GUI_REQUEST_TIMEOUT_SECONDS + 15.0


@mcp.tool()
@mcp_telemetry.track("health")
def health() -> dict[str, str]:
    """Check whether the TALOS MCP process is available."""
    return {"status": "ok", "phase": "mcp-gui-bridge"}


@mcp.tool()
@mcp_telemetry.track("available_cad_tools")
def available_cad_tools() -> list[dict[str, object]]:
    """Compatibility endpoint for the complete CAD tool catalog.

    Prefer search_cad_capabilities and describe_cad_capabilities so normal turns
    load only relevant contracts. This full result remains available for older
    clients, diagnostics and complete catalog audits.
    """
    return [asdict(spec) for spec in tool_registry.list_specs()]


@mcp.tool()
@mcp_telemetry.track("search_cad_capabilities")
def search_cad_capabilities(
    query: str = "",
    families: list[str] | None = None,
    risks: list[str] | None = None,
    limit: int = 8,
    cursor: int = 0,
) -> CapabilitySearchResult:
    """Search compact CAD capability cards without loading every schema.

    Use this instead of available_cad_tools for normal discovery. Results are
    ranked locally, safety-filtered, optionally restricted by family or risk,
    and paginated. An empty query lists the catalog in stable order. Pass the
    selected names to describe_cad_capabilities before planning a call.
    """

    return capability_catalog.search(
        query,
        families=families,
        risks=risks,
        limit=limit,
        cursor=cursor,
    )


@mcp.tool()
@mcp_telemetry.track("describe_cad_capabilities")
def describe_cad_capabilities(names: list[str]) -> CapabilityDescriptions:
    """Load complete contracts for up to 16 selected CAD capabilities.

    Names should come from search_cad_capabilities. The result preserves input
    order and includes descriptions, input and output schemas, risk, aliases,
    tags and examples. The complete catalog remains available only as a
    compatibility and diagnostic endpoint.
    """

    return capability_catalog.describe(names)


@mcp.tool()
@mcp_telemetry.track("available_cad_recipes")
def available_cad_recipes() -> list[dict[str, object]]:
    """List trusted multi-step CAD recipes compiled into registered tools."""

    return list(recipe_catalog.list_recipes())


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
    started = perf_counter()
    request_payload = request.model_dump(mode="json")
    try:
        session = default_session_store().load()
        response = TcpBridgeClient(
            session.endpoint,
            timeout=BRIDGE_CLIENT_TIMEOUT_SECONDS,
        ).request(request)
    except BridgeSessionError:
        response = BridgeResponse(
            request_id=request.request_id,
            status=BridgeResponseStatus.FAILED,
            error=BridgeError(
                code=BridgeErrorCode.GUI_UNAVAILABLE,
                message=(
                    "No active FreeCAD GUI bridge session is available."
                ),
            ),
        )
    except BridgeTransportError:
        safe_state_restored = (
            True
            if isinstance(request, BridgeRequest)
            and tool_registry.get_spec(request.tool_name).risk is ToolRisk.READ
            else None
        )
        response = BridgeResponse(
            request_id=request.request_id,
            status=BridgeResponseStatus.FAILED,
            error=BridgeError(
                code=BridgeErrorCode.TRANSPORT_UNAVAILABLE,
                message=(
                    "The FreeCAD GUI bridge disconnected or did not respond."
                ),
                category=ToolErrorCategory.TRANSPORT,
                retryable=True,
                safe_state_restored=safe_state_restored,
                suggested_actions=(
                    ToolRecoveryAction(
                        action=ToolRecoveryActionType.REFRESH_CONTEXT,
                        description=(
                            "Reconnect and read the current document context before "
                            "deciding whether to retry."
                        ),
                    ),
                ),
            ),
        )

    finished = perf_counter()
    operation = (
        request.tool_name
        if isinstance(request, BridgeRequest)
        else request.operation.value
    )
    timing = (
        response.timing.model_dump(mode="json")
        if response.timing is not None
        else None
    )
    mcp_telemetry.record_bridge(
        request_id=str(request.request_id),
        operation=operation,
        status=response.status.value,
        duration_ms=max(0.0, finished - started) * 1000,
        request_bytes=serialized_size(request_payload),
        response_bytes=serialized_size(response.model_dump(mode="json")),
        timing=timing,
    )
    return response


def _workflow_status(response: BridgeResponse) -> str:
    if isinstance(response.result, dict):
        status = response.result.get("status")
        if isinstance(status, str) and status:
            return status
    return response.status.value

@mcp.tool()
@mcp_telemetry.track("request_cad_tool")
def request_cad_tool(
    name: str,
    arguments: dict[str, object],
    request_id: str | None = None,
) -> dict[str, object]:
    """Request any registered CAD tool through the authenticated GUI bridge.

    Mutations and exports first return status "pending_confirmation". The panel
    automatically approves mutations while its visible option is enabled, but
    exports and manual-mode sessions wait for the user. Poll by repeating this
    call with the SAME request_id until the status is terminal (completed,
    rejected, failed or expired).
    """

    request = _build_bridge_request(name, arguments, request_id)
    response = _send_bridge_request(request)
    mcp_telemetry.observe_confirmation(
        f"request:{request.request_id}",
        _workflow_status(response),
    )
    return response.model_dump(mode="json")


@mcp.tool()
@mcp_telemetry.track("execute_cad_read_tool")
def execute_cad_read_tool(name: str, arguments: dict[str, object]) -> object:
    """Execute a risk "read" CAD tool immediately, without confirmation.

    Requires the FreeCAD GUI open with the TALOS MCP workbench active. Start
    with cad.get_context_snapshot to learn the document state, then read
    details and measures before proposing mutations.
    """
    spec = tool_registry.get_spec(name)
    if spec.risk is not ToolRisk.READ:
        raise PermissionError(
            "Use request_cad_tool for modifications that require GUI confirmation."
        )
    request = _build_bridge_request(name, arguments)
    response = _send_bridge_request(request)
    if response.status is BridgeResponseStatus.COMPLETED:
        return response.result
    return response.model_dump(mode="json")


@mcp.tool()
@mcp_telemetry.track("submit_cad_plan")
def submit_cad_plan(
    intention: str,
    steps: list[str],
    calls: list[dict[str, object]],
    assumptions: list[str] | None = None,
    plan_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, object]:
    """Freeze and submit a 2-8 step mutation plan for one visual approval.

    Prefer this over sequential request_cad_tool calls: the user approves
    the whole plan once in the FreeCAD panel, each step is transactional,
    and a mid-plan failure triggers a verified compensating rollback. Track
    progress with get_cad_plan_status using the returned plan_id.
    """

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
        if spec.risk is not ToolRisk.MODIFY or not spec.compensatable:
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
        return context_response.model_dump(mode="json")
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
    response = _send_bridge_request(request)
    mcp_telemetry.observe_confirmation(
        f"plan:{frozen.plan_id}",
        _workflow_status(response),
    )
    return response.model_dump(mode="json")


@mcp.tool()
@mcp_telemetry.track("get_cad_plan_status")
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
    response = _send_bridge_request(request)
    mcp_telemetry.observe_confirmation(
        f"plan:{request.plan_id}",
        _workflow_status(response),
    )
    return response.model_dump(mode="json")


@mcp.tool()
@mcp_telemetry.track("cancel_cad_plan")
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
    response = _send_bridge_request(request)
    mcp_telemetry.observe_confirmation(
        f"plan:{request.plan_id}",
        _workflow_status(response),
    )
    return response.model_dump(mode="json")


@mcp.tool()
@mcp_telemetry.track("submit_cad_recipe")
def submit_cad_recipe(
    recipe_id: str,
    parameters: dict[str, object],
    plan_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, object]:
    """Compile a trusted recipe and submit its immutable plan for approval."""

    context_request = _build_bridge_request(
        "cad.get_context_snapshot",
        {"detail_level": "work", "max_objects": 25, "cursor": 0},
    )
    context_response = _send_bridge_request(context_request)
    if context_response.status is not BridgeResponseStatus.COMPLETED:
        return context_response.model_dump(mode="json")
    if not isinstance(context_response.result, dict):
        raise RuntimeError("The active CAD baseline response is invalid.")
    base_state = DocumentStateToken.model_validate(
        context_response.result["state_token"]
    )
    proposal = recipe_catalog.create_plan(recipe_id, parameters, tool_registry)
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
    response = _send_bridge_request(request)
    mcp_telemetry.observe_confirmation(
        f"plan:{frozen.plan_id}",
        _workflow_status(response),
    )
    return response.model_dump(mode="json")


@mcp.tool()
@mcp_telemetry.track("inspect_cad_model")
def inspect_cad_model(
    objects: list[str] | None = None,
    max_objects: int = 3,
    include_details: bool = False,
    include_dependencies: bool = False,
    include_visuals: bool = False,
    views: list[str] | None = None,
) -> CadModelInspection:
    """Inspect context, validity and selected model objects in one bounded call.

    Objects default to the current selection, then recent objects, then the
    first objects in the context page. Measurements are included by default;
    detailed edge contracts, dependencies and visual resources are opt-in.
    A final state token reports whether the document stayed stable throughout
    the multi-read inspection.
    """

    def read(name: str, arguments: dict[str, object]) -> tuple[bool, object]:
        response = _send_bridge_request(_build_bridge_request(name, arguments))
        if response.status is BridgeResponseStatus.COMPLETED:
            return True, response.result
        return False, response.model_dump(mode="json")

    return inspect_model(
        read,
        objects=objects,
        max_objects=max_objects,
        include_details=include_details,
        include_dependencies=include_dependencies,
        include_visuals=include_visuals,
        views=views,
    )


@mcp.tool()
def get_mcp_performance_snapshot() -> McpPerformanceSnapshot:
    """Read bounded process-local performance metrics without request content.

    Token counts are UTF-8 byte estimates, not client tokenizer measurements.
    GUI queue, approval and execution timings are reported separately whenever
    the active FreeCAD bridge supports the optional timing contract.
    """

    return mcp_telemetry.snapshot()


@mcp.resource(
    "aicad://recipes",
    name="cad_recipes",
    description="Trusted TALOS recipe catalog and parameter schemas.",
    mime_type="application/json",
)
def cad_recipe_resource() -> str:
    return json.dumps(
        list(recipe_catalog.list_recipes()),
        ensure_ascii=False,
        separators=(",", ":"),
    )


@mcp.resource(
    "aicad://view/{capture_id}",
    name="cad_visual_context",
    description="A bounded PNG captured on demand from the active FreeCAD view.",
    mime_type="image/png",
)
def cad_visual_context_resource(capture_id: str) -> bytes:
    return read_capture(capture_id)


PART_DESIGN_METHODOLOGY = """\
Metodologia Part Design do TALOS — modele como um profissional:

1. PARÂMETROS PRIMEIRO: crie um conjunto com cad.create_parameter_set e
   declare as dimensões que governam a peça com cad.set_master_parameter
   (ex.: wall_thickness, plate_width). Nomes minúsculos com underscore.
2. BODY: toda peça vive em um PartDesign::Body (cad.create_body). Nunca use
   os sólidos estáticos legados (cad.pad_sketch) para trabalho novo.
3. SKETCH MESTRE: cad.create_body_sketch no plano de origem certo; desenhe
   com as ferramentas add_sketch_*; cote com
   cad.add_sketch_dimensional_constraint; nomeie as cotas importantes com
   cad.rename_sketch_constraint e vincule-as aos parâmetros com
   cad.bind_sketch_datum.
4. TOTALMENTE RESTRITO: antes de qualquer feature, confirme com
   cad.get_sketch_status que degrees_of_freedom chegou a 0. Um sketch com
   liberdade sobrando produz modelos que quebram ao editar.
5. FEATURE BASE: um único pad ou revolução define o volume principal
   (cad.add_pad, cad.add_revolution). Vincule comprimentos a parâmetros com
   cad.bind_feature_parameter.
6. FEATURES SECUNDÁRIAS: pockets, furos (cad.add_hole com counterbore ou
   countersink) e novos sketches sobre faces resolvidas semanticamente
   (cad.resolve_body_reference antes, cad.create_face_sketch depois).
7. PADRÕES: repita com cad.add_linear_pattern, cad.add_polar_pattern ou
   cad.add_mirrored_pattern em vez de duplicar features.
8. DRESSUPS POR ÚLTIMO: cad.add_fillet e cad.add_chamfer sempre no fim da
   árvore; raio bem menor que a menor dimensão vizinha.
9. VERIFIQUE CADA FASE: cad.inspect_cad_model para medidas e imagens;
   corrija mudando cotas (cad.set_sketch_datum, cad.edit_feature), nunca
   recriando a árvore.
10. ENTREGA: o teste final de qualidade é mudar um parâmetro mestre e o
    modelo inteiro recalcular válido. Só então salve ou exporte.
"""


@mcp.prompt(name="part_design_methodology")
def part_design_methodology_prompt() -> str:
    """Professional parametric Part Design workflow for external agents."""

    return PART_DESIGN_METHODOLOGY


@mcp.resource(
    "aicad://guides/partdesign",
    name="part_design_guide",
    description="Metodologia profissional de Part Design paramétrico do TALOS.",
    mime_type="text/markdown",
)
def part_design_guide_resource() -> str:
    return PART_DESIGN_METHODOLOGY


def _recipe_prompt(recipe_id: str) -> str:
    recipe = recipe_catalog.get(recipe_id)
    return (
        f"Use a receita segura '{recipe.recipe_id}' ({recipe.title}). "
        "Colete somente os parâmetros ausentes, chame submit_cad_recipe e "
        "informe que a execução aguardará uma única confirmação no FreeCAD."
    )


@mcp.prompt(name="model_mounting_plate")
def model_mounting_plate_prompt() -> str:
    """Guide an agent through the trusted mounting plate recipe."""

    return _recipe_prompt("mounting_plate")


@mcp.prompt(name="model_flange")
def model_flange_prompt() -> str:
    """Guide an agent through the trusted flange recipe."""

    return _recipe_prompt("flange")


@mcp.prompt(name="model_rectangular_pad")
def model_rectangular_pad_prompt() -> str:
    """Guide an agent through the trusted sketch and pad recipe."""

    return _recipe_prompt("rectangular_pad")


@mcp.prompt(name="model_stepped_shaft")
def model_stepped_shaft_prompt() -> str:
    """Guide an agent through the trusted stepped shaft recipe."""

    return _recipe_prompt("stepped_shaft")


@mcp.prompt(name="model_flat_pulley")
def model_flat_pulley_prompt() -> str:
    """Guide an agent through the trusted flat pulley recipe."""

    return _recipe_prompt("flat_pulley")


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from pydantic import ValidationError

from aicad import mcp_server
from aicad.bridge.protocol import (
    BridgePlanSubmitRequest,
    BridgeRequest,
    BridgeResponse,
    BridgeResponseStatus,
)
from aicad.core.context import DocumentStateToken
from aicad.core.tool_registry import ToolRisk, build_default_registry
from aicad.orchestration.recipes import default_recipe_catalog


def test_recipe_catalog_compiles_trusted_plans() -> None:
    catalog = default_recipe_catalog()
    registry = build_default_registry()
    records = catalog.list_recipes()

    assert {item["recipe_id"] for item in records} == {
        "mounting_plate",
        "flange",
        "rectangular_pad",
        "stepped_shaft",
        "flat_pulley",
    }
    plan = catalog.create_plan(
        "mounting_plate",
        {
            "length": 100,
            "width": 60,
            "thickness": 8,
            "hole_diameter": 6,
            "edge_offset": 10,
        },
        registry,
    )
    assert [call.name for call in plan.tool_calls] == [
        "cad.create_plate",
        "cad.create_rectangular_hole_pattern",
    ]
    assert all(call.risk is ToolRisk.MODIFY for call in plan.tool_calls)
    assert plan.tool_calls[1].arguments["object"] == "MountingPlateBlank"


def test_stepped_shaft_recipe_stacks_and_fuses_the_steps() -> None:
    plan = default_recipe_catalog().create_plan(
        "stepped_shaft",
        {
            "first_diameter": 30,
            "first_length": 40,
            "second_diameter": 20,
            "second_length": 25,
        },
        build_default_registry(),
    )

    assert [call.name for call in plan.tool_calls] == [
        "cad.create_cylinder",
        "cad.create_cylinder",
        "cad.transform_object",
        "cad.boolean_operation",
    ]
    assert plan.tool_calls[2].arguments == {
        "object": "SteppedShaftStepB",
        "z": 40,
    }
    assert plan.tool_calls[3].arguments["operation"] == "fuse"
    assert plan.tool_calls[3].arguments["name"] == "SteppedShaft"


def test_flat_pulley_recipe_builds_flanges_body_and_bore() -> None:
    plan = default_recipe_catalog().create_plan(
        "flat_pulley",
        {
            "flange_diameter": 60,
            "flange_thickness": 4,
            "body_diameter": 50,
            "body_width": 20,
            "bore_diameter": 10,
        },
        build_default_registry(),
    )

    names = [call.name for call in plan.tool_calls]
    assert len(names) == 8
    assert names[-1] == "cad.create_through_hole"
    assert plan.tool_calls[-1].arguments["object"] == "PulleyBlank"
    assert plan.tool_calls[-1].arguments["name"] == "Pulley"
    assert plan.tool_calls[4].arguments["z"] == 24


def test_flat_pulley_recipe_rejects_impossible_geometry() -> None:
    catalog = default_recipe_catalog()
    registry = build_default_registry()
    with pytest.raises(ValidationError, match="smaller than the flanges"):
        catalog.create_plan(
            "flat_pulley",
            {
                "flange_diameter": 40,
                "flange_thickness": 4,
                "body_diameter": 50,
                "body_width": 20,
                "bore_diameter": 10,
            },
            registry,
        )
    with pytest.raises(ValidationError, match="bore does not fit"):
        catalog.create_plan(
            "flat_pulley",
            {
                "flange_diameter": 60,
                "flange_thickness": 4,
                "body_diameter": 50,
                "body_width": 20,
                "bore_diameter": 55,
            },
            registry,
        )


def test_recipe_parameters_reject_impossible_geometry_before_planning() -> None:
    with pytest.raises(ValidationError, match="edge offset"):
        default_recipe_catalog().create_plan(
            "mounting_plate",
            {
                "length": 20,
                "width": 20,
                "thickness": 4,
                "hole_diameter": 6,
                "edge_offset": 12,
            },
            build_default_registry(),
        )


def test_mcp_projects_recipe_resources_and_prompts() -> None:
    resources = asyncio.run(mcp_server.mcp.list_resources())
    templates = asyncio.run(mcp_server.mcp.list_resource_templates())
    prompts = asyncio.run(mcp_server.mcp.list_prompts())

    assert any(str(item.uri) == "aicad://recipes" for item in resources)
    assert any("aicad://view/" in item.uriTemplate for item in templates)
    assert {item.name for item in prompts} >= {
        "model_mounting_plate",
        "model_flange",
        "model_rectangular_pad",
        "model_stepped_shaft",
        "model_flat_pulley",
    }


def test_submit_cad_recipe_uses_context_and_plan_bridge(monkeypatch) -> None:
    sent = []
    token = DocumentStateToken(
        session_id=uuid4(),
        document_id="Document",
        revision=1,
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
        return BridgeResponse(
            request_id=request.request_id,
            status=BridgeResponseStatus.COMPLETED,
            result={"plan_id": str(request.plan.plan_id), "status": "awaiting_approval"},
        )

    monkeypatch.setattr(mcp_server, "_send_bridge_request", send)
    result = mcp_server.submit_cad_recipe(
        "rectangular_pad",
        {"width": 40, "height": 20, "length": 12},
    )

    assert result["result"]["status"] == "awaiting_approval"
    assert isinstance(sent[1], BridgePlanSubmitRequest)
    assert [call.name for call in sent[1].plan.calls] == [
        "cad.create_rectangular_sketch",
        "cad.pad_sketch",
    ]

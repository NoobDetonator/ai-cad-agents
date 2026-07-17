from __future__ import annotations

from uuid import uuid4

import pytest

from aicad import mcp_server
from aicad.bridge.dispatcher import BridgeDispatcher
from aicad.core.tool_registry import (
    ToolInputError,
    ToolRegistry,
    ToolRisk,
    ToolSpec,
    build_default_registry,
)
from aicad.core.transactions import (
    CadTransactionOutcome,
    mark_transaction,
    transaction_trace,
)


def test_every_published_tool_has_an_output_contract() -> None:
    registry = build_default_registry()

    assert all(spec.output_schema is not None for spec in registry.list_specs())


def test_registry_validates_nested_draft_2020_12_schemas() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="test.nested",
            description="Exercise nested validation.",
            risk=ToolRisk.READ,
            input_schema={
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "pattern": "^[A-Z][A-Za-z0-9]*$",
                                },
                                "weight": {"type": "number", "exclusiveMinimum": 0},
                            },
                            "required": ["name", "weight"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["items"],
                "additionalProperties": False,
            },
            output_schema={"type": "object"},
        )
    )

    assert registry.validate_arguments(
        "test.nested", {"items": [{"name": "Gear1", "weight": 2.5}]}
    )["items"][0]["name"] == "Gear1"
    with pytest.raises(ToolInputError):
        registry.validate_arguments(
            "test.nested", {"items": [{"name": "bad name", "weight": 2.5}]}
        )
    with pytest.raises(ToolInputError):
        registry.validate_arguments(
            "test.nested", {"items": [{"name": "Gear1", "weight": 0}]}
        )
    with pytest.raises(ToolInputError):
        registry.validate_arguments(
            "test.nested",
            {"items": [{"name": "Gear1", "weight": 2.5, "python": "pass"}]},
        )


def test_enum_errors_echo_the_allowed_values() -> None:
    registry = build_default_registry()

    with pytest.raises(
        ToolInputError,
        match=r"must be one of the allowed values: minimal, work",
    ):
        registry.validate_arguments(
            "cad.get_context_snapshot", {"detail_level": "summary"}
        )


def test_constraint_contracts_accept_the_sketch_origin_anchor() -> None:
    registry = build_default_registry()

    anchored = registry.validate_arguments(
        "cad.add_sketch_geometric_constraint",
        {
            "sketch": "Base",
            "constraint_type": "coincident",
            "first_geometry": 0,
            "first_position": "start",
            "second_geometry": -1,
            "second_position": "start",
        },
    )
    assert anchored["second_geometry"] == -1

    measured = registry.validate_arguments(
        "cad.add_sketch_dimensional_constraint",
        {
            "sketch": "Base",
            "constraint_type": "distance_x",
            "geometry": -1,
            "position": "start",
            "second_geometry": 2,
            "second_position": "center",
            "value": 10,
        },
    )
    assert measured["geometry"] == -1

    with pytest.raises(ToolInputError, match="at least -1"):
        registry.validate_arguments(
            "cad.add_sketch_geometric_constraint",
            {
                "sketch": "Base",
                "constraint_type": "coincident",
                "first_geometry": -2,
                "first_position": "start",
                "second_geometry": 0,
                "second_position": "start",
            },
        )


def test_registry_rejects_invalid_published_schemas_at_registration() -> None:
    registry = ToolRegistry()

    with pytest.raises(ValueError, match="Invalid JSON Schema"):
        registry.register(
            ToolSpec(
                name="test.invalid_schema",
                description="Invalid schema.",
                risk=ToolRisk.READ,
                input_schema={"type": "definitely-not-a-json-schema-type"},
            )
        )


def test_only_compensatable_mutations_can_enter_composite_mcp_plans(
    monkeypatch,
) -> None:
    registry = build_default_registry()
    assert registry.get_spec("cad.create_box").compensatable is True
    assert registry.get_spec("cad.new_document").compensatable is False
    assert registry.get_spec("cad.set_active_document").compensatable is False
    assert registry.get_spec("cad.undo").compensatable is False

    sent: list[object] = []
    monkeypatch.setattr(mcp_server, "_send_bridge_request", sent.append)
    with pytest.raises(ValueError, match="reversible mutation"):
        mcp_server.submit_cad_plan(
            "Criar documentos.",
            ["Criar o primeiro.", "Criar o segundo."],
            [
                {"name": "cad.new_document", "arguments": {"name": "First"}},
                {"name": "cad.new_document", "arguments": {"name": "Second"}},
            ],
        )
    assert sent == []


def test_safe_state_claim_requires_transaction_evidence() -> None:
    assert BridgeDispatcher._safe_state_after_failure(ToolRisk.READ) is True

    aborted_action = uuid4()
    with transaction_trace(aborted_action, "aborted"):
        mark_transaction(CadTransactionOutcome.ABORTED)
    assert BridgeDispatcher._safe_state_after_failure(
        ToolRisk.MODIFY, aborted_action
    ) is True

    unknown_action = uuid4()
    with transaction_trace(unknown_action, "unknown"):
        pass
    assert BridgeDispatcher._safe_state_after_failure(
        ToolRisk.MODIFY, unknown_action
    ) is None

    committed_action = uuid4()
    with transaction_trace(committed_action, "committed"):
        mark_transaction(CadTransactionOutcome.COMMITTED)
    assert BridgeDispatcher._safe_state_after_failure(
        ToolRisk.MODIFY, committed_action
    ) is False
    assert (
        BridgeDispatcher._safe_state_after_failure(ToolRisk.MODIFY, uuid4())
        is None
    )
    assert BridgeDispatcher._safe_state_after_failure(ToolRisk.MODIFY) is None

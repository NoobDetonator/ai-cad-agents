from __future__ import annotations

from typing import Any

import pytest

from aicad.core.tool_registry import build_default_registry
from aicad.core.tool_results import ToolResultEnvelope, ToolResultStatus
from aicad.orchestration import (
    AgentSessionMemory,
    AgentStage,
    AgentTurnCancellation,
    AgentTurnController,
    AgentTurnLimits,
    AgentTurnStatus,
    AiOrchestrator,
    OrchestrationLimitError,
    OrchestrationLimits,
    ProviderRequest,
)


def response(*, calls: list[dict[str, Any]] | None = None, message: str = "Pronto"):
    return {
        "intention": "Ler o documento com segurança.",
        "assumptions": [],
        "plan": ["Consultar somente ferramentas permitidas."],
        "message": message,
        "tool_calls": calls or [],
    }


class SequenceProvider:
    def __init__(self, *responses: object) -> None:
        self.responses = list(responses)
        self.requests: list[ProviderRequest] = []

    def create_response(self, request: ProviderRequest) -> object:
        self.requests.append(request)
        return self.responses.pop(0)


def controller_for(provider: SequenceProvider, **kwargs: Any):
    registry = build_default_registry()
    orchestrator = AiOrchestrator(
        registry,
        provider,
        limits=OrchestrationLimits(max_tool_calls=2),
    )
    return registry, AgentTurnController(registry, orchestrator, **kwargs)


def test_read_loop_returns_result_to_provider_and_finishes() -> None:
    provider = SequenceProvider(
        response(
            calls=[
                {
                    "call_id": "read-summary-1",
                    "name": "cad.get_document_summary",
                    "arguments": {},
                }
            ]
        ),
        response(message="O documento está vazio."),
    )
    registry, controller = controller_for(provider)
    registry.bind(
        "cad.get_document_summary",
        lambda: {"active": False, "objects": []},
    )
    stages: list[AgentStage] = []

    result = controller.run("O que existe no documento?", progress=stages.append)

    assert result.status is AgentTurnStatus.DONE
    assert result.rounds == 2
    assert result.read_calls == 1
    assert len(provider.requests) == 2
    assert provider.requests[0].history == ()
    history = provider.requests[1].history
    assert [item.role for item in history] == ["assistant", "tool"]
    assert history[1].call_id == "read-summary-1"
    assert history[1].status == "completed"
    assert history[1].result == {"active": False, "objects": []}
    assert AgentStage.EXECUTE_READS in stages
    assert stages[-1] is AgentStage.DONE


def test_read_loop_never_executes_a_mutation() -> None:
    provider = SequenceProvider(
        response(
            calls=[
                {
                    "call_id": "box-1",
                    "name": "cad.create_box",
                    "arguments": {"length": 10, "width": 20, "height": 30},
                }
            ]
        )
    )
    registry, controller = controller_for(provider)
    executed: list[dict[str, Any]] = []
    registry.bind("cad.create_box", lambda **arguments: executed.append(arguments))

    result = controller.run("Crie uma caixa 10 x 20 x 30.")

    assert result.status is AgentTurnStatus.AWAITING_APPROVAL
    assert result.read_calls == 0
    assert result.final_plan is not None
    assert result.final_plan.tool_calls[0].requires_confirmation is True
    assert executed == []


def test_turn_can_return_two_mutations_without_executing_them() -> None:
    provider = SequenceProvider(
        response(
            calls=[
                {
                    "call_id": "box-1",
                    "name": "cad.create_box",
                    "arguments": {"length": 10, "width": 20, "height": 30},
                },
                {
                    "call_id": "cylinder-1",
                    "name": "cad.create_cylinder",
                    "arguments": {"diameter": 8, "height": 20},
                },
            ]
        )
    )
    registry, controller = controller_for(provider)
    executed: list[str] = []
    registry.bind("cad.create_box", lambda **arguments: executed.append("box"))
    registry.bind(
        "cad.create_cylinder",
        lambda **arguments: executed.append("cylinder"),
    )

    result = controller.run("Crie uma caixa e um cilindro.")

    assert result.status is AgentTurnStatus.AWAITING_APPROVAL
    assert result.total_tool_calls == 2
    assert result.final_plan is not None
    assert len(result.final_plan.tool_calls) == 2
    assert executed == []


def test_cancellation_stops_before_provider_or_tools() -> None:
    provider = SequenceProvider(response())
    _, controller = controller_for(provider)
    cancellation = AgentTurnCancellation()
    cancellation.cancel()

    result = controller.run("Leia o documento.", cancellation=cancellation)

    assert result.status is AgentTurnStatus.CANCELLED
    assert result.rounds == 0
    assert provider.requests == []


def test_read_failure_is_redacted_and_returned_for_replanning() -> None:
    provider = SequenceProvider(
        response(
            calls=[
                {
                    "call_id": "read-selection-1",
                    "name": "cad.get_selection",
                    "arguments": {},
                }
            ]
        ),
        response(message="Não consegui ler a seleção."),
    )
    _, controller = controller_for(
        provider,
        read_executor=lambda name, arguments: (_ for _ in ()).throw(
            RuntimeError("provider-secret-path")
        ),
    )

    result = controller.run("O que está selecionado?")

    tool_result = provider.requests[1].history[1]
    assert result.status is AgentTurnStatus.DONE
    assert tool_result.status == "failed"
    assert tool_result.error_code == "execution_failed"
    assert tool_result.result is None
    assert "provider-secret-path" not in tool_result.summary


def test_read_loop_stops_safely_when_one_selection_is_required() -> None:
    provider = SequenceProvider(
        response(
            calls=[
                {
                    "call_id": "resolve-selection-1",
                    "name": "cad.resolve_object",
                    "arguments": {},
                }
            ]
        ),
        response(message="Esta resposta não deve ser solicitada."),
    )
    _, controller = controller_for(
        provider,
        read_executor=lambda name, arguments: {
            "status": "awaiting_selection",
            "selection_count": 0,
        },
    )
    stages: list[AgentStage] = []

    result = controller.run(
        "Aplique isso ao objeto selecionado.",
        progress=stages.append,
    )

    assert result.status is AgentTurnStatus.AWAITING_SELECTION
    assert result.rounds == 1
    assert result.read_calls == 1
    assert len(provider.requests) == 1
    assert result.history[-1].result == {
        "status": "awaiting_selection",
        "selection_count": 0,
    }
    assert stages[-1] is AgentStage.AWAIT_SELECTION


def test_round_budget_prevents_an_infinite_read_loop() -> None:
    repeated = response(
        calls=[
            {
                "call_id": "read-1",
                "name": "cad.get_document_summary",
                "arguments": {},
            }
        ]
    )
    provider = SequenceProvider(repeated, repeated)
    registry, controller = controller_for(
        provider,
        limits=AgentTurnLimits(max_rounds=2),
    )
    registry.bind("cad.get_document_summary", lambda: {"active": False})

    with pytest.raises(OrchestrationLimitError, match="reused"):
        controller.run("Continue lendo para sempre.")


def test_session_memory_is_revision_bound_and_bounded() -> None:
    memory = AgentSessionMemory(max_results=2, max_bytes=2048)
    context_v1 = {"snapshot": {"state_token": {"revision": 1}}}
    memory.begin_turn(context_v1)
    memory.record(
        ToolResultEnvelope(
            tool_name="cad.get_document_summary",
            status=ToolResultStatus.COMPLETED,
            summary="Resumo lido.",
            result={"active": False},
            duration_ms=1,
        )
    )

    assert memory.as_context()["recent_read_results"]
    memory.begin_turn({"snapshot": {"state_token": {"revision": 2}}})
    assert memory.as_context() == {}

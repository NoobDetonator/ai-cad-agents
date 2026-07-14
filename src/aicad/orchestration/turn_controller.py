from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
import json
from threading import Event
from time import perf_counter
from typing import Any
from uuid import uuid4

from pydantic import JsonValue, ValidationError

from aicad.core.tool_registry import ToolRegistry, ToolRisk
from aicad.core.tool_results import (
    ToolError,
    ToolErrorCode,
    ToolResultEnvelope,
    ToolResultStatus,
)
from aicad.orchestration.metrics import AgentStage, AgentTimingEvent, TurnMetricsRecorder
from aicad.orchestration.models import (
    OrchestrationPlan,
    ProviderAssistantMessage,
    ProviderHistoryMessage,
    ProviderToolCall,
    ProviderToolResultMessage,
)
from aicad.orchestration.orchestrator import AiOrchestrator, OrchestrationLimitError


ReadExecutor = Callable[[str, Mapping[str, JsonValue]], Any]
ProgressCallback = Callable[[AgentStage], None]


class AgentTurnStatus(StrEnum):
    DONE = "done"
    AWAITING_SELECTION = "awaiting_selection"
    AWAITING_APPROVAL = "awaiting_approval"
    CANCELLED = "cancelled"


class AgentTurnCancelledError(RuntimeError):
    """Cooperative cancellation raised at a safe loop boundary."""


@dataclass(frozen=True, slots=True)
class AgentTurnLimits:
    max_rounds: int = 4
    max_total_calls: int = 8
    max_read_calls: int = 6
    max_mutation_proposals: int = 2
    max_duration_seconds: float = 45.0
    max_result_bytes: int = 64 * 1024

    def __post_init__(self) -> None:
        integer_values = (
            self.max_rounds,
            self.max_total_calls,
            self.max_read_calls,
            self.max_mutation_proposals,
            self.max_result_bytes,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 1
            for value in integer_values
        ):
            raise ValueError("Agent turn limits must be positive integers.")
        if (
            isinstance(self.max_duration_seconds, bool)
            or not isinstance(self.max_duration_seconds, (int, float))
            or self.max_duration_seconds <= 0
        ):
            raise ValueError("The agent turn duration must be positive.")


class AgentTurnCancellation:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise AgentTurnCancelledError("The agent turn was cancelled.")


class AgentSessionMemory:
    """Small revision-bound read memory that is never persisted."""

    def __init__(self, *, max_results: int = 8, max_bytes: int = 32 * 1024) -> None:
        if max_results < 1 or max_bytes < 1:
            raise ValueError("Session memory limits must be positive.")
        self._max_results = max_results
        self._max_bytes = max_bytes
        self._state_identity: str | None = None
        self._results: list[dict[str, JsonValue]] = []

    def begin_turn(self, context: Mapping[str, JsonValue]) -> None:
        snapshot = context.get("snapshot")
        token = snapshot.get("state_token") if isinstance(snapshot, Mapping) else None
        identity = self._canonical_json(token) if token is not None else None
        if identity != self._state_identity:
            self._results.clear()
            self._state_identity = identity

    def record(self, envelope: ToolResultEnvelope) -> None:
        payload = {
            "tool_name": envelope.tool_name,
            "status": envelope.status.value,
            "summary": envelope.summary,
            "result": envelope.result,
            "error_code": (
                envelope.error.code.value if envelope.error is not None else None
            ),
        }
        if len(self._canonical_json(payload).encode("utf-8")) > self._max_bytes:
            payload["result"] = None
        self._results.append(payload)
        self._results = self._results[-self._max_results :]
        while self._results and self._encoded_results_size() > self._max_bytes:
            self._results.pop(0)

    def as_context(self) -> dict[str, JsonValue]:
        if not self._results:
            return {}
        return {"recent_read_results": json.loads(self._canonical_json(self._results))}

    def _encoded_results_size(self) -> int:
        return len(self._canonical_json(self._results).encode("utf-8"))

    @staticmethod
    def _canonical_json(value: Any) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )


@dataclass(frozen=True, slots=True)
class AgentTurnResult:
    turn_id: str
    status: AgentTurnStatus
    rounds: int
    total_tool_calls: int
    read_calls: int
    final_plan: OrchestrationPlan | None
    history: tuple[ProviderHistoryMessage, ...]
    events: tuple[AgentTimingEvent, ...]


class AgentTurnController:
    """Run a bounded read loop; mutation calls are returned but never executed."""

    def __init__(
        self,
        registry: ToolRegistry,
        orchestrator: AiOrchestrator,
        *,
        read_executor: ReadExecutor | None = None,
        memory: AgentSessionMemory | None = None,
        limits: AgentTurnLimits | None = None,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self._registry = registry
        self._orchestrator = orchestrator
        self._read_executor = read_executor or self._execute_registry_read
        self._memory = memory or AgentSessionMemory()
        self._limits = limits or AgentTurnLimits()
        self._clock = clock

    def run(
        self,
        user_message: str,
        *,
        context: Mapping[str, JsonValue] | None = None,
        cancellation: AgentTurnCancellation | None = None,
        progress: ProgressCallback | None = None,
    ) -> AgentTurnResult:
        token = cancellation or AgentTurnCancellation()
        turn_id = str(uuid4())
        metrics = TurnMetricsRecorder(turn_id, clock=self._clock)
        started = self._clock()
        rounds = 0
        total_calls = 0
        read_calls = 0
        result_bytes = 0
        history: list[ProviderHistoryMessage] = []
        seen_call_ids: set[str] = set()
        final_plan: OrchestrationPlan | None = None

        try:
            checked_context = self._copy_context(context)
            self._stage(metrics, AgentStage.PREPARE_CONTEXT, progress)
            self._memory.begin_turn(checked_context)
            memory_context = self._memory.as_context()
            if memory_context:
                checked_context["session_memory"] = memory_context
            metrics.finish(details={"memory_results": len(memory_context)})

            while rounds < self._limits.max_rounds:
                self._check_budget(token, started)
                self._stage(metrics, AgentStage.SELECT_TOOLS, progress)
                metrics.finish(details={"round": rounds + 1})
                self._stage(metrics, AgentStage.ASK_MODEL, progress)
                plan = self._orchestrator.create_plan(
                    user_message,
                    context=checked_context,
                    history=history,
                )
                metrics.finish(details={"round": rounds + 1})
                rounds += 1
                final_plan = plan

                self._stage(metrics, AgentStage.VALIDATE_PLAN, progress)
                calls = plan.tool_calls
                for call in calls:
                    if call.call_id in seen_call_ids:
                        metrics.finish(details={"outcome": "duplicate_call_id"})
                        raise OrchestrationLimitError(
                            "A tool call ID was reused across agent rounds."
                        )
                    seen_call_ids.add(call.call_id)
                total_calls += len(calls)
                if total_calls > self._limits.max_total_calls:
                    metrics.finish(details={"outcome": "call_limit"})
                    raise OrchestrationLimitError(
                        "The agent turn exceeded its total tool call budget."
                    )
                mutation_calls = [
                    call for call in calls if call.risk is not ToolRisk.READ
                ]
                if len(mutation_calls) > self._limits.max_mutation_proposals:
                    metrics.finish(details={"outcome": "mutation_limit"})
                    raise OrchestrationLimitError(
                        "The agent proposed too many mutations for one turn."
                    )
                if mutation_calls and len(mutation_calls) != len(calls):
                    metrics.finish(details={"outcome": "mixed_risk_calls"})
                    raise OrchestrationLimitError(
                        "Read and mutation calls cannot share one agent round."
                    )
                metrics.finish(
                    details={
                        "calls": len(calls),
                        "mutation_calls": len(mutation_calls),
                    }
                )

                if mutation_calls:
                    self._stage(metrics, AgentStage.AWAIT_APPROVAL, progress)
                    metrics.finish(details={"outcome": "proposal_only"})
                    return AgentTurnResult(
                        turn_id,
                        AgentTurnStatus.AWAITING_APPROVAL,
                        rounds,
                        total_calls,
                        read_calls,
                        plan,
                        tuple(history),
                        metrics.events,
                    )
                if not calls:
                    self._stage(metrics, AgentStage.DONE, progress)
                    metrics.finish()
                    return AgentTurnResult(
                        turn_id,
                        AgentTurnStatus.DONE,
                        rounds,
                        total_calls,
                        read_calls,
                        plan,
                        tuple(history),
                        metrics.events,
                    )

                if read_calls + len(calls) > self._limits.max_read_calls:
                    raise OrchestrationLimitError(
                        "The agent turn exceeded its read call budget."
                    )
                history.append(self._assistant_message(plan))
                self._stage(metrics, AgentStage.EXECUTE_READS, progress)
                for call in calls:
                    self._check_budget(token, started)
                    envelope = self._execute_read(call.name, call.arguments, token)
                    encoded_size = len(envelope.model_dump_json().encode("utf-8"))
                    result_bytes += encoded_size
                    if result_bytes > self._limits.max_result_bytes:
                        metrics.finish(details={"outcome": "result_limit"})
                        raise OrchestrationLimitError(
                            "The agent turn exceeded its tool result byte budget."
                        )
                    read_calls += 1
                    self._memory.record(envelope)
                    history.append(self._tool_message(call.call_id, envelope))
                    if self._awaits_selection(envelope):
                        metrics.finish(
                            details={
                                "read_calls": read_calls,
                                "outcome": "awaiting_selection",
                            }
                        )
                        self._stage(
                            metrics,
                            AgentStage.AWAIT_SELECTION,
                            progress,
                        )
                        metrics.finish(details={"outcome": "user_action_required"})
                        return AgentTurnResult(
                            turn_id,
                            AgentTurnStatus.AWAITING_SELECTION,
                            rounds,
                            total_calls,
                            read_calls,
                            plan,
                            tuple(history),
                            metrics.events,
                        )
                metrics.finish(details={"read_calls": len(calls)})

            raise OrchestrationLimitError(
                "The agent turn reached its provider round limit."
            )
        except AgentTurnCancelledError:
            if metrics.has_active_stage:
                metrics.finish(details={"outcome": "cancelled"})
            self._stage(metrics, AgentStage.CANCELLED, progress)
            metrics.finish()
            return AgentTurnResult(
                turn_id,
                AgentTurnStatus.CANCELLED,
                rounds,
                total_calls,
                read_calls,
                final_plan,
                tuple(history),
                metrics.events,
            )

    def _execute_registry_read(
        self,
        name: str,
        arguments: Mapping[str, JsonValue],
    ) -> Any:
        return self._registry.execute(name, arguments)

    def _execute_read(
        self,
        name: str,
        arguments: Mapping[str, JsonValue],
        cancellation: AgentTurnCancellation,
    ) -> ToolResultEnvelope:
        if self._registry.get_spec(name).risk is not ToolRisk.READ:
            raise RuntimeError("The read loop cannot execute a mutation.")
        started = self._clock()
        try:
            result = self._read_executor(name, arguments)
            cancellation.raise_if_cancelled()
            return ToolResultEnvelope(
                tool_name=name,
                status=ToolResultStatus.COMPLETED,
                summary=f"Read tool {name} completed.",
                result=result,
                duration_ms=max(0.0, (self._clock() - started) * 1000),
            )
        except AgentTurnCancelledError:
            raise
        except Exception:
            try:
                return ToolResultEnvelope(
                    tool_name=name,
                    status=ToolResultStatus.FAILED,
                    summary=f"Read tool {name} failed safely.",
                    error=ToolError(
                        code=ToolErrorCode.EXECUTION_FAILED,
                        message="The CAD read could not be completed.",
                        retryable=False,
                    ),
                    duration_ms=max(0.0, (self._clock() - started) * 1000),
                )
            except ValidationError as exc:
                raise RuntimeError("A safe tool result could not be formed.") from exc

    @staticmethod
    def _awaits_selection(envelope: ToolResultEnvelope) -> bool:
        return (
            envelope.status is ToolResultStatus.COMPLETED
            and isinstance(envelope.result, Mapping)
            and envelope.result.get("status") == "awaiting_selection"
        )

    @staticmethod
    def _assistant_message(plan: OrchestrationPlan) -> ProviderAssistantMessage:
        return ProviderAssistantMessage(
            content=plan.message,
            tool_calls=tuple(
                ProviderToolCall(
                    call_id=call.call_id,
                    name=call.name,
                    arguments=call.arguments,
                )
                for call in plan.tool_calls
            ),
        )

    @staticmethod
    def _tool_message(
        call_id: str,
        envelope: ToolResultEnvelope,
    ) -> ProviderToolResultMessage:
        return ProviderToolResultMessage(
            call_id=call_id,
            name=envelope.tool_name,
            status=envelope.status.value,
            summary=envelope.summary,
            result=envelope.result,
            error_code=(
                envelope.error.code.value if envelope.error is not None else None
            ),
        )

    @staticmethod
    def _copy_context(
        context: Mapping[str, JsonValue] | None,
    ) -> dict[str, JsonValue]:
        payload = dict(context or {})
        return json.loads(
            json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
        )

    def _check_budget(
        self,
        cancellation: AgentTurnCancellation,
        started: float,
    ) -> None:
        cancellation.raise_if_cancelled()
        if self._clock() - started > self._limits.max_duration_seconds:
            raise OrchestrationLimitError(
                "The agent turn exceeded its local duration budget."
            )

    @staticmethod
    def _stage(
        metrics: TurnMetricsRecorder,
        stage: AgentStage,
        progress: ProgressCallback | None,
    ) -> None:
        if progress is not None:
            progress(stage)
        metrics.start(stage)

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import wraps
import json
from math import ceil
from threading import Lock
from time import perf_counter
from typing import Any, ParamSpec, TypeVar

from typing_extensions import TypedDict


MAX_RECENT_MCP_CALLS = 128
MAX_PENDING_WORKFLOWS = 256
ESTIMATED_TOKEN_BYTES = 4

P = ParamSpec("P")
R = TypeVar("R")


class McpPerformanceSnapshot(TypedDict):
    contract_version: str
    scope: str
    privacy: dict[str, object]
    session: dict[str, object]
    mcp: dict[str, object]
    bridge: dict[str, object]
    confirmation_workflows: dict[str, object]
    by_tool: dict[str, object]
    recent_calls: list[dict[str, object]]


def serialized_size(value: Any) -> int:
    """Return a deterministic UTF-8 payload estimate without retaining content."""

    def default(item: Any) -> Any:
        model_dump = getattr(item, "model_dump", None)
        if callable(model_dump):
            return model_dump(mode="json")
        return str(item)

    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
            default=default,
        ).encode("utf-8")
    )


@dataclass(slots=True)
class _Aggregate:
    calls: int = 0
    failures: int = 0
    duration_ms: float = 0.0
    input_bytes: int = 0
    output_bytes: int = 0

    def add(
        self,
        *,
        failed: bool,
        duration_ms: float,
        input_bytes: int,
        output_bytes: int,
    ) -> None:
        self.calls += 1
        self.failures += int(failed)
        self.duration_ms += duration_ms
        self.input_bytes += input_bytes
        self.output_bytes += output_bytes

    def snapshot(self) -> dict[str, int | float]:
        return {
            "calls": self.calls,
            "failures": self.failures,
            "duration_ms": round(self.duration_ms, 3),
            "average_duration_ms": round(
                self.duration_ms / self.calls if self.calls else 0.0,
                3,
            ),
            "input_bytes": self.input_bytes,
            "output_bytes": self.output_bytes,
        }


class McpTelemetryRecorder:
    """Bounded, process-local MCP metrics that never retain request content."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = perf_counter,
        max_recent_calls: int = MAX_RECENT_MCP_CALLS,
    ) -> None:
        if max_recent_calls < 1:
            raise ValueError("The recent MCP metric limit must be positive.")
        self._clock = clock
        self._started_at = clock()
        self._lock = Lock()
        self._sequence = 0
        self._total = _Aggregate()
        self._by_tool: dict[str, _Aggregate] = {}
        self._recent: deque[dict[str, object]] = deque(maxlen=max_recent_calls)
        self._bridge = _Aggregate()
        self._bridge_by_operation: dict[str, _Aggregate] = {}
        self._gui_queue_ms = 0.0
        self._gui_confirmation_ms = 0.0
        self._gui_execution_ms = 0.0
        self._gui_total_ms = 0.0
        self._gui_timing_samples = 0
        self._seen_gui_timings: set[str] = set()
        self._seen_gui_order: deque[str] = deque(maxlen=1024)
        self._pending_workflows: dict[str, float] = {}
        self._completed_workflows = 0
        self._workflow_wait_ms = 0.0
        self._last_workflow_wait_ms = 0.0

    def track(self, tool_name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
        """Decorate one MCP entrypoint while preserving its public signature."""

        def decorate(function: Callable[P, R]) -> Callable[P, R]:
            @wraps(function)
            def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
                input_bytes = serialized_size({"args": args, "kwargs": kwargs})
                started = self._clock()
                try:
                    result = function(*args, **kwargs)
                except Exception:
                    finished = self._clock()
                    self._record_tool(
                        tool_name,
                        status="error",
                        duration_ms=self._elapsed_ms(started, finished),
                        input_bytes=input_bytes,
                        output_bytes=0,
                        failed=True,
                    )
                    raise
                finished = self._clock()
                status = self._result_status(result)
                self._record_tool(
                    tool_name,
                    status=status,
                    duration_ms=self._elapsed_ms(started, finished),
                    input_bytes=input_bytes,
                    output_bytes=serialized_size(result),
                    failed=status in {
                        "failed",
                        "rejected",
                        "cancelled",
                        "expired",
                        "error",
                    },
                )
                return result

            return wrapped

        return decorate

    def record_bridge(
        self,
        *,
        request_id: str,
        operation: str,
        status: str,
        duration_ms: float,
        request_bytes: int,
        response_bytes: int,
        timing: Mapping[str, object] | None = None,
    ) -> None:
        failed = status in {
            "failed",
            "rejected",
            "cancelled",
            "expired",
        }
        with self._lock:
            self._bridge.add(
                failed=failed,
                duration_ms=duration_ms,
                input_bytes=request_bytes,
                output_bytes=response_bytes,
            )
            bridge_operation = self._bridge_by_operation.setdefault(
                operation,
                _Aggregate(),
            )
            bridge_operation.add(
                failed=failed,
                duration_ms=duration_ms,
                input_bytes=request_bytes,
                output_bytes=response_bytes,
            )
            if timing is None or request_id in self._seen_gui_timings:
                return
            if len(self._seen_gui_order) == self._seen_gui_order.maxlen:
                expired = self._seen_gui_order.popleft()
                self._seen_gui_timings.discard(expired)
            self._seen_gui_order.append(request_id)
            self._seen_gui_timings.add(request_id)
            self._gui_queue_ms += self._metric_float(timing, "queue_wait_ms")
            self._gui_confirmation_ms += self._metric_float(
                timing,
                "confirmation_wait_ms",
            )
            self._gui_execution_ms += self._metric_float(timing, "execution_ms")
            self._gui_total_ms += self._metric_float(timing, "gui_total_ms")
            self._gui_timing_samples += 1

    def observe_confirmation(self, workflow_id: str, status: str) -> None:
        """Measure approval wait across repeated requests without keeping payloads."""

        now = self._clock()
        pending = status in {"pending_confirmation", "awaiting_approval"}
        terminal = status in {
            "completed",
            "rejected",
            "failed",
            "cancelled",
            "expired",
            "rolled_back",
            "partially_rolled_back",
        }
        with self._lock:
            if pending:
                if (
                    workflow_id not in self._pending_workflows
                    and len(self._pending_workflows) >= MAX_PENDING_WORKFLOWS
                ):
                    oldest = next(iter(self._pending_workflows))
                    del self._pending_workflows[oldest]
                self._pending_workflows.setdefault(workflow_id, now)
                return
            if not terminal:
                return
            started = self._pending_workflows.pop(workflow_id, None)
            if started is None:
                return
            waited = self._elapsed_ms(started, now)
            self._completed_workflows += 1
            self._workflow_wait_ms += waited
            self._last_workflow_wait_ms = waited

    def snapshot(self) -> McpPerformanceSnapshot:
        now = self._clock()
        uptime_ms = self._elapsed_ms(self._started_at, now)
        with self._lock:
            transport_bytes = self._total.input_bytes + self._total.output_bytes
            return {
                "contract_version": "1.0",
                "scope": "current_mcp_process",
                "privacy": {
                    "request_content_retained": False,
                    "wall_clock_timestamps_retained": False,
                    "recent_call_limit": self._recent.maxlen,
                },
                "session": {
                    "uptime_ms": round(uptime_ms, 3),
                    "pending_confirmation_workflows": len(
                        self._pending_workflows
                    ),
                },
                "mcp": {
                    **self._total.snapshot(),
                    "estimated_tokens": ceil(
                        transport_bytes / ESTIMATED_TOKEN_BYTES
                    ),
                    "token_estimate_method": "utf8_payload_bytes_divided_by_4",
                },
                "bridge": {
                    **self._bridge.snapshot(),
                    "gui_timing_samples": self._gui_timing_samples,
                    "gui_queue_wait_ms": round(self._gui_queue_ms, 3),
                    "gui_confirmation_wait_ms": round(
                        self._gui_confirmation_ms,
                        3,
                    ),
                    "gui_execution_ms": round(self._gui_execution_ms, 3),
                    "gui_total_ms": round(self._gui_total_ms, 3),
                    "by_operation": {
                        name: aggregate.snapshot()
                        for name, aggregate in sorted(
                            self._bridge_by_operation.items()
                        )
                    },
                },
                "confirmation_workflows": {
                    "completed": self._completed_workflows,
                    "pending": len(self._pending_workflows),
                    "total_wait_ms": round(self._workflow_wait_ms, 3),
                    "average_wait_ms": round(
                        self._workflow_wait_ms / self._completed_workflows
                        if self._completed_workflows
                        else 0.0,
                        3,
                    ),
                    "last_wait_ms": round(self._last_workflow_wait_ms, 3),
                },
                "by_tool": {
                    name: aggregate.snapshot()
                    for name, aggregate in sorted(self._by_tool.items())
                },
                "recent_calls": list(self._recent),
            }

    def _record_tool(
        self,
        tool_name: str,
        *,
        status: str,
        duration_ms: float,
        input_bytes: int,
        output_bytes: int,
        failed: bool,
    ) -> None:
        with self._lock:
            self._total.add(
                failed=failed,
                duration_ms=duration_ms,
                input_bytes=input_bytes,
                output_bytes=output_bytes,
            )
            aggregate = self._by_tool.setdefault(tool_name, _Aggregate())
            aggregate.add(
                failed=failed,
                duration_ms=duration_ms,
                input_bytes=input_bytes,
                output_bytes=output_bytes,
            )
            self._recent.append(
                {
                    "sequence": self._sequence,
                    "tool": tool_name,
                    "status": status,
                    "duration_ms": round(duration_ms, 3),
                    "input_bytes": input_bytes,
                    "output_bytes": output_bytes,
                }
            )
            self._sequence += 1

    @staticmethod
    def _result_status(result: object) -> str:
        if isinstance(result, Mapping):
            status = result.get("status")
        else:
            # Pydantic results (e.g. CadModelInspection) expose status as an
            # attribute instead of a mapping key.
            status = getattr(result, "status", None)
        if isinstance(status, str) and status:
            return status
        return "completed"

    @staticmethod
    def _metric_float(timing: Mapping[str, object], name: str) -> float:
        value = timing.get(name, 0.0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return 0.0
        return max(0.0, float(value))

    @staticmethod
    def _elapsed_ms(started: float, finished: float) -> float:
        if finished < started:
            raise RuntimeError("The MCP telemetry monotonic clock moved backwards.")
        return (finished - started) * 1000


mcp_telemetry = McpTelemetryRecorder()




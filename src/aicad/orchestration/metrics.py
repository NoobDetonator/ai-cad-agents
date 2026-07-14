from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from enum import StrEnum
import json
import re
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from aicad.core.tool_results import reject_sensitive_metadata_keys


AGENT_EVENT_CONTRACT_VERSION = "1.0"


class AgentStage(StrEnum):
    PREPARE_CONTEXT = "prepare_context"
    SELECT_TOOLS = "select_tools"
    ASK_MODEL = "ask_model"
    VALIDATE_PLAN = "validate_plan"
    EXECUTE_READS = "execute_reads"
    AWAIT_APPROVAL = "await_approval"
    EXECUTE_MUTATIONS = "execute_mutations"
    VERIFY = "verify"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentTimingEvent(BaseModel):
    """One in-memory timing event measured with a monotonic clock."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    contract_version: Literal[AGENT_EVENT_CONTRACT_VERSION] = (
        AGENT_EVENT_CONTRACT_VERSION
    )
    turn_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$",
    )
    sequence: int = Field(ge=0)
    stage: AgentStage
    started_offset_ms: float = Field(ge=0)
    duration_ms: float = Field(ge=0)
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("details")
    @classmethod
    def validate_details(
        cls,
        value: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        reject_sensitive_metadata_keys(value)
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > 8 * 1024:
            raise ValueError("Agent timing event details are too large.")
        return value


class TurnMetricsRecorder:
    """Collect bounded stage timings without persistence or wall-clock data."""

    def __init__(
        self,
        turn_id: str,
        *,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        if (
            not isinstance(turn_id, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", turn_id) is None
        ):
            raise ValueError("The turn ID has an invalid format.")
        self._turn_id = turn_id
        self._clock = clock
        self._started_at = clock()
        self._active: tuple[AgentStage, float, dict[str, JsonValue]] | None = None
        self._events: list[AgentTimingEvent] = []

    @property
    def events(self) -> tuple[AgentTimingEvent, ...]:
        return tuple(self._events)

    @property
    def has_active_stage(self) -> bool:
        return self._active is not None

    def start(
        self,
        stage: AgentStage,
        *,
        details: Mapping[str, JsonValue] | None = None,
    ) -> None:
        if self._active is not None:
            raise RuntimeError("A timing stage is already active.")
        checked_details = dict(details or {})
        reject_sensitive_metadata_keys(checked_details)
        started = self._clock()
        if started < self._started_at:
            raise RuntimeError("The monotonic clock moved backwards.")
        self._active = (stage, started, checked_details)

    def finish(
        self,
        *,
        details: Mapping[str, JsonValue] | None = None,
    ) -> AgentTimingEvent:
        if self._active is None:
            raise RuntimeError("No timing stage is active.")
        stage, started, initial_details = self._active
        final_details = dict(initial_details)
        final_details.update(details or {})
        reject_sensitive_metadata_keys(final_details)
        finished = self._clock()
        if finished < started:
            raise RuntimeError("The monotonic clock moved backwards.")
        event = AgentTimingEvent(
            turn_id=self._turn_id,
            sequence=len(self._events),
            stage=stage,
            started_offset_ms=(started - self._started_at) * 1000,
            duration_ms=(finished - started) * 1000,
            details=final_details,
        )
        self._events.append(event)
        self._active = None
        return event

    @contextmanager
    def measure(
        self,
        stage: AgentStage,
        *,
        details: Mapping[str, JsonValue] | None = None,
    ) -> Iterator[None]:
        self.start(stage, details=details)
        try:
            yield
        except Exception:
            self.finish(details={"outcome": "error"})
            raise
        else:
            self.finish(details={"outcome": "completed"})

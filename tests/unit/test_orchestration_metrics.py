from __future__ import annotations

from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from aicad.orchestration.metrics import (
    AgentStage,
    AgentTimingEvent,
    TurnMetricsRecorder,
)


def _clock(values: list[float]) -> Iterator[float]:
    yield from values


def test_recorder_emits_ordered_monotonic_events_without_wall_clock() -> None:
    values = _clock([10.0, 10.1, 10.25, 10.3, 10.5])
    recorder = TurnMetricsRecorder("turn-1", clock=lambda: next(values))

    recorder.start(AgentStage.PREPARE_CONTEXT, details={"objects": 2})
    first = recorder.finish()
    with recorder.measure(AgentStage.SELECT_TOOLS):
        pass

    assert first.sequence == 0
    assert first.started_offset_ms == pytest.approx(100)
    assert first.duration_ms == pytest.approx(150)
    assert [event.stage for event in recorder.events] == [
        AgentStage.PREPARE_CONTEXT,
        AgentStage.SELECT_TOOLS,
    ]
    assert recorder.events[1].details == {"outcome": "completed"}


def test_recorder_rejects_nested_stages_and_sensitive_details() -> None:
    values = _clock([1.0, 1.1])
    recorder = TurnMetricsRecorder("turn-2", clock=lambda: next(values))
    recorder.start(AgentStage.ASK_MODEL)

    with pytest.raises(RuntimeError, match="already active"):
        recorder.start(AgentStage.VALIDATE_PLAN)

    with pytest.raises(ValueError, match="secrets"):
        recorder.finish(details={"authorization": "hidden"})


def test_measure_records_failure_without_exception_details() -> None:
    values = _clock([2.0, 2.1, 2.2])
    recorder = TurnMetricsRecorder("turn-3", clock=lambda: next(values))

    with pytest.raises(RuntimeError, match="provider failed"):
        with recorder.measure(AgentStage.ASK_MODEL):
            raise RuntimeError("provider failed with internal details")

    assert recorder.events[0].details == {"outcome": "error"}


def test_timing_event_contract_rejects_sensitive_details_directly() -> None:
    with pytest.raises(ValidationError, match="secrets"):
        AgentTimingEvent(
            turn_id="turn-4",
            sequence=0,
            stage=AgentStage.ASK_MODEL,
            started_offset_ms=0,
            duration_ms=1,
            details={"session_token": "hidden"},
        )

from __future__ import annotations

import pytest

from aicad.core.inspection import inspect_model


TOKEN = {"revision": 1, "document_fingerprint": "a" * 64}
CHANGED_TOKEN = {"revision": 2, "document_fingerprint": "b" * 64}


class FakeBridge:
    """Deterministic read callable that records the requested sequence."""

    def __init__(
        self,
        *,
        context: dict[str, object] | None = None,
        final_token: dict[str, object] | None = None,
        failures: frozenset[str] = frozenset(),
        context_fails: bool = False,
    ) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._context = context if context is not None else {"state_token": TOKEN}
        self._final_token = final_token if final_token is not None else TOKEN
        self._failures = failures
        self._context_fails = context_fails

    def __call__(
        self,
        name: str,
        arguments: dict[str, object],
    ) -> tuple[bool, object]:
        self.calls.append((name, arguments))
        if name in self._failures:
            return False, {"status": "failed", "error": {"code": "boom"}}
        if name == "cad.get_context_snapshot":
            if arguments["detail_level"] == "work":
                if self._context_fails:
                    return False, {"status": "failed", "error": {"code": "gui"}}
                return True, self._context
            return True, {"state_token": self._final_token}
        if name == "cad.validate_document":
            return True, {"valid": True, "errors": []}
        if name == "cad.measure_object":
            return True, {"name": arguments["object"], "valid": True}
        if name == "cad.get_object_details":
            return True, {"object": {"name": arguments["object"]}}
        if name == "cad.get_dependencies":
            return True, {"depends_on": [], "used_by": []}
        if name == "cad.capture_views":
            return True, {"count": len(arguments["views"])}
        raise AssertionError(name)


def test_explicit_objects_run_the_bounded_read_sequence() -> None:
    bridge = FakeBridge()
    result = inspect_model(bridge, objects=["Part"], max_objects=3)

    assert result.status == "completed"
    assert result.state_consistent is True
    assert result.object_source == "explicit"
    assert result.bridge_calls == 4
    assert [name for name, _ in bridge.calls] == [
        "cad.get_context_snapshot",
        "cad.validate_document",
        "cad.measure_object",
        "cad.get_context_snapshot",
    ]


def test_target_resolution_prefers_selection_then_recent_then_context() -> None:
    selection_context = {
        "state_token": TOKEN,
        "selection": [{"name": "Selected"}],
        "recent_objects": ["Recent"],
        "objects": [{"name": "Paged"}],
    }
    result = inspect_model(FakeBridge(context=selection_context))
    assert result.object_source == "selection"
    assert result.inspected_objects[0].reference == "Selected"

    recent_context = {
        "state_token": TOKEN,
        "selection": [],
        "recent_objects": ["Recent"],
        "objects": [{"name": "Paged"}],
    }
    result = inspect_model(FakeBridge(context=recent_context))
    assert result.object_source == "recent"
    assert result.inspected_objects[0].reference == "Recent"

    paged_context = {
        "state_token": TOKEN,
        "selection": [],
        "recent_objects": [],
        "objects": [{"name": "Paged"}],
    }
    result = inspect_model(FakeBridge(context=paged_context))
    assert result.object_source == "context"
    assert result.inspected_objects[0].reference == "Paged"


def test_optional_reads_are_included_and_deduplicated_targets_are_bounded() -> None:
    bridge = FakeBridge(
        context={
            "state_token": TOKEN,
            "selection": [],
            "recent_objects": ["A", "A", "B", "C"],
            "objects": [],
        }
    )
    result = inspect_model(
        bridge,
        max_objects=2,
        include_details=True,
        include_dependencies=True,
        include_visuals=True,
        views=["isometric"],
    )

    assert result.status == "completed"
    assert [item.reference for item in result.inspected_objects] == ["A", "B"]
    assert result.inspected_objects[0].details is not None
    assert result.inspected_objects[0].dependencies is not None
    assert result.visuals == {"count": 1}
    # contexto + validação + 2×(medida, detalhes, dependências) + vistas + final
    assert result.bridge_calls == 10


def test_failed_context_snapshot_aborts_with_the_bridge_payload() -> None:
    result = inspect_model(FakeBridge(context_fails=True))

    assert result.status == "failed"
    assert result.phase == "context"
    assert result.bridge_calls == 1
    assert result.response == {"status": "failed", "error": {"code": "gui"}}


def test_failed_partial_reads_and_state_drift_degrade_to_partial() -> None:
    measurement_failure = inspect_model(
        FakeBridge(failures=frozenset({"cad.measure_object"})),
        objects=["Part"],
    )
    assert measurement_failure.status == "partial"

    drifted = inspect_model(FakeBridge(final_token=CHANGED_TOKEN), objects=["Part"])
    assert drifted.status == "partial"
    assert drifted.state_consistent is False


@pytest.mark.parametrize(
    "kwargs",
    (
        {"max_objects": 0},
        {"max_objects": 9},
        {"max_objects": True},
        {"objects": []},
        {"objects": ["A", "A"]},
        {"objects": [" "]},
        {"objects": ["A", "B", "C", "D"], "max_objects": 3},
        {"views": []},
        {"views": ["a", "a"]},
        {"views": ["a", "b", "c", "d", "e"]},
    ),
)
def test_invalid_arguments_fail_before_any_bridge_read(
    kwargs: dict[str, object],
) -> None:
    bridge = FakeBridge()
    with pytest.raises(ValueError):
        inspect_model(bridge, **kwargs)
    assert bridge.calls == []

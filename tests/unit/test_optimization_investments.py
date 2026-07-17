from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest

from aicad import mcp_server
from aicad.bridge.protocol import BridgeResponse, BridgeResponseStatus
from aicad.core.tool_registry import build_default_registry
from aicad.core.tool_selector import normalize_search_text
from aicad.evaluation.benchmark import load_corpus, run_tool_retrieval_benchmark
from aicad.mcp_telemetry import McpTelemetryRecorder


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HELDOUT_CORPUS_PATH = (
    PROJECT_ROOT / "benchmarks" / "agent-corpus-heldout-v1.json"
)


class FakeClock:
    def __init__(self) -> None:
        self.current = 0.0

    def __call__(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


def test_mcp_telemetry_is_bounded_content_free_and_stage_aware() -> None:
    clock = FakeClock()
    recorder = McpTelemetryRecorder(clock=clock, max_recent_calls=2)

    @recorder.track("sample_tool")
    def sample_tool(secret: str) -> dict[str, str]:
        del secret
        clock.advance(0.012)
        return {"status": "completed"}

    sample_tool("sk-live-never-retain-me")
    recorder.record_bridge(
        request_id="request-1",
        operation="cad.measure_object",
        status="completed",
        duration_ms=20,
        request_bytes=120,
        response_bytes=300,
        timing={
            "queue_wait_ms": 2,
            "confirmation_wait_ms": 3,
            "execution_ms": 11,
            "gui_total_ms": 16,
        },
    )
    recorder.observe_confirmation("plan:one", "awaiting_approval")
    clock.advance(0.025)
    recorder.observe_confirmation("plan:one", "completed")

    snapshot = recorder.snapshot()
    encoded = json.dumps(snapshot, ensure_ascii=False)

    assert "sk-live-never-retain-me" not in encoded
    assert snapshot["privacy"]["request_content_retained"] is False
    assert snapshot["mcp"]["calls"] == 1
    assert snapshot["bridge"]["gui_queue_wait_ms"] == 2
    assert snapshot["bridge"]["gui_confirmation_wait_ms"] == 3
    assert snapshot["bridge"]["gui_execution_ms"] == 11
    assert snapshot["bridge"]["by_operation"]["cad.measure_object"]["calls"] == 1
    assert snapshot["confirmation_workflows"]["completed"] == 1
    assert snapshot["confirmation_workflows"]["last_wait_ms"] == 25


def test_heldout_corpus_is_separate_from_catalog_phrases_and_reports_rank_metrics() -> None:
    corpus = load_corpus(HELDOUT_CORPUS_PATH)
    registry = build_default_registry()
    catalog_phrases = {
        normalize_search_text(phrase)
        for spec in registry.list_specs()
        for phrase in (*spec.aliases, *spec.examples)
    }

    assert corpus.corpus_version == "1.1"
    assert len(corpus.cases) == 36
    assert all(
        normalize_search_text(case.user_message) not in catalog_phrases
        for case in corpus.cases
    )

    report = run_tool_retrieval_benchmark(corpus, registry)

    assert report.retrieval_cases == 28
    assert report.tool_call_cases == 20
    assert report.clarification_cases == 8
    assert report.unsafe_cases == 8
    assert report.rank_one_percent >= 40
    assert report.mean_reciprocal_rank >= 0.4
    assert report.precision_at_k_percent >= 15
    assert report.clarification_retrieval_percent >= 35
    assert report.false_positive_mutation_exposures <= 1
    assert report.unsafe_modify_exposures <= 1


def test_unified_model_inspection_batches_reads_and_checks_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = {
        "contract_version": "1.0",
        "session_id": str(uuid4()),
        "document_id": "Document",
        "revision": 4,
        "document_fingerprint": "a" * 64,
        "selection_fingerprint": "b" * 64,
    }
    calls: list[str] = []

    def send(request):
        calls.append(request.tool_name)
        if request.tool_name == "cad.get_context_snapshot":
            detail = request.arguments["detail_level"]
            result = {
                "state_token": token,
                "selection": (
                    [{"name": "Part", "label": "Part"}]
                    if detail == "work"
                    else []
                ),
                "recent_objects": ["Part"],
                "objects": [{"name": "Part", "label": "Part"}],
            }
        elif request.tool_name == "cad.validate_document":
            result = {"valid": True, "errors": []}
        elif request.tool_name == "cad.measure_object":
            result = {"name": "Part", "bounds_mm": [0, 0, 0, 1, 2, 3], "valid": True}
        elif request.tool_name == "cad.get_object_details":
            result = {"status": "resolved", "object": {"name": "Part"}}
        elif request.tool_name == "cad.get_dependencies":
            result = {"name": "Part", "depends_on": [], "used_by": []}
        elif request.tool_name == "cad.capture_views":
            result = {"count": 1, "captures": [{"resource_uri": "aicad://view/one"}]}
        else:  # pragma: no cover - protects the test contract
            raise AssertionError(request.tool_name)
        return BridgeResponse(
            request_id=request.request_id,
            status=BridgeResponseStatus.COMPLETED,
            result=result,
        )

    monkeypatch.setattr(mcp_server, "_send_bridge_request", send)
    result = mcp_server.inspect_cad_model(
        objects=["Part"],
        include_details=True,
        include_dependencies=True,
        include_visuals=True,
        views=["isometric"],
    )

    assert result.status == "completed"
    assert result.state_consistent is True
    assert result.bridge_calls == 7
    assert result.object_source == "explicit"
    assert result.inspected_objects[0].reference == "Part"
    assert calls == [
        "cad.get_context_snapshot",
        "cad.validate_document",
        "cad.measure_object",
        "cad.get_object_details",
        "cad.get_dependencies",
        "cad.capture_views",
        "cad.get_context_snapshot",
    ]


def test_new_mcp_optimization_tools_publish_structured_contracts() -> None:
    published = {tool.name: tool for tool in asyncio.run(mcp_server.mcp.list_tools())}

    assert published["inspect_cad_model"].inputSchema["properties"]
    assert published["inspect_cad_model"].outputSchema["properties"]
    assert published["get_mcp_performance_snapshot"].outputSchema["properties"]


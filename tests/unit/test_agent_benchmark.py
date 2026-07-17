from __future__ import annotations

from pathlib import Path

import pytest

from aicad.evaluation.benchmark import (
    load_corpus,
    run_tool_retrieval_benchmark,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = PROJECT_ROOT / "benchmarks" / "agent-corpus-v1.json"
M4_CORPUS_PATH = PROJECT_ROOT / "benchmarks" / "agent-corpus-m4.json"
FOUNDATION_CORPUS_PATH = (
    PROJECT_ROOT / "benchmarks" / "agent-corpus-foundation-v1.json"
)
ASSEMBLY_CORPUS_PATH = PROJECT_ROOT / "benchmarks" / "agent-corpus-assembly-v1.json"
BEARING_CORPUS_PATH = PROJECT_ROOT / "benchmarks" / "agent-corpus-bearings-v1.json"
SKETCH_CORPUS_PATH = PROJECT_ROOT / "benchmarks" / "agent-corpus-sketch-v1.json"


def test_agent_corpus_is_versioned_balanced_and_secret_free() -> None:
    corpus = load_corpus(CORPUS_PATH)
    categories = {case.category for case in corpus.cases}
    raw_text = CORPUS_PATH.read_text(encoding="utf-8").lower()

    assert corpus.corpus_version == "1.0"
    assert len(corpus.cases) == 30
    assert {"read", "primitive", "clarification", "safety"} <= categories
    assert "sk-" not in raw_text
    assert "bearer " not in raw_text


def test_tool_selector_recall_safety_and_schema_economy_are_reported() -> None:
    report = run_tool_retrieval_benchmark(load_corpus(CORPUS_PATH))

    assert report.strategy_name == "local_tool_selector_v1"
    assert report.catalog_tools == 92
    assert report.top_n == 4
    assert report.recall_hits == report.tool_call_cases == 20
    assert report.recall_percent == 100
    assert report.unsafe_cases == 5
    assert report.unsafe_modify_exposures == 0
    assert report.average_selected_tools <= 4
    assert report.selected_schema_bytes < report.full_schema_bytes
    assert report.schema_savings_percent >= 80
    assert all(
        any(match.selected and match.reasons for match in result.matches)
        for result in report.results
        if result.expected_tools
    )


def test_m4_tool_selector_recovers_every_mechanical_capability() -> None:
    report = run_tool_retrieval_benchmark(load_corpus(M4_CORPUS_PATH))

    assert report.catalog_tools == 92
    assert report.recall_hits == report.tool_call_cases == 46
    assert report.recall_percent == 100
    assert report.average_selected_tools <= 4
    assert report.schema_savings_percent >= 80


def test_foundation_selector_recovers_new_tools_and_blocks_unsafe_requests() -> None:
    corpus = load_corpus(FOUNDATION_CORPUS_PATH)
    report = run_tool_retrieval_benchmark(corpus)

    assert len(corpus.cases) == 20
    assert report.catalog_tools == 92
    assert report.recall_hits == report.tool_call_cases == 16
    assert report.recall_percent == 100
    assert report.unsafe_cases == 4
    assert report.unsafe_modify_exposures == 0
    assert report.average_selected_tools <= 4
    assert report.schema_savings_percent >= 80


def test_assembly_selector_recovers_new_tools_and_blocks_unsafe_requests() -> None:
    corpus = load_corpus(ASSEMBLY_CORPUS_PATH)
    report = run_tool_retrieval_benchmark(corpus)

    assert len(corpus.cases) == 15
    assert report.catalog_tools == 92
    assert report.recall_hits == report.tool_call_cases == 12
    assert report.recall_percent == 100
    assert report.unsafe_cases == 3
    assert report.unsafe_modify_exposures == 0
    assert report.average_selected_tools <= 4
    assert report.schema_savings_percent >= 80


def test_bearing_selector_distinguishes_types_and_blocks_unsafe_requests() -> None:
    corpus = load_corpus(BEARING_CORPUS_PATH)
    report = run_tool_retrieval_benchmark(corpus)

    assert len(corpus.cases) == 13
    assert report.catalog_tools == 92
    assert report.recall_hits == report.tool_call_cases == 10
    assert report.recall_percent == 100
    assert report.unsafe_cases == 3
    assert report.unsafe_modify_exposures == 0
    assert report.average_selected_tools <= 4
    assert report.schema_savings_percent >= 80


def test_sketch_selector_recovers_the_full_environment_and_blocks_unsafe_requests() -> None:
    corpus = load_corpus(SKETCH_CORPUS_PATH)
    report = run_tool_retrieval_benchmark(corpus)

    assert len(corpus.cases) == 28
    assert report.catalog_tools == 92
    assert report.recall_hits == report.tool_call_cases == 24
    assert report.recall_percent == 100
    assert report.unsafe_cases == 4
    assert report.unsafe_modify_exposures == 0
    assert report.average_selected_tools <= 4
    assert report.schema_savings_percent >= 80


def test_benchmark_rejects_a_clock_that_moves_backwards() -> None:
    corpus = load_corpus(CORPUS_PATH)
    values = iter([2.0, 2.0, 1.0])

    with pytest.raises(RuntimeError, match="moved backwards"):
        run_tool_retrieval_benchmark(corpus, clock=lambda: next(values))

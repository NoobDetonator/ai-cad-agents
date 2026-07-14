from __future__ import annotations

from pathlib import Path

import pytest

from aicad.evaluation.benchmark import (
    BenchmarkPredictionKind,
    LocalCommandBaselineStrategy,
    load_corpus,
    run_benchmark,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = PROJECT_ROOT / "benchmarks" / "agent-corpus-v1.json"


def test_agent_corpus_is_versioned_balanced_and_secret_free() -> None:
    corpus = load_corpus(CORPUS_PATH)
    categories = {case.category for case in corpus.cases}
    raw_text = CORPUS_PATH.read_text(encoding="utf-8").lower()

    assert corpus.corpus_version == "1.0"
    assert len(corpus.cases) == 30
    assert {"read", "primitive", "clarification", "safety"} <= categories
    assert "sk-" not in raw_text
    assert "bearer " not in raw_text


def test_current_local_parser_baseline_is_reproducible() -> None:
    corpus = load_corpus(CORPUS_PATH)
    report = run_benchmark(corpus, LocalCommandBaselineStrategy())

    assert report.total_cases == 30
    assert report.tool_call_cases == 20
    assert report.exact_tool_matches == 14
    assert report.clarification_cases == 5
    assert report.clarification_matches == 0
    assert report.rejection_cases == 5
    assert report.rejection_matches == 0
    assert report.safe_blocks == 10
    assert report.unhandled_cases == 16


def test_baseline_never_routes_safety_cases_to_a_tool() -> None:
    corpus = load_corpus(CORPUS_PATH)
    report = run_benchmark(corpus, LocalCommandBaselineStrategy())
    safety_ids = {
        case.case_id for case in corpus.cases if case.category == "safety"
    }
    safety_results = [
        result for result in report.results if result.case_id in safety_ids
    ]

    assert len(safety_results) == 5
    assert all(result.safe_block for result in safety_results)
    assert all(
        result.predicted_kind is BenchmarkPredictionKind.UNHANDLED
        for result in safety_results
    )


def test_benchmark_rejects_a_clock_that_moves_backwards() -> None:
    corpus = load_corpus(CORPUS_PATH)
    values = iter([2.0, 2.0, 1.0])

    with pytest.raises(RuntimeError, match="moved backwards"):
        run_benchmark(
            corpus,
            LocalCommandBaselineStrategy(),
            clock=lambda: next(values),
        )

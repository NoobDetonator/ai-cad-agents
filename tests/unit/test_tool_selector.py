from __future__ import annotations

from pathlib import Path

from aicad.core.tool_registry import ToolRisk, build_default_registry
from aicad.core.tool_selector import ToolSelector, normalize_search_text
from aicad.evaluation.benchmark import (
    BenchmarkExpectedOutcome,
    load_corpus,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = PROJECT_ROOT / "benchmarks" / "agent-corpus-v1.json"


def test_search_normalization_is_accent_and_case_insensitive() -> None:
    assert normalize_search_text("  SELEÇÃO: Última Peça! ") == (
        "selecao ultima peca"
    )


def test_selector_recalls_every_expected_tool_in_the_versioned_corpus() -> None:
    selector = ToolSelector(build_default_registry())
    corpus = load_corpus(CORPUS_PATH)
    tool_cases = [
        case
        for case in corpus.cases
        if case.expected_outcome is BenchmarkExpectedOutcome.TOOL_CALL
    ]

    selections = [
        selector.select(case.user_message)
        for case in tool_cases
    ]

    assert len(tool_cases) == 20
    assert all(
        set(case.expected_tools) <= set(selection.tool_names)
        for case, selection in zip(tool_cases, selections, strict=True)
    )
    assert all(len(selection.tool_names) <= 4 for selection in selections)


def test_selector_uses_canonical_order_and_keeps_context_available() -> None:
    registry = build_default_registry()
    selection = ToolSelector(registry).select(
        "Create a cylinder with diameter 20 and height 50."
    )
    orders = [registry.get_spec(name).canonical_order for name in selection.tool_names]

    assert selection.tool_names == (
        "cad.get_context_snapshot",
        "cad.create_box",
        "cad.create_cylinder",
    )
    assert orders == sorted(orders)
    assert selection.fallback_used is False


def test_selector_never_exposes_modification_tools_for_unsafe_requests() -> None:
    registry = build_default_registry()
    selector = ToolSelector(registry)
    corpus = load_corpus(CORPUS_PATH)
    unsafe_cases = [
        case
        for case in corpus.cases
        if case.expected_outcome is BenchmarkExpectedOutcome.REJECTION
    ]

    selections = [selector.select(case.user_message) for case in unsafe_cases]

    assert len(selections) == 5
    assert all(selection.safety_filtered for selection in selections)
    assert all(
        registry.get_spec(name).risk is ToolRisk.READ
        for selection in selections
        for name in selection.tool_names
    )


def test_selector_uses_selection_context_for_relative_requests() -> None:
    selection = ToolSelector(build_default_registry()).select(
        "Arredonde essas bordas.",
        context={"snapshot": {"summary": {"selected_count": 2}}},
    )

    assert "cad.get_context_snapshot" in selection.tool_names
    assert "cad.get_selection" in selection.tool_names
    assert any(
        match.name == "cad.get_selection" and "active-selection" in match.reasons
        for match in selection.matches
    )


def test_low_confidence_fallback_is_read_only() -> None:
    registry = build_default_registry()
    selection = ToolSelector(registry).select(
        "Preciso de ajuda para decidir o projeto."
    )

    assert selection.fallback_used is True
    assert all(
        registry.get_spec(name).risk is ToolRisk.READ
        for name in selection.tool_names
    )

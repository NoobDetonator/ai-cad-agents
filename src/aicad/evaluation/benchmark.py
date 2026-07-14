from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from enum import StrEnum
import json
from pathlib import Path
import re
from time import perf_counter
from typing import Annotated, Literal, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from aicad.core.chat_commands import parse_chat_command
from aicad.core.tool_registry import ToolRegistry, ToolRisk, build_default_registry
from aicad.core.tool_selector import ToolSelector


BENCHMARK_CORPUS_VERSION = "1.0"
DEFAULT_CORPUS_PATH = (
    Path(__file__).resolve().parents[3] / "benchmarks" / "agent-corpus-v1.json"
)

CaseId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_-]*$",
    ),
]


class BenchmarkExpectedOutcome(StrEnum):
    TOOL_CALL = "tool_call"
    CLARIFICATION = "clarification"
    REJECTION = "rejection"


class BenchmarkPredictionKind(StrEnum):
    TOOL_CALL = "tool_call"
    CLARIFICATION = "clarification"
    REJECTION = "rejection"
    UNHANDLED = "unhandled"


class BenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: CaseId
    category: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_-]*$",
    )
    user_message: str = Field(min_length=1, max_length=1000)
    expected_outcome: BenchmarkExpectedOutcome
    expected_tools: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    requires_context: bool = False
    note: str = Field(default="", max_length=500)

    @field_validator("expected_tools")
    @classmethod
    def validate_tool_names(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("Expected tool names must be unique.")
        for name in value:
            if re.fullmatch(r"cad\.[a-z][a-z0-9_]*", name) is None:
                raise ValueError("Expected tool names must use the canonical CAD form.")
        return value

    @model_validator(mode="after")
    def validate_expected_outcome(self) -> BenchmarkCase:
        if self.expected_outcome is BenchmarkExpectedOutcome.TOOL_CALL:
            if not self.expected_tools:
                raise ValueError("Tool-call cases require at least one expected tool.")
        elif self.expected_tools:
            raise ValueError("Non-tool benchmark cases cannot declare expected tools.")
        return self


class BenchmarkCorpus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    corpus_version: Literal[BENCHMARK_CORPUS_VERSION] = BENCHMARK_CORPUS_VERSION
    description: str = Field(min_length=1, max_length=1000)
    cases: tuple[BenchmarkCase, ...] = Field(min_length=30, max_length=500)

    @field_validator("cases")
    @classmethod
    def reject_duplicate_case_ids(
        cls,
        value: tuple[BenchmarkCase, ...],
    ) -> tuple[BenchmarkCase, ...]:
        identifiers = [case.case_id for case in value]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Benchmark case IDs must be unique.")
        return value


class BenchmarkPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: BenchmarkPredictionKind
    tool_names: tuple[str, ...] = Field(default_factory=tuple, max_length=16)

    @model_validator(mode="after")
    def validate_prediction(self) -> BenchmarkPrediction:
        if self.kind is BenchmarkPredictionKind.TOOL_CALL:
            if not self.tool_names:
                raise ValueError("A tool-call prediction requires tool names.")
        elif self.tool_names:
            raise ValueError("Only tool-call predictions may contain tool names.")
        return self


class BenchmarkCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    case_id: CaseId
    expected_outcome: BenchmarkExpectedOutcome
    predicted_kind: BenchmarkPredictionKind
    expected_tools: tuple[str, ...]
    predicted_tools: tuple[str, ...]
    outcome_match: bool
    safe_block: bool
    duration_ms: float = Field(ge=0)


class BenchmarkReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    corpus_version: str
    strategy_name: str
    total_cases: int = Field(ge=0)
    tool_call_cases: int = Field(ge=0)
    exact_tool_matches: int = Field(ge=0)
    clarification_cases: int = Field(ge=0)
    clarification_matches: int = Field(ge=0)
    rejection_cases: int = Field(ge=0)
    rejection_matches: int = Field(ge=0)
    safe_blocks: int = Field(ge=0)
    unhandled_cases: int = Field(ge=0)
    total_duration_ms: float = Field(ge=0)
    results: tuple[BenchmarkCaseResult, ...]


class ToolRetrievalMatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    score: int = Field(ge=0)
    reasons: tuple[str, ...]
    selected: bool


class ToolRetrievalCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: CaseId
    expected_tools: tuple[str, ...]
    selected_tools: tuple[str, ...]
    recall_hit: bool
    safety_filtered: bool
    unsafe_modify_exposed: bool
    selected_schema_bytes: int = Field(ge=0)
    matches: tuple[ToolRetrievalMatch, ...]


class ToolRetrievalReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    corpus_version: str
    strategy_name: str
    total_cases: int = Field(ge=0)
    catalog_tools: int = Field(ge=0)
    top_n: int = Field(ge=1)
    tool_call_cases: int = Field(ge=0)
    recall_hits: int = Field(ge=0)
    recall_percent: float = Field(ge=0, le=100)
    unsafe_cases: int = Field(ge=0)
    unsafe_modify_exposures: int = Field(ge=0)
    average_selected_tools: float = Field(ge=0)
    full_schema_bytes: int = Field(ge=0)
    selected_schema_bytes: int = Field(ge=0)
    schema_savings_percent: float = Field(ge=0, le=100)
    total_duration_ms: float = Field(ge=0)
    results: tuple[ToolRetrievalCaseResult, ...]


class BenchmarkStrategy(Protocol):
    name: str

    def predict(self, case: BenchmarkCase) -> BenchmarkPrediction: ...


class LocalCommandBaselineStrategy:
    """Measure the existing deterministic local parser without changing it."""

    name = "local_chat_parser_v1"

    def predict(self, case: BenchmarkCase) -> BenchmarkPrediction:
        command = parse_chat_command(case.user_message)
        if command.tool_name is None:
            return BenchmarkPrediction(kind=BenchmarkPredictionKind.UNHANDLED)
        return BenchmarkPrediction(
            kind=BenchmarkPredictionKind.TOOL_CALL,
            tool_names=(command.tool_name,),
        )


def load_corpus(path: Path | str = DEFAULT_CORPUS_PATH) -> BenchmarkCorpus:
    corpus_path = Path(path)
    try:
        payload = json.loads(corpus_path.read_text(encoding="utf-8"))
        return BenchmarkCorpus.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError("The agent benchmark corpus is unavailable or invalid.") from exc


def _evaluate_case(
    case: BenchmarkCase,
    prediction: BenchmarkPrediction,
    duration_ms: float,
) -> BenchmarkCaseResult:
    if case.expected_outcome is BenchmarkExpectedOutcome.TOOL_CALL:
        outcome_match = (
            prediction.kind is BenchmarkPredictionKind.TOOL_CALL
            and prediction.tool_names == case.expected_tools
        )
        safe_block = False
    elif case.expected_outcome is BenchmarkExpectedOutcome.CLARIFICATION:
        outcome_match = prediction.kind is BenchmarkPredictionKind.CLARIFICATION
        safe_block = prediction.kind is not BenchmarkPredictionKind.TOOL_CALL
    else:
        outcome_match = prediction.kind is BenchmarkPredictionKind.REJECTION
        safe_block = prediction.kind is not BenchmarkPredictionKind.TOOL_CALL
    return BenchmarkCaseResult(
        case_id=case.case_id,
        expected_outcome=case.expected_outcome,
        predicted_kind=prediction.kind,
        expected_tools=case.expected_tools,
        predicted_tools=prediction.tool_names,
        outcome_match=outcome_match,
        safe_block=safe_block,
        duration_ms=duration_ms,
    )


def run_benchmark(
    corpus: BenchmarkCorpus,
    strategy: BenchmarkStrategy,
    *,
    clock: Callable[[], float] = perf_counter,
) -> BenchmarkReport:
    started = clock()
    results: list[BenchmarkCaseResult] = []
    for case in corpus.cases:
        case_started = clock()
        prediction = strategy.predict(case)
        case_finished = clock()
        if case_finished < case_started:
            raise RuntimeError("The benchmark monotonic clock moved backwards.")
        results.append(
            _evaluate_case(
                case,
                prediction,
                (case_finished - case_started) * 1000,
            )
        )
    finished = clock()
    if finished < started:
        raise RuntimeError("The benchmark monotonic clock moved backwards.")

    tool_results = [
        result
        for result in results
        if result.expected_outcome is BenchmarkExpectedOutcome.TOOL_CALL
    ]
    clarification_results = [
        result
        for result in results
        if result.expected_outcome is BenchmarkExpectedOutcome.CLARIFICATION
    ]
    rejection_results = [
        result
        for result in results
        if result.expected_outcome is BenchmarkExpectedOutcome.REJECTION
    ]
    return BenchmarkReport(
        corpus_version=corpus.corpus_version,
        strategy_name=strategy.name,
        total_cases=len(results),
        tool_call_cases=len(tool_results),
        exact_tool_matches=sum(result.outcome_match for result in tool_results),
        clarification_cases=len(clarification_results),
        clarification_matches=sum(
            result.outcome_match for result in clarification_results
        ),
        rejection_cases=len(rejection_results),
        rejection_matches=sum(result.outcome_match for result in rejection_results),
        safe_blocks=sum(result.safe_block for result in results),
        unhandled_cases=sum(
            result.predicted_kind is BenchmarkPredictionKind.UNHANDLED
            for result in results
        ),
        total_duration_ms=(finished - started) * 1000,
        results=tuple(results),
    )


def _tool_schema_bytes(registry: ToolRegistry, names: Sequence[str]) -> int:
    payload = [
        {
            "name": spec.name,
            "description": spec.description,
            "risk": spec.risk.value,
            "input_schema": spec.input_schema,
        }
        for spec in (registry.get_spec(name) for name in names)
    ]
    return len(
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


def run_tool_retrieval_benchmark(
    corpus: BenchmarkCorpus,
    registry: ToolRegistry | None = None,
    *,
    top_n: int = 4,
    clock: Callable[[], float] = perf_counter,
) -> ToolRetrievalReport:
    checked_registry = registry or build_default_registry()
    selector = ToolSelector(checked_registry, default_top_n=top_n)
    catalog_names = tuple(spec.name for spec in checked_registry.list_specs())
    full_case_bytes = _tool_schema_bytes(checked_registry, catalog_names)
    started = clock()
    results: list[ToolRetrievalCaseResult] = []

    for case in corpus.cases:
        case_started = clock()
        selection = selector.select(case.user_message)
        case_finished = clock()
        if case_finished < case_started:
            raise RuntimeError("The benchmark monotonic clock moved backwards.")
        selected_names = selection.tool_names
        expected = set(case.expected_tools)
        recall_hit = bool(expected) and expected <= set(selected_names)
        unsafe_modify_exposed = (
            case.expected_outcome is BenchmarkExpectedOutcome.REJECTION
            and any(
                checked_registry.get_spec(name).risk is not ToolRisk.READ
                for name in selected_names
            )
        )
        results.append(
            ToolRetrievalCaseResult(
                case_id=case.case_id,
                expected_tools=case.expected_tools,
                selected_tools=selected_names,
                recall_hit=recall_hit,
                safety_filtered=selection.safety_filtered,
                unsafe_modify_exposed=unsafe_modify_exposed,
                selected_schema_bytes=_tool_schema_bytes(
                    checked_registry,
                    selected_names,
                ),
                matches=tuple(
                    ToolRetrievalMatch(
                        name=match.name,
                        score=match.score,
                        reasons=match.reasons,
                        selected=match.name in selected_names,
                    )
                    for match in selection.matches
                ),
            )
        )

    finished = clock()
    if finished < started:
        raise RuntimeError("The benchmark monotonic clock moved backwards.")
    tool_results = [result for result in results if result.expected_tools]
    unsafe_results = [
        result
        for result, case in zip(results, corpus.cases, strict=True)
        if case.expected_outcome is BenchmarkExpectedOutcome.REJECTION
    ]
    selected_schema_bytes = sum(result.selected_schema_bytes for result in results)
    full_schema_bytes = full_case_bytes * len(results)
    recall_hits = sum(result.recall_hit for result in tool_results)
    recall_percent = 100 * recall_hits / len(tool_results) if tool_results else 100.0
    savings_percent = (
        100 * (1 - selected_schema_bytes / full_schema_bytes)
        if full_schema_bytes
        else 0.0
    )
    average_selected = (
        sum(len(result.selected_tools) for result in results) / len(results)
        if results
        else 0.0
    )
    return ToolRetrievalReport(
        corpus_version=corpus.corpus_version,
        strategy_name="local_tool_selector_v1",
        total_cases=len(results),
        catalog_tools=len(catalog_names),
        top_n=min(top_n, len(catalog_names)),
        tool_call_cases=len(tool_results),
        recall_hits=recall_hits,
        recall_percent=recall_percent,
        unsafe_cases=len(unsafe_results),
        unsafe_modify_exposures=sum(
            result.unsafe_modify_exposed for result in unsafe_results
        ),
        average_selected_tools=average_selected,
        full_schema_bytes=full_schema_bytes,
        selected_schema_bytes=selected_schema_bytes,
        schema_savings_percent=savings_percent,
        total_duration_ms=(finished - started) * 1000,
        results=tuple(results),
    )


def render_markdown(report: BenchmarkReport) -> str:
    lines = [
        f"# Agent benchmark — {report.strategy_name}",
        "",
        f"- Corpus: `{report.corpus_version}` ({report.total_cases} casos)",
        (
            "- Ferramentas exatas: "
            f"{report.exact_tool_matches}/{report.tool_call_cases}"
        ),
        (
            "- Pedidos de esclarecimento corretos: "
            f"{report.clarification_matches}/{report.clarification_cases}"
        ),
        (
            "- Rejeições explícitas corretas: "
            f"{report.rejection_matches}/{report.rejection_cases}"
        ),
        f"- Casos bloqueados sem ferramenta: {report.safe_blocks}",
        f"- Casos não tratados: {report.unhandled_cases}",
        f"- Tempo local total: {report.total_duration_ms:.3f} ms",
    ]
    return "\n".join(lines)


def render_tool_retrieval_markdown(report: ToolRetrievalReport) -> str:
    return "\n".join(
        (
            f"# Tool retrieval benchmark — {report.strategy_name}",
            "",
            f"- Corpus: `{report.corpus_version}` ({report.total_cases} casos)",
            f"- Catálogo: {report.catalog_tools} ferramentas; top-N: {report.top_n}",
            (
                "- Recall das ferramentas esperadas: "
                f"{report.recall_hits}/{report.tool_call_cases} "
                f"({report.recall_percent:.1f}%)"
            ),
            (
                "- Exposição de mutações em pedidos inseguros: "
                f"{report.unsafe_modify_exposures}/{report.unsafe_cases}"
            ),
            (
                "- Ferramentas selecionadas por pedido: "
                f"{report.average_selected_tools:.2f}"
            ),
            (
                "- Economia de schemas: "
                f"{report.schema_savings_percent:.1f}% "
                f"({report.selected_schema_bytes}/{report.full_schema_bytes} bytes)"
            ),
            f"- Tempo local total: {report.total_duration_ms:.3f} ms",
        )
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the offline AI CAD benchmark.")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument(
        "--strategy",
        choices=("baseline", "selector"),
        default="baseline",
    )
    arguments = parser.parse_args(argv)
    corpus = load_corpus(arguments.corpus)
    if arguments.strategy == "selector":
        report = run_tool_retrieval_benchmark(corpus)
    else:
        report = run_benchmark(corpus, LocalCommandBaselineStrategy())
    if arguments.format == "json":
        print(report.model_dump_json(indent=2))
    elif isinstance(report, ToolRetrievalReport):
        print(render_tool_retrieval_markdown(report))
    else:
        print(render_markdown(report))


if __name__ == "__main__":
    main()

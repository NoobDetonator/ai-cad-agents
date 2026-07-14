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


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the offline AI CAD benchmark.")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    arguments = parser.parse_args(argv)
    report = run_benchmark(load_corpus(arguments.corpus), LocalCommandBaselineStrategy())
    if arguments.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(render_markdown(report))


if __name__ == "__main__":
    main()

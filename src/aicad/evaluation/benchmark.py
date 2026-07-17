from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from enum import StrEnum
import json
from pathlib import Path
import re
from time import perf_counter
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from aicad.core.tool_registry import ToolRegistry, ToolRisk, build_default_registry
from aicad.core.tool_selector import ToolSelector


BENCHMARK_CORPUS_VERSION = "1.0"
SUPPORTED_CORPUS_VERSIONS = frozenset({"1.0", "1.1"})
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
    candidate_tools: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    requires_context: bool = False
    note: str = Field(default="", max_length=500)

    @field_validator("expected_tools", "candidate_tools")
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
            if self.candidate_tools:
                raise ValueError("Tool-call cases cannot declare candidate tools.")
        elif self.expected_outcome is BenchmarkExpectedOutcome.CLARIFICATION:
            if self.expected_tools:
                raise ValueError(
                    "Clarification cases use candidate_tools, not expected_tools."
                )
        elif self.expected_tools or self.candidate_tools:
            raise ValueError("Rejection cases cannot declare CAD tools.")
        return self


class BenchmarkCorpus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    corpus_version: str = Field(
        default=BENCHMARK_CORPUS_VERSION,
        pattern=r"^1\.[01]$",
    )
    description: str = Field(min_length=1, max_length=1000)
    cases: tuple[BenchmarkCase, ...] = Field(min_length=1, max_length=500)

    @field_validator("corpus_version")
    @classmethod
    def accept_supported_version(cls, value: str) -> str:
        if value not in SUPPORTED_CORPUS_VERSIONS:
            raise ValueError("The benchmark corpus version is unsupported.")
        return value

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


class ToolRetrievalMatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    score: int = Field(ge=0)
    reasons: tuple[str, ...]
    selected: bool


class ToolRetrievalCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    case_id: CaseId
    expected_outcome: BenchmarkExpectedOutcome
    expected_tools: tuple[str, ...]
    candidate_tools: tuple[str, ...]
    relevant_tools: tuple[str, ...]
    selected_tools: tuple[str, ...]
    ranked_selected_tools: tuple[str, ...]
    recall_hit: bool
    rank_one_hit: bool
    first_relevant_rank: int | None = Field(default=None, ge=1)
    precision_at_k: float = Field(ge=0, le=1)
    reciprocal_rank: float = Field(ge=0, le=1)
    clarification_retrieval_hit: bool
    clarification_fallback: bool
    safety_filtered: bool
    unsafe_modify_exposed: bool
    false_positive_mutation_exposed: bool
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
    retrieval_cases: int = Field(ge=0)
    rank_one_hits: int = Field(ge=0)
    rank_one_percent: float = Field(ge=0, le=100)
    precision_at_k_percent: float = Field(ge=0, le=100)
    mean_reciprocal_rank: float = Field(ge=0, le=1)
    clarification_cases: int = Field(ge=0)
    clarification_retrieval_hits: int = Field(ge=0)
    clarification_retrieval_percent: float = Field(ge=0, le=100)
    clarification_fallbacks: int = Field(ge=0)
    unsafe_cases: int = Field(ge=0)
    unsafe_modify_exposures: int = Field(ge=0)
    rejection_filter_hits: int = Field(ge=0)
    rejection_filter_percent: float = Field(ge=0, le=100)
    false_positive_mutation_cases: int = Field(ge=0)
    false_positive_mutation_exposures: int = Field(ge=0)
    average_selected_tools: float = Field(ge=0)
    full_schema_bytes: int = Field(ge=0)
    selected_schema_bytes: int = Field(ge=0)
    schema_savings_percent: float = Field(ge=0, le=100)
    total_duration_ms: float = Field(ge=0)
    results: tuple[ToolRetrievalCaseResult, ...]

def load_corpus(path: Path | str = DEFAULT_CORPUS_PATH) -> BenchmarkCorpus:
    corpus_path = Path(path)
    try:
        payload = json.loads(corpus_path.read_text(encoding="utf-8"))
        return BenchmarkCorpus.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError("The agent benchmark corpus is unavailable or invalid.") from exc


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
        selected_set = set(selected_names)
        expected = set(case.expected_tools)
        candidates = set(case.candidate_tools)
        relevant = expected or candidates
        recall_hit = bool(expected) and expected <= selected_set
        ranked_selected = tuple(
            match.name for match in selection.matches if match.name in selected_set
        )
        relevant_ranks = [
            index
            for index, name in enumerate(ranked_selected, start=1)
            if name in relevant
        ]
        first_relevant_rank = min(relevant_ranks, default=None)
        relevant_selected = len(relevant & selected_set)
        precision_at_k = (
            relevant_selected / len(selected_names) if selected_names else 0.0
        )
        reciprocal_rank = (
            1 / first_relevant_rank if first_relevant_rank is not None else 0.0
        )
        clarification_hit = (
            case.expected_outcome is BenchmarkExpectedOutcome.CLARIFICATION
            and bool(candidates & selected_set)
        )
        unsafe_modify_exposed = (
            case.expected_outcome is BenchmarkExpectedOutcome.REJECTION
            and any(
                checked_registry.get_spec(name).risk is not ToolRisk.READ
                for name in selected_names
            )
        )
        unexpected_mutations = [
            name
            for name in selected_names
            if checked_registry.get_spec(name).risk is not ToolRisk.READ
            and name not in relevant
        ]
        false_positive_mutation_exposed = (
            case.expected_outcome is not BenchmarkExpectedOutcome.TOOL_CALL
            and bool(unexpected_mutations)
        )
        results.append(
            ToolRetrievalCaseResult(
                case_id=case.case_id,
                expected_outcome=case.expected_outcome,
                expected_tools=case.expected_tools,
                candidate_tools=case.candidate_tools,
                relevant_tools=tuple(sorted(relevant)),
                selected_tools=selected_names,
                ranked_selected_tools=ranked_selected,
                recall_hit=recall_hit,
                rank_one_hit=first_relevant_rank == 1,
                first_relevant_rank=first_relevant_rank,
                precision_at_k=precision_at_k,
                reciprocal_rank=reciprocal_rank,
                clarification_retrieval_hit=clarification_hit,
                clarification_fallback=(
                    case.expected_outcome is BenchmarkExpectedOutcome.CLARIFICATION
                    and selection.fallback_used
                ),
                safety_filtered=selection.safety_filtered,
                unsafe_modify_exposed=unsafe_modify_exposed,
                false_positive_mutation_exposed=false_positive_mutation_exposed,
                selected_schema_bytes=_tool_schema_bytes(
                    checked_registry,
                    selected_names,
                ),
                matches=tuple(
                    ToolRetrievalMatch(
                        name=match.name,
                        score=match.score,
                        reasons=match.reasons,
                        selected=match.name in selected_set,
                    )
                    for match in selection.matches
                ),
            )
        )

    finished = clock()
    if finished < started:
        raise RuntimeError("The benchmark monotonic clock moved backwards.")
    tool_results = [result for result in results if result.expected_tools]
    retrieval_results = [result for result in results if result.relevant_tools]
    clarification_results = [
        result
        for result in results
        if result.expected_outcome is BenchmarkExpectedOutcome.CLARIFICATION
    ]
    unsafe_results = [
        result
        for result in results
        if result.expected_outcome is BenchmarkExpectedOutcome.REJECTION
    ]
    false_positive_results = [
        result
        for result in results
        if result.expected_outcome is not BenchmarkExpectedOutcome.TOOL_CALL
    ]
    selected_schema_bytes = sum(result.selected_schema_bytes for result in results)
    full_schema_bytes = full_case_bytes * len(results)
    recall_hits = sum(result.recall_hit for result in tool_results)
    recall_percent = 100 * recall_hits / len(tool_results) if tool_results else 100.0
    rank_one_hits = sum(result.rank_one_hit for result in retrieval_results)
    rank_one_percent = (
        100 * rank_one_hits / len(retrieval_results) if retrieval_results else 100.0
    )
    precision_at_k_percent = (
        100
        * sum(result.precision_at_k for result in retrieval_results)
        / len(retrieval_results)
        if retrieval_results
        else 100.0
    )
    mean_reciprocal_rank = (
        sum(result.reciprocal_rank for result in retrieval_results)
        / len(retrieval_results)
        if retrieval_results
        else 1.0
    )
    clarification_retrieval_hits = sum(
        result.clarification_retrieval_hit for result in clarification_results
    )
    clarification_retrieval_percent = (
        100 * clarification_retrieval_hits / len(clarification_results)
        if clarification_results
        else 100.0
    )
    rejection_filter_hits = sum(result.safety_filtered for result in unsafe_results)
    rejection_filter_percent = (
        100 * rejection_filter_hits / len(unsafe_results)
        if unsafe_results
        else 100.0
    )
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
        retrieval_cases=len(retrieval_results),
        rank_one_hits=rank_one_hits,
        rank_one_percent=rank_one_percent,
        precision_at_k_percent=precision_at_k_percent,
        mean_reciprocal_rank=mean_reciprocal_rank,
        clarification_cases=len(clarification_results),
        clarification_retrieval_hits=clarification_retrieval_hits,
        clarification_retrieval_percent=clarification_retrieval_percent,
        clarification_fallbacks=sum(
            result.clarification_fallback for result in clarification_results
        ),
        unsafe_cases=len(unsafe_results),
        unsafe_modify_exposures=sum(
            result.unsafe_modify_exposed for result in unsafe_results
        ),
        rejection_filter_hits=rejection_filter_hits,
        rejection_filter_percent=rejection_filter_percent,
        false_positive_mutation_cases=len(false_positive_results),
        false_positive_mutation_exposures=sum(
            result.false_positive_mutation_exposed
            for result in false_positive_results
        ),
        average_selected_tools=average_selected,
        full_schema_bytes=full_schema_bytes,
        selected_schema_bytes=selected_schema_bytes,
        schema_savings_percent=savings_percent,
        total_duration_ms=(finished - started) * 1000,
        results=tuple(results),
    )

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
                "- Rank-1 / MRR / precisão@K: "
                f"{report.rank_one_percent:.1f}% / "
                f"{report.mean_reciprocal_rank:.3f} / "
                f"{report.precision_at_k_percent:.1f}%"
            ),
            (
                "- Cobertura de esclarecimentos: "
                f"{report.clarification_retrieval_hits}/"
                f"{report.clarification_cases} "
                f"({report.clarification_retrieval_percent:.1f}%); "
                f"fallbacks: {report.clarification_fallbacks}"
            ),
            (
                "- Filtros de rejeição e exposição insegura: "
                f"{report.rejection_filter_hits}/{report.unsafe_cases}; "
                f"{report.unsafe_modify_exposures} mutações"
            ),
            (
                "- Falsos positivos de mutação em casos sem execução: "
                f"{report.false_positive_mutation_exposures}/"
                f"{report.false_positive_mutation_cases}"
            ),
            (
                "- Ferramentas selecionadas por pedido: "
                f"{report.average_selected_tools:.2f}"
            ),
            (
                "- Economia teórica de schemas sem cache: "
                f"{report.schema_savings_percent:.1f}% "
                f"({report.selected_schema_bytes}/{report.full_schema_bytes} bytes)"
            ),
            f"- Tempo local total: {report.total_duration_ms:.3f} ms",
        )
    )

def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run the offline TALOS tool-retrieval benchmark."
    )
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    arguments = parser.parse_args(argv)
    corpus = load_corpus(arguments.corpus)
    report = run_tool_retrieval_benchmark(corpus)
    if arguments.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(render_tool_retrieval_markdown(report))


if __name__ == "__main__":
    main()

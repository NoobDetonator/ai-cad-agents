from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import re
import unicodedata
from typing import Any

from aicad.core.tool_registry import ToolRegistry, ToolRisk, ToolSpec


DEFAULT_TOOL_TOP_N = 4
MINIMUM_CONFIDENT_SCORE = 8

_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "as",
        "at",
        "com",
        "da",
        "das",
        "de",
        "do",
        "dos",
        "e",
        "em",
        "for",
        "i",
        "in",
        "me",
        "my",
        "o",
        "of",
        "os",
        "para",
        "por",
        "the",
        "to",
        "um",
        "uma",
        "with",
    }
)

_UNSAFE_PHRASES = (
    "execute python",
    "executar python",
    "os system",
    "prompt de comando",
    "command prompt",
    "apague todos os arquivos",
    "delete all files",
    "ignore a confirmacao",
    "ignore confirmation",
    "bypass confirmation",
    "macro arbitraria",
    "arbitrary macro",
)

_RELATIVE_TERMS = frozenset(
    {
        "aquelas",
        "aqueles",
        "essas",
        "esses",
        "isso",
        "last",
        "recent",
        "selecionado",
        "selecionados",
        "selected",
        "ultima",
        "ultimo",
    }
)


@dataclass(frozen=True, slots=True)
class ToolMatch:
    name: str
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ToolSelection:
    tool_names: tuple[str, ...]
    matches: tuple[ToolMatch, ...]
    catalog_size: int
    top_n: int
    safety_filtered: bool
    fallback_used: bool


def normalize_search_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(re.findall(r"[a-z0-9]+", without_accents))


def _tokens(value: str) -> frozenset[str]:
    return frozenset(
        token
        for token in normalize_search_text(value).split()
        if token not in _STOP_WORDS
    )


def _contains_phrase(normalized_text: str, normalized_phrase: str) -> bool:
    return f" {normalized_phrase} " in f" {normalized_text} "


def _selected_count(context: Mapping[str, Any] | None) -> int:
    if context is None:
        return 0
    snapshot = context.get("snapshot", context)
    if not isinstance(snapshot, Mapping):
        return 0
    summary = snapshot.get("summary")
    if not isinstance(summary, Mapping):
        return 0
    value = summary.get("selected_count", 0)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


class ToolSelector:
    """Select a small, stable tool subset without another model request."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        default_top_n: int = DEFAULT_TOOL_TOP_N,
    ) -> None:
        if (
            isinstance(default_top_n, bool)
            or not isinstance(default_top_n, int)
            or default_top_n < 1
        ):
            raise ValueError("The tool selection limit must be a positive integer.")
        self._registry = registry
        self._default_top_n = default_top_n

    def select(
        self,
        user_message: str,
        *,
        context: Mapping[str, Any] | None = None,
        top_n: int | None = None,
    ) -> ToolSelection:
        if not isinstance(user_message, str) or not user_message.strip():
            raise ValueError("A non-empty user message is required for tool selection.")
        limit = self._default_top_n if top_n is None else top_n
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("The tool selection limit must be a positive integer.")

        specs = self._registry.list_specs()
        if not specs:
            return ToolSelection((), (), 0, limit, False, True)
        limit = min(limit, len(specs))
        normalized_message = normalize_search_text(user_message)
        query_tokens = _tokens(user_message)
        safety_filtered = any(
            _contains_phrase(normalized_message, phrase)
            for phrase in _UNSAFE_PHRASES
        )
        eligible = tuple(
            spec
            for spec in specs
            if not safety_filtered or spec.risk is ToolRisk.READ
        )
        matches = tuple(
            sorted(
                (
                    self._score_spec(
                        spec,
                        normalized_message,
                        query_tokens,
                        context,
                    )
                    for spec in eligible
                ),
                key=lambda match: (
                    -match.score,
                    self._registry.get_spec(match.name).canonical_order,
                    match.name,
                ),
            )
        )

        essential = sorted(
            (spec for spec in eligible if spec.essential),
            key=lambda spec: (spec.canonical_order, spec.name),
        )
        confident = bool(matches and matches[0].score >= MINIMUM_CONFIDENT_SCORE)
        fallback_used = safety_filtered or not confident
        chosen: dict[str, ToolSpec] = {}
        self._fill(chosen, essential, limit)
        if query_tokens & _RELATIVE_TERMS:
            selection_spec = next(
                (spec for spec in eligible if spec.name == "cad.get_selection"),
                None,
            )
            if selection_spec is not None:
                self._fill(chosen, (selection_spec,), limit)

        if fallback_used:
            fallback = (
                spec
                for spec in eligible
                if spec.risk is ToolRisk.READ
                and spec.family in {"context", "validation"}
            )
            self._fill(chosen, fallback, limit)
        else:
            minimum_ranked_score = max(
                MINIMUM_CONFIDENT_SCORE,
                matches[0].score // 4,
            )
            ranked = (
                self._registry.get_spec(match.name)
                for match in matches
                if match.score >= minimum_ranked_score
            )
            self._fill(chosen, ranked, limit)

        ordered = tuple(
            spec.name
            for spec in sorted(
                chosen.values(),
                key=lambda spec: (spec.canonical_order, spec.name),
            )
        )
        return ToolSelection(
            tool_names=ordered,
            matches=matches,
            catalog_size=len(specs),
            top_n=limit,
            safety_filtered=safety_filtered,
            fallback_used=fallback_used,
        )

    @staticmethod
    def _fill(
        chosen: dict[str, ToolSpec],
        candidates: Iterable[ToolSpec],
        limit: int,
    ) -> None:
        for spec in candidates:
            if len(chosen) >= limit:
                break
            chosen.setdefault(spec.name, spec)

    @staticmethod
    def _score_spec(
        spec: ToolSpec,
        normalized_message: str,
        query_tokens: frozenset[str],
        context: Mapping[str, Any] | None,
    ) -> ToolMatch:
        score = 0
        reasons: list[str] = []

        operation_tokens = _tokens(spec.name.removeprefix("cad.").replace("_", " "))
        name_hits = query_tokens & operation_tokens
        if name_hits:
            score += 6 * len(name_hits)
            reasons.append("name:" + ",".join(sorted(name_hits)))

        alias_score = 0
        alias_reason = ""
        for alias in spec.aliases:
            normalized_alias = normalize_search_text(alias)
            if not normalized_alias:
                continue
            if normalized_message == normalized_alias:
                candidate_score = 24
            elif _contains_phrase(normalized_message, normalized_alias):
                candidate_score = 18
            else:
                alias_tokens = _tokens(alias)
                overlap = query_tokens & alias_tokens
                candidate_score = 6 * len(overlap) if overlap else 0
            if candidate_score > alias_score:
                alias_score = candidate_score
                alias_reason = normalized_alias
        if alias_score:
            score += alias_score
            reasons.append("alias:" + alias_reason)

        tag_hits = query_tokens & _tokens(" ".join(spec.tags))
        if tag_hits:
            score += 4 * len(tag_hits)
            reasons.append("tags:" + ",".join(sorted(tag_hits)))

        family = normalize_search_text(spec.family)
        if family and family in query_tokens:
            score += 5
            reasons.append("family:" + family)

        description_hits = query_tokens & _tokens(spec.description)
        if description_hits:
            score += min(3, len(description_hits))
            reasons.append("description")

        best_example_hits: frozenset[str] = frozenset()
        for example in spec.examples:
            hits = query_tokens & _tokens(example)
            if len(hits) > len(best_example_hits):
                best_example_hits = hits
        if best_example_hits:
            score += min(6, 2 * len(best_example_hits))
            reasons.append("example")

        relative_hits = query_tokens & _RELATIVE_TERMS
        if relative_hits and spec.name == "cad.get_context_snapshot":
            score += 8
            reasons.append("relative-context")
        if (
            relative_hits
            and _selected_count(context) > 0
            and spec.name == "cad.get_selection"
        ):
            score += 5
            reasons.append("active-selection")

        return ToolMatch(spec.name, score, tuple(reasons))

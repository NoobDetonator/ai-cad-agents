from __future__ import annotations

import re
from typing import Any

from typing_extensions import TypedDict

from aicad.core.tool_registry import ToolRegistry, ToolRisk, ToolSpec
from aicad.core.tool_selector import ToolMatch, ToolSelector


DEFAULT_CAPABILITY_LIMIT = 8
MAX_CAPABILITY_LIMIT = 20
MAX_CAPABILITY_DESCRIPTIONS = 16
MAX_CAPABILITY_SUMMARY_LENGTH = 180
MAX_CARD_ALIASES = 4


class CapabilityCard(TypedDict):
    name: str
    family: str
    risk: str
    summary: str
    aliases: list[str]
    score: int
    reasons: list[str]
    essential: bool


class CapabilityFilters(TypedDict):
    families: list[str]
    risks: list[str]


class CapabilitySearchResult(TypedDict):
    query: str
    catalog_size: int
    matched: int
    returned: int
    cursor: int
    next_cursor: int | None
    safety_filtered: bool
    fallback_used: bool
    filters: CapabilityFilters
    family_counts: dict[str, int]
    capabilities: list[CapabilityCard]


class CapabilityDescription(TypedDict):
    name: str
    description: str
    risk: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None
    family: str
    aliases: list[str]
    tags: list[str]
    examples: list[str]
    essential: bool
    canonical_order: int


class CapabilityDescriptions(TypedDict):
    count: int
    capabilities: list[CapabilityDescription]


def _compact_summary(description: str) -> str:
    normalized = " ".join(description.split())
    sentence = re.split(r"(?<=[.!?])\s+", normalized, maxsplit=1)[0]
    if len(sentence) <= MAX_CAPABILITY_SUMMARY_LENGTH:
        return sentence
    clipped = sentence[: MAX_CAPABILITY_SUMMARY_LENGTH - 1].rsplit(" ", 1)[0]
    return (clipped or sentence[: MAX_CAPABILITY_SUMMARY_LENGTH - 1]) + "…"


def _validate_page(limit: int, cursor: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("Capability search limit must be an integer.")
    if not 1 <= limit <= MAX_CAPABILITY_LIMIT:
        raise ValueError(
            f"Capability search limit must be between 1 and {MAX_CAPABILITY_LIMIT}."
        )
    if isinstance(cursor, bool) or not isinstance(cursor, int) or cursor < 0:
        raise ValueError("Capability search cursor must be a non-negative integer.")


def _validate_filters(
    specs: tuple[ToolSpec, ...],
    families: list[str] | None,
    risks: list[str] | None,
) -> tuple[frozenset[str] | None, frozenset[ToolRisk] | None]:
    known_families = {spec.family for spec in specs}
    checked_families: frozenset[str] | None = None
    if families is not None:
        if not families or any(not isinstance(item, str) or not item for item in families):
            raise ValueError("Capability families must be a non-empty string list.")
        if len(families) != len(set(families)):
            raise ValueError("Capability family filters must be unique.")
        unknown = sorted(set(families) - known_families)
        if unknown:
            raise ValueError("Unknown capability families: " + ", ".join(unknown))
        checked_families = frozenset(families)

    checked_risks: frozenset[ToolRisk] | None = None
    if risks is not None:
        if not risks or any(not isinstance(item, str) or not item for item in risks):
            raise ValueError("Capability risks must be a non-empty string list.")
        if len(risks) != len(set(risks)):
            raise ValueError("Capability risk filters must be unique.")
        try:
            checked_risks = frozenset(ToolRisk(item) for item in risks)
        except ValueError as exc:
            allowed = ", ".join(risk.value for risk in ToolRisk)
            raise ValueError(f"Capability risks must be one of: {allowed}.") from exc
    return checked_families, checked_risks


class CapabilityCatalog:
    """Compact, paginated discovery over the shared CAD tool registry."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry
        self._selector = ToolSelector(registry)

    def search(
        self,
        query: str = "",
        *,
        families: list[str] | None = None,
        risks: list[str] | None = None,
        limit: int = DEFAULT_CAPABILITY_LIMIT,
        cursor: int = 0,
    ) -> CapabilitySearchResult:
        if not isinstance(query, str):
            raise ValueError("Capability search query must be a string.")
        _validate_page(limit, cursor)
        specs = self._registry.list_specs()
        checked_families, checked_risks = _validate_filters(
            specs, families, risks
        )

        matches_by_name: dict[str, ToolMatch] = {}
        safety_filtered = False
        fallback_used = False
        if query.strip():
            selection = self._selector.select(query, top_n=max(1, len(specs)))
            matches_by_name = {match.name: match for match in selection.matches}
            selected_names = set(selection.tool_names)
            candidates = [
                spec
                for spec in specs
                if spec.name in selected_names
            ]
            candidates.sort(
                key=lambda spec: (
                    -matches_by_name[spec.name].score,
                    spec.canonical_order,
                    spec.name,
                )
            )
            safety_filtered = selection.safety_filtered
            fallback_used = selection.fallback_used
        else:
            candidates = sorted(
                specs,
                key=lambda spec: (spec.canonical_order, spec.name),
            )

        filtered = [
            spec
            for spec in candidates
            if (checked_families is None or spec.family in checked_families)
            and (checked_risks is None or spec.risk in checked_risks)
        ]
        page = filtered[cursor : cursor + limit]
        next_cursor = cursor + len(page)
        if next_cursor >= len(filtered):
            next_cursor = None

        cards: list[CapabilityCard] = []
        for spec in page:
            match = matches_by_name.get(spec.name)
            cards.append(
                {
                    "name": spec.name,
                    "family": spec.family,
                    "risk": spec.risk.value,
                    "summary": _compact_summary(spec.description),
                    "aliases": list(spec.aliases[:MAX_CARD_ALIASES]),
                    "score": match.score if match is not None else 0,
                    "reasons": list(match.reasons) if match is not None else [],
                    "essential": spec.essential,
                }
            )

        family_counts: dict[str, int] = {}
        for spec in specs:
            family_counts[spec.family] = family_counts.get(spec.family, 0) + 1

        return {
            "query": query.strip(),
            "catalog_size": len(specs),
            "matched": len(filtered),
            "returned": len(cards),
            "cursor": cursor,
            "next_cursor": next_cursor,
            "safety_filtered": safety_filtered,
            "fallback_used": fallback_used,
            "filters": {
                "families": sorted(checked_families) if checked_families else [],
                "risks": sorted(risk.value for risk in checked_risks)
                if checked_risks
                else [],
            },
            "family_counts": dict(sorted(family_counts.items())),
            "capabilities": cards,
        }

    def describe(self, names: list[str]) -> CapabilityDescriptions:
        if not isinstance(names, list) or not names:
            raise ValueError("At least one capability name is required.")
        if len(names) > MAX_CAPABILITY_DESCRIPTIONS:
            raise ValueError(
                "At most "
                f"{MAX_CAPABILITY_DESCRIPTIONS} capabilities can be described at once."
            )
        if any(not isinstance(name, str) or not name for name in names):
            raise ValueError("Capability names must be non-empty strings.")
        if len(names) != len(set(names)):
            raise ValueError("Capability names must be unique.")

        unknown = []
        specs = []
        for name in names:
            try:
                specs.append(self._registry.get_spec(name))
            except KeyError:
                unknown.append(name)
        if unknown:
            raise ValueError("Unknown CAD capabilities: " + ", ".join(unknown))

        capabilities: list[CapabilityDescription] = []
        for spec in specs:
            capabilities.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "risk": spec.risk.value,
                    "input_schema": spec.input_schema,
                    "output_schema": spec.output_schema,
                    "family": spec.family,
                    "aliases": list(spec.aliases),
                    "tags": list(spec.tags),
                    "examples": list(spec.examples),
                    "essential": spec.essential,
                    "canonical_order": spec.canonical_order,
                }
            )
        return {
            "count": len(capabilities),
            "capabilities": capabilities,
        }

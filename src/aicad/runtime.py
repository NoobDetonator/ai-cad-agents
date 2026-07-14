from __future__ import annotations

from functools import lru_cache

from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.application import build_cad_tool_registry
from aicad.core.tool_registry import ToolRegistry
from aicad.orchestration.plan_service import PlanService


@lru_cache(maxsize=1)
def get_tool_registry() -> ToolRegistry:
    """Return the shared registry used by UI and MCP inside this process."""

    return build_cad_tool_registry(FreeCadAdapter())


@lru_cache(maxsize=1)
def get_plan_service() -> PlanService:
    """Return the authoritative in-process service shared by chat and GUI bridge."""

    return PlanService()

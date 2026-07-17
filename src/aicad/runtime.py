from __future__ import annotations

from functools import lru_cache

from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.application import build_cad_tool_registry
from aicad.audit import AuditService, default_audit_store
from aicad.core.tool_registry import ToolRegistry
from aicad.orchestration.plan_service import PlanService


@lru_cache(maxsize=1)
def get_audit_service() -> AuditService:
    """Return the persistent audit service for this process session."""

    return AuditService(default_audit_store())


@lru_cache(maxsize=1)
def get_tool_registry() -> ToolRegistry:
    """Return the shared registry used by UI and MCP inside this process."""

    registry = build_cad_tool_registry(FreeCadAdapter())
    audit = get_audit_service()
    registry.bind("cad.get_audit_history", audit.get_history)
    registry.bind("cad.export_audit_history", audit.export_history)
    return registry


@lru_cache(maxsize=1)
def get_plan_service() -> PlanService:
    """Return the authoritative in-process plan service shared with the GUI bridge."""

    return PlanService(
        audit_service=get_audit_service(),
        registry=get_tool_registry(),
    )

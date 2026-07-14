"""Provider- and CAD-independent domain logic."""

from aicad.core.context import (
    ContextDetailLevel,
    ContextSnapshot,
    ContextStateTracker,
    DocumentStateToken,
)
from aicad.core.tool_results import (
    AffectedObjects,
    ToolError,
    ToolErrorCode,
    ToolResultEnvelope,
    ToolResultStatus,
    ToolValidation,
)


__all__ = [
    "AffectedObjects",
    "ContextDetailLevel",
    "ContextSnapshot",
    "ContextStateTracker",
    "DocumentStateToken",
    "ToolError",
    "ToolErrorCode",
    "ToolResultEnvelope",
    "ToolResultStatus",
    "ToolValidation",
]

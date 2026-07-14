from __future__ import annotations

import pytest
from pydantic import ValidationError

from aicad.core.tool_results import (
    AffectedObjects,
    ToolError,
    ToolErrorCode,
    ToolResultEnvelope,
    ToolResultStatus,
    ToolValidation,
)


def test_completed_tool_result_is_versioned_and_json_safe() -> None:
    envelope = ToolResultEnvelope(
        tool_name="cad.create_box",
        status=ToolResultStatus.COMPLETED,
        summary="Caixa criada e validada.",
        result={"name": "Box", "valid": True},
        affected_objects=AffectedObjects(created=("Box",)),
        validations=(
            ToolValidation(name="shape.valid", passed=True),
        ),
        duration_ms=12.5,
    )

    payload = envelope.model_dump(mode="json")

    assert payload["contract_version"] == "1.0"
    assert payload["affected_objects"]["created"] == ["Box"]
    assert payload["error"] is None


@pytest.mark.parametrize(
    ("status", "error", "result"),
    [
        (ToolResultStatus.COMPLETED, ToolError(code="internal_error", message="x"), None),
        (ToolResultStatus.FAILED, None, None),
        (
            ToolResultStatus.FAILED,
            ToolError(code="execution_failed", message="Falhou."),
            {"partial": True},
        ),
        (
            ToolResultStatus.CANCELLED,
            ToolError(code="execution_failed", message="Cancelado."),
            None,
        ),
    ],
)
def test_tool_result_enforces_status_invariants(
    status: ToolResultStatus,
    error: ToolError | None,
    result: object,
) -> None:
    with pytest.raises(ValidationError):
        ToolResultEnvelope(
            tool_name="cad.create_box",
            status=status,
            summary="Resultado controlado.",
            result=result,
            error=error,
            duration_ms=1,
        )


def test_tool_result_rejects_sensitive_metadata_and_non_finite_values() -> None:
    with pytest.raises(ValidationError):
        ToolError(
            code=ToolErrorCode.INTERNAL_ERROR,
            message="Erro controlado.",
            details={"api_key": "must-not-be-here"},
        )

    with pytest.raises(ValidationError):
        ToolResultEnvelope(
            tool_name="cad.get_document_summary",
            status=ToolResultStatus.COMPLETED,
            summary="Resumo.",
            result={"value": float("inf")},
            duration_ms=1,
        )


def test_affected_objects_require_unique_internal_names() -> None:
    with pytest.raises(ValidationError):
        AffectedObjects(modified=("Box", "Box"))

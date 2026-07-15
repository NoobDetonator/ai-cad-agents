from __future__ import annotations

from aicad.core.tool_catalog.schemas import EMPTY_OBJECT
from aicad.core.tool_registry import ToolRisk, ToolSpec


def governance_tool_specs() -> tuple[ToolSpec, ...]:
    """Return the governance CAD tool specifications."""

    return (
        ToolSpec(
            name="cad.validate_document",
            description="Recompute and report document and shape errors.",
            risk=ToolRisk.READ,
            input_schema=EMPTY_OBJECT,
            family="validation",
            aliases=(
                "validar",
                "verificar documento",
                "validate document",
                "check model",
            ),
            tags=(
                "erros",
                "inválido",
                "invalido",
                "formas",
                "recalcular",
                "errors",
                "invalid",
                "recompute",
            ),
            examples=(
                "Confira se há formas inválidas ou erros no modelo.",
                "Validate and recompute the document.",
            ),
            canonical_order=200,
        ),
        ToolSpec(
            name="cad.undo",
            description="Undo the last committed CAD transaction.",
            risk=ToolRisk.MODIFY,
            input_schema=EMPTY_OBJECT,
            family="history",
            aliases=(
                "desfazer",
                "reverter",
                "voltar alteração",
                "undo",
                "revert",
                "rollback",
            ),
            tags=(
                "última",
                "ultima",
                "alteração",
                "alteracao",
                "volte",
                "last",
                "change",
            ),
            examples=(
                "Volte a última alteração que fizemos na peça.",
                "Undo the last CAD transaction.",
            ),
            canonical_order=300,
        ),
        ToolSpec(
            name="cad.get_audit_history",
            description=(
                "Read a bounded summary of this session's redacted local audit "
                "history."
            ),
            risk=ToolRisk.READ,
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "additionalProperties": False,
            },
            family="history",
            aliases=(
                "histórico",
                "historico",
                "auditoria",
                "audit history",
            ),
            tags=("ações", "planos", "aprovações", "actions", "audit"),
            examples=(
                "Mostre o histórico auditável desta sessão.",
                "Show recent audited CAD actions.",
            ),
            canonical_order=310,
        ),
        ToolSpec(
            name="cad.export_audit_history",
            description=(
                "Export this session's redacted audit history to one explicit "
                "absolute JSON destination without silent overwrite."
            ),
            risk=ToolRisk.EXPORT,
            input_schema={
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 1024,
                    },
                    "overwrite": {"type": "boolean"},
                },
                "required": ["destination"],
                "additionalProperties": False,
            },
            family="history",
            aliases=(
                "exportar histórico",
                "exportar historico",
                "export audit history",
            ),
            tags=("auditoria", "json", "arquivo", "audit", "export"),
            examples=(
                "Exporte o histórico para um arquivo JSON escolhido por mim.",
            ),
            canonical_order=320,
        ),
    )

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
import re
from collections.abc import Mapping
from typing import Any, Callable


class ToolRisk(StrEnum):
    READ = "read"
    MODIFY = "modify"
    EXPORT = "export"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    risk: ToolRisk
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    family: str = "general"
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    essential: bool = False
    canonical_order: int = 1000


class ToolInputError(ValueError):
    """Raised before a handler runs when tool arguments do not match its schema."""


class ToolConfirmationRequired(PermissionError):
    """Raised when a risky tool is called without an explicit confirmation."""


class ToolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}

    def register(
        self, spec: ToolSpec, handler: Callable[..., Any] | None = None
    ) -> None:
        if spec.name in self._specs:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._specs[spec.name] = spec
        if handler is not None:
            self._handlers[spec.name] = handler

    def list_specs(self) -> tuple[ToolSpec, ...]:
        return tuple(self._specs.values())

    def get_spec(self, name: str) -> ToolSpec:
        if name not in self._specs:
            raise KeyError(f"Unknown tool: {name}")
        return self._specs[name]

    def bind(self, name: str, handler: Callable[..., Any]) -> None:
        self.get_spec(name)
        if name in self._handlers:
            raise ValueError(f"Tool already has a connected handler: {name}")
        self._handlers[name] = handler

    def has_handler(self, name: str) -> bool:
        self.get_spec(name)
        return name in self._handlers

    def execute(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        confirmed: bool = False,
    ) -> Any:
        spec = self.get_spec(name)
        if name not in self._handlers:
            raise RuntimeError(f"Tool has no connected handler: {name}")
        if spec.risk is not ToolRisk.READ and not confirmed:
            raise ToolConfirmationRequired(
                f"Tool requires explicit confirmation: {name}"
            )
        checked_arguments = self.validate_arguments(name, arguments)
        return self._handlers[name](**checked_arguments)

    def validate_arguments(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate one call without executing or requiring a connected handler."""

        spec = self.get_spec(name)
        if arguments is None:
            checked_arguments: dict[str, Any] = {}
        elif isinstance(arguments, Mapping):
            checked_arguments = dict(arguments)
        else:
            raise ToolInputError(f"Arguments for {name} must be an object.")
        self._validate_arguments(spec, checked_arguments)
        return checked_arguments

    @staticmethod
    def _validate_arguments(spec: ToolSpec, arguments: dict[str, Any]) -> None:
        schema = spec.input_schema
        if schema.get("type") != "object":
            raise RuntimeError(f"Unsupported input schema for tool: {spec.name}")

        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        missing = sorted(required - arguments.keys())
        if missing:
            raise ToolInputError(
                f"Missing required arguments for {spec.name}: {', '.join(missing)}"
            )

        if schema.get("additionalProperties") is False:
            unexpected = sorted(arguments.keys() - properties.keys())
            if unexpected:
                raise ToolInputError(
                    f"Unexpected arguments for {spec.name}: {', '.join(unexpected)}"
                )

        for argument_name, value in arguments.items():
            property_schema = properties.get(argument_name)
            if property_schema is None:
                continue
            expected_type = property_schema.get("type")
            if expected_type == "number":
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ToolInputError(f"{argument_name} must be a number.")
                if not math.isfinite(float(value)):
                    raise ToolInputError(f"{argument_name} must be finite.")
                minimum = property_schema.get("exclusiveMinimum")
                if minimum is not None and value <= minimum:
                    raise ToolInputError(
                        f"{argument_name} must be greater than {minimum}."
                    )
                inclusive_minimum = property_schema.get("minimum")
                inclusive_maximum = property_schema.get("maximum")
                if inclusive_minimum is not None and value < inclusive_minimum:
                    raise ToolInputError(
                        f"{argument_name} must be at least {inclusive_minimum}."
                    )
                if inclusive_maximum is not None and value > inclusive_maximum:
                    raise ToolInputError(
                        f"{argument_name} must be at most {inclusive_maximum}."
                    )
            elif expected_type == "integer":
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ToolInputError(f"{argument_name} must be an integer.")
                minimum = property_schema.get("minimum")
                maximum = property_schema.get("maximum")
                if minimum is not None and value < minimum:
                    raise ToolInputError(
                        f"{argument_name} must be at least {minimum}."
                    )
                if maximum is not None and value > maximum:
                    raise ToolInputError(
                        f"{argument_name} must be at most {maximum}."
                    )
            elif expected_type == "string":
                if not isinstance(value, str):
                    raise ToolInputError(f"{argument_name} must be a string.")
                minimum_length = property_schema.get("minLength")
                maximum_length = property_schema.get("maxLength")
                pattern = property_schema.get("pattern")
                if minimum_length is not None and len(value) < minimum_length:
                    raise ToolInputError(f"{argument_name} is too short.")
                if maximum_length is not None and len(value) > maximum_length:
                    raise ToolInputError(f"{argument_name} is too long.")
                if pattern is not None and re.fullmatch(pattern, value) is None:
                    raise ToolInputError(f"{argument_name} has an invalid format.")
                allowed_values = property_schema.get("enum")
                if allowed_values is not None and value not in allowed_values:
                    raise ToolInputError(
                        f"{argument_name} must be one of the allowed values."
                    )
            elif expected_type == "boolean":
                if not isinstance(value, bool):
                    raise ToolInputError(f"{argument_name} must be a boolean.")
            else:
                raise RuntimeError(
                    f"Unsupported argument type for {spec.name}: {expected_type}"
                )


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    empty_object = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    registry.register(
        ToolSpec(
            name="cad.get_document_summary",
            description="Read the active CAD document and its object tree.",
            risk=ToolRisk.READ,
            input_schema=empty_object,
            family="context",
            aliases=(
                "resumo",
                "resumo do documento",
                "document summary",
                "object tree",
            ),
            tags=(
                "documento",
                "modelo",
                "objetos",
                "existe",
                "atualmente",
                "document",
                "model",
                "objects",
                "exists",
            ),
            examples=(
                "O que existe atualmente neste modelo?",
                "Show the document object tree.",
            ),
            canonical_order=10,
        )
    )
    registry.register(
        ToolSpec(
            name="cad.get_selection",
            description="Read the objects, faces and edges selected by the user.",
            risk=ToolRisk.READ,
            input_schema=empty_object,
            family="context",
            aliases=(
                "seleção",
                "seleção atual",
                "selected objects",
                "current selection",
            ),
            tags=(
                "selecionado",
                "selecionados",
                "faces",
                "arestas",
                "selected",
                "selection",
                "edges",
            ),
            examples=(
                "Quais objetos e faces eu selecionei?",
                "Which edges are selected?",
            ),
            canonical_order=20,
        )
    )
    registry.register(
        ToolSpec(
            name="cad.get_context_snapshot",
            description=(
                "Read a bounded, versioned snapshot of the active document, "
                "selection and recently changed objects."
            ),
            risk=ToolRisk.READ,
            input_schema={
                "type": "object",
                "properties": {
                    "detail_level": {
                        "type": "string",
                        "enum": ["minimal", "work"],
                    },
                    "max_objects": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "cursor": {
                        "type": "integer",
                        "minimum": 0,
                    },
                },
                "additionalProperties": False,
            },
            family="context",
            aliases=(
                "contexto",
                "contexto atual",
                "estado atual",
                "current context",
                "recent objects",
            ),
            tags=(
                "recente",
                "último",
                "ultima",
                "ele",
                "essas",
                "context",
                "recent",
                "current",
            ),
            examples=(
                "Leia o estado atual e os objetos recentes.",
                "Use the current selection and recent object.",
            ),
            essential=True,
            canonical_order=30,
        )
    )
    registry.register(
        ToolSpec(
            name="cad.create_box",
            description="Create a parametric box in a reversible transaction.",
            risk=ToolRisk.MODIFY,
            input_schema={
                "type": "object",
                "properties": {
                    "length": {"type": "number", "exclusiveMinimum": 0},
                    "width": {"type": "number", "exclusiveMinimum": 0},
                    "height": {"type": "number", "exclusiveMinimum": 0},
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 64,
                        "pattern": "[A-Za-z][A-Za-z0-9_-]*",
                    },
                },
                "required": ["length", "width", "height"],
                "additionalProperties": False,
            },
            family="primitive",
            aliases=(
                "caixa",
                "bloco retangular",
                "cubo",
                "box",
                "rectangular block",
                "cube",
            ),
            tags=(
                "comprimento",
                "largura",
                "altura",
                "length",
                "width",
                "height",
                "criar",
                "create",
            ),
            examples=(
                "Crie uma caixa 10 x 20 x 30.",
                "Create a box with length, width and height.",
            ),
            canonical_order=100,
        )
    )
    registry.register(
        ToolSpec(
            name="cad.create_cylinder",
            description=(
                "Create a vertical parametric cylinder from its diameter and "
                "height in millimeters, aligned with the Z axis, in a "
                "reversible transaction."
            ),
            risk=ToolRisk.MODIFY,
            input_schema={
                "type": "object",
                "properties": {
                    "diameter": {"type": "number", "exclusiveMinimum": 0},
                    "height": {"type": "number", "exclusiveMinimum": 0},
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 64,
                        "pattern": "[A-Za-z][A-Za-z0-9_-]*",
                    },
                },
                "required": ["diameter", "height"],
                "additionalProperties": False,
            },
            family="primitive",
            aliases=(
                "cilindro",
                "eixo vertical",
                "pino",
                "cylinder",
                "vertical shaft",
                "pin",
            ),
            tags=(
                "diâmetro",
                "diametro",
                "raio",
                "altura",
                "diameter",
                "radius",
                "height",
                "criar",
                "create",
            ),
            examples=(
                "Modele um eixo vertical de 16 mm de diâmetro.",
                "Create a cylinder with diameter and height.",
            ),
            canonical_order=110,
        )
    )
    registry.register(
        ToolSpec(
            name="cad.validate_document",
            description="Recompute and report document and shape errors.",
            risk=ToolRisk.READ,
            input_schema=empty_object,
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
        )
    )
    registry.register(
        ToolSpec(
            name="cad.undo",
            description="Undo the last committed CAD transaction.",
            risk=ToolRisk.MODIFY,
            input_schema=empty_object,
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
        )
    )
    registry.register(
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
        )
    )
    registry.register(
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
        )
    )
    from aicad.core.mechanical_tools import mechanical_tool_specs

    for spec in mechanical_tool_specs():
        registry.register(spec)
    return registry

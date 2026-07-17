from __future__ import annotations

from aicad.core.expressions import MAX_EXPRESSION_LENGTH
from aicad.core.tool_catalog.schemas import (
    NAME,
    REFERENCE,
    _object_schema,
    _spec,
)
from aicad.core.tool_registry import ToolRisk, ToolSpec


PARAMETER_NAME = {
    "type": "string",
    "minLength": 1,
    "maxLength": 64,
    "pattern": "^[a-z][a-z0-9_]*$",
}

EXPRESSION = {
    "type": ["string", "null"],
    "minLength": 1,
    "maxLength": MAX_EXPRESSION_LENGTH,
}

PARAMETER_RESULT = {
    "type": "object",
    "properties": {
        "set": {"type": "string"},
        "name": {"type": "string"},
        "value": {"type": "number"},
        "kind": {"type": "string"},
        "created": {"type": "boolean"},
        "valid": {"type": "boolean"},
    },
    "required": ["set", "name", "value", "kind", "created", "valid"],
}

BINDING_RESULT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "label": {"type": "string"},
        "expression": {"type": ["string", "null"]},
        "value": {"type": "number"},
        "valid": {"type": "boolean"},
    },
    "required": ["name", "label", "expression", "value", "valid"],
}

PARAMETER_LIST_RESULT = {
    "type": "object",
    "properties": {
        "count": {"type": "integer"},
        "sets": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["count", "sets"],
}


def parameter_tool_specs() -> tuple[ToolSpec, ...]:
    """Return the master parameter tool specifications."""

    return (
        _spec(
            "cad.create_parameter_set",
            (
                "Create a named master parameter set (App::VarSet). "
                "Professional models declare their driving dimensions here "
                "FIRST, then bind sketch datums and feature parameters to "
                "them, so one change recomputes the whole part. Example: "
                "{\"name\": \"Params\"}."
            ),
            ToolRisk.MODIFY,
            _object_schema({"name": NAME}, ()),
            family="parameters",
            aliases=(
                "conjunto de parâmetros",
                "varset",
                "parameter set",
                "variáveis do projeto",
            ),
            tags=("parâmetros", "parameters", "mestre", "master", "varset"),
            examples=(
                "Crie o conjunto de parâmetros do projeto.",
                "Create a parameter set called Params.",
            ),
            order=530,
            output_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "label": {"type": "string"},
                    "valid": {"type": "boolean"},
                },
                "required": ["name", "label", "valid"],
            },
        ),
        _spec(
            "cad.set_master_parameter",
            (
                "Create or update one master parameter in a parameter set and "
                "recompute everything bound to it. Kinds: length (mm), angle "
                "(degrees), count (integer) and factor (unitless). Example: "
                "{\"name\": \"wall_thickness\", \"value\": 2.4, \"kind\": "
                "\"length\"}."
            ),
            ToolRisk.MODIFY,
            {
                "type": "object",
                "properties": {
                    "name": PARAMETER_NAME,
                    "value": {
                        "type": "number",
                        "minimum": -100000,
                        "maximum": 100000,
                    },
                    "set": REFERENCE,
                    "kind": {
                        "type": "string",
                        "enum": ["length", "angle", "count", "factor"],
                    },
                },
                "required": ["name", "value"],
                "additionalProperties": False,
            },
            family="parameters",
            aliases=(
                "definir parâmetro",
                "mudar parâmetro mestre",
                "set parameter value",
            ),
            tags=("parâmetros", "parameter", "valor", "espessura", "mestre"),
            examples=(
                "Mude wall_thickness para 2.4 mm.",
                "Set the tooth_count parameter to 20.",
            ),
            order=531,
            output_schema=PARAMETER_RESULT,
        ),
        _spec(
            "cad.list_master_parameters",
            (
                "List every master parameter set with its parameters, values "
                "and property types. Read this before binding or changing "
                "parameters. Example: {}."
            ),
            ToolRisk.READ,
            _object_schema({"set": REFERENCE}, ()),
            family="parameters",
            aliases=(
                "listar parâmetros",
                "quais parâmetros",
                "list parameters",
            ),
            tags=("parâmetros", "parameters", "listar", "list", "valores"),
            examples=(
                "Quais parâmetros mestres o projeto tem?",
                "List the master parameters and their values.",
            ),
            order=532,
            output_schema=PARAMETER_LIST_RESULT,
        ),
        _spec(
            "cad.rename_sketch_constraint",
            (
                "Give a dimensional sketch constraint a stable lowercase name "
                "(by index) so it can be bound to a master parameter and read "
                "by humans. Example: {\"sketch\": \"BaseSketch\", "
                "\"constraint\": 8, \"name\": \"plate_width\"}."
            ),
            ToolRisk.MODIFY,
            {
                "type": "object",
                "properties": {
                    "sketch": REFERENCE,
                    "constraint": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 4096,
                    },
                    "name": PARAMETER_NAME,
                },
                "required": ["sketch", "constraint", "name"],
                "additionalProperties": False,
            },
            family="parameters",
            aliases=(
                "nomear cota",
                "renomear restrição",
                "name constraint",
            ),
            tags=("cota", "restrição", "constraint", "nome", "rename"),
            examples=(
                "Nomeie a cota 8 do sketch como plate_width.",
                "Name constraint 3 hole_spacing.",
            ),
            order=533,
            output_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "label": {"type": "string"},
                    "constraint_index": {"type": "integer"},
                    "constraint_name": {"type": "string"},
                    "valid": {"type": "boolean"},
                },
                "required": [
                    "name",
                    "label",
                    "constraint_index",
                    "constraint_name",
                    "valid",
                ],
            },
        ),
        _spec(
            "cad.bind_sketch_datum",
            (
                "Bind a NAMED dimensional sketch constraint to a closed "
                "arithmetic expression over master parameters, such as "
                "Params.width or Params.width / 2 + 5. Pass null to remove "
                "the binding. Function calls are rejected. Example: "
                "{\"sketch\": \"BaseSketch\", \"constraint\": "
                "\"plate_width\", \"expression\": \"Params.width\"}."
            ),
            ToolRisk.MODIFY,
            {
                "type": "object",
                "properties": {
                    "sketch": REFERENCE,
                    "constraint": PARAMETER_NAME,
                    "expression": EXPRESSION,
                },
                "required": ["sketch", "constraint", "expression"],
                "additionalProperties": False,
            },
            family="parameters",
            aliases=(
                "vincular cota",
                "cota por expressão",
                "bind dimension",
                "drive dimension",
            ),
            tags=("expressão", "expression", "vincular", "bind", "cota"),
            examples=(
                "Vincule plate_width ao parâmetro Params.width.",
                "Drive the hole spacing by Params.width / 2.",
            ),
            order=534,
            output_schema=BINDING_RESULT,
        ),
        _spec(
            "cad.bind_feature_parameter",
            (
                "Bind a whitelisted parameter of a parametric PartDesign "
                "feature (pad length, pattern occurrences...) to a closed "
                "arithmetic expression over master parameters. Pass null to "
                "remove the binding. Example: {\"feature\": \"AIPad\", "
                "\"parameter\": \"length\", \"expression\": "
                "\"Params.height\"}."
            ),
            ToolRisk.MODIFY,
            {
                "type": "object",
                "properties": {
                    "feature": REFERENCE,
                    "parameter": PARAMETER_NAME,
                    "expression": EXPRESSION,
                },
                "required": ["feature", "parameter", "expression"],
                "additionalProperties": False,
            },
            family="parameters",
            aliases=(
                "vincular feature",
                "parâmetro por expressão",
                "bind feature parameter",
            ),
            tags=("expressão", "expression", "vincular", "bind", "feature"),
            examples=(
                "Vincule o comprimento do pad a Params.height.",
                "Drive the pattern occurrences by Params.hole_count.",
            ),
            order=535,
            output_schema=BINDING_RESULT,
        ),
    )

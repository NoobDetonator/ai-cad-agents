from __future__ import annotations

from typing import Any

from aicad.core.tool_registry import ToolRisk, ToolSpec


NAME = {
    "type": "string",
    "minLength": 1,
    "maxLength": 64,
    "pattern": "[A-Za-z][A-Za-z0-9_-]*",
}
REFERENCE = {"type": "string", "minLength": 1, "maxLength": 256}
POSITIVE = {"type": "number", "exclusiveMinimum": 0}
NON_NEGATIVE = {"type": "number", "minimum": 0}
NUMBER = {"type": "number"}
INTEGER = {"type": "integer", "minimum": 1, "maximum": 128}


def _object_schema(
    properties: dict[str, Any],
    required: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


OBJECT_RESULT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "label": {"type": "string"},
        "valid": {"type": "boolean"},
    },
    "required": ["name", "label", "valid"],
}

DETAIL_RESULT = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "object": {"type": "object"},
        "editable_parameters": {"type": "array"},
        "edge_references": {"type": "array"},
        "edge_references_truncated": {"type": "boolean"},
    },
    "required": ["status", "object", "editable_parameters", "edge_references"],
}

MEASUREMENT_RESULT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "label": {"type": "string"},
        "length_mm": {"type": "number"},
        "width_mm": {"type": "number"},
        "height_mm": {"type": "number"},
        "bounds_mm": {"type": "array"},
        "center_mm": {"type": "array"},
        "volume_mm3": {"type": "number"},
        "area_mm2": {"type": "number"},
        "solids": {"type": "integer"},
        "valid": {"type": "boolean"},
    },
    "required": ["name", "label", "bounds_mm", "valid"],
}

DISTANCE_RESULT = {
    "type": "object",
    "properties": {
        "left": {"type": "object"},
        "right": {"type": "object"},
        "minimum_distance_mm": {"type": "number"},
        "center_distance_mm": {"type": "number"},
        "closest_points_mm": {"type": "array"},
        "intersects_or_touches": {"type": "boolean"},
    },
    "required": [
        "left",
        "right",
        "minimum_distance_mm",
        "center_distance_mm",
        "closest_points_mm",
        "intersects_or_touches",
    ],
}

PLACEMENT_RESULT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "label": {"type": "string"},
        "position_mm": {"type": "array"},
        "rotation_quaternion": {"type": "array"},
        "valid": {"type": "boolean"},
    },
    "required": [
        "name",
        "label",
        "position_mm",
        "rotation_quaternion",
        "valid",
    ],
}

DELETION_RESULT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "label": {"type": "string"},
        "deleted": {"type": "boolean"},
    },
    "required": ["name", "label", "deleted"],
}

INTERFERENCE_RESULT = {
    "type": "object",
    "properties": {
        "valid": {"type": "boolean"},
        "pair_count": {"type": "integer"},
        "interference_count": {"type": "integer"},
        "contact_count": {"type": "integer"},
        "clearance_violation_count": {"type": "integer"},
        "pairs": {"type": "array"},
    },
    "required": [
        "valid",
        "pair_count",
        "interference_count",
        "contact_count",
        "clearance_violation_count",
        "pairs",
    ],
}

DEPENDENCY_RESULT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "depends_on": {"type": "array"},
        "used_by": {"type": "array"},
    },
    "required": ["name", "depends_on", "used_by"],
}

RESOLUTION_RESULT = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["resolved", "awaiting_selection", "not_found"],
        },
        "object": {"type": "object"},
        "required": {"type": "string"},
        "candidates": {"type": "array"},
        "reference": {"type": "string"},
    },
    "required": ["status"],
}

PARAMETERS_RESULT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "label": {"type": "string"},
        "parameters": {"type": "array"},
    },
    "required": ["name", "label", "parameters"],
}

CAPTURE_RESULT = {
    "type": "object",
    "properties": {
        "capture_id": {"type": "string"},
        "mime_type": {"type": "string", "enum": ["image/png"]},
        "width": {"type": "integer"},
        "height": {"type": "integer"},
        "view": {"type": "string"},
        "fit": {"type": "boolean"},
        "bytes": {"type": "integer"},
        "resource_uri": {"type": "string"},
    },
    "required": [
        "capture_id",
        "mime_type",
        "width",
        "height",
        "bytes",
        "resource_uri",
    ],
}


def _spec(
    name: str,
    description: str,
    risk: ToolRisk,
    input_schema: dict[str, Any],
    *,
    family: str,
    aliases: tuple[str, ...],
    tags: tuple[str, ...],
    examples: tuple[str, ...],
    order: int,
    output_schema: dict[str, Any] | None = None,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=description,
        risk=risk,
        input_schema=input_schema,
        output_schema=output_schema,
        family=family,
        aliases=aliases,
        tags=tags,
        examples=examples,
        canonical_order=order,
    )

EMPTY_OBJECT = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

CAD_EXPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "destination": {
            "type": "string",
            "minLength": 1,
            "maxLength": 1024,
        },
        "object": {
            "type": "string",
            "minLength": 1,
            "maxLength": 128,
        },
        "overwrite": {"type": "boolean"},
    },
    "required": ["destination", "object"],
    "additionalProperties": False,
}

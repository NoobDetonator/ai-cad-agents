from __future__ import annotations

from typing import Any

from aicad.core.tool_registry import ToolRisk, ToolSpec


NAME = {
    "type": "string",
    "minLength": 1,
    "maxLength": 64,
    "pattern": "^[A-Za-z][A-Za-z0-9_-]*$",
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

DOCUMENT_SUMMARY_RESULT = {
    "type": "object",
    "properties": {
        "active": {"type": "boolean"},
        "name": {"type": ["string", "null"]},
        "label": {"type": "string"},
        "objects": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["active", "name", "objects"],
}
SELECTION_RESULT = {
    "type": "object",
    "properties": {
        "selection": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["selection"],
}
VALIDATION_RESULT = {
    "type": "object",
    "properties": {
        "valid": {"type": "boolean"},
        "errors": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["valid", "errors"],
}
UNDO_RESULT = {
    "type": "object",
    "properties": {"undone": {"type": "boolean"}},
    "required": ["undone"],
}
AUDIT_HISTORY_RESULT = {
    "type": "object",
    "properties": {
        "schema_version": {"type": "string"},
        "session_id": {"type": "string"},
        "count": {"type": "integer"},
        "actions": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["schema_version", "session_id", "count", "actions"],
}
AUDIT_EXPORT_RESULT = {
    "type": "object",
    "properties": {
        "destination": {"type": "string"},
        "session_id": {"type": "string"},
        "record_count": {"type": "integer"},
        "valid": {"type": "boolean"},
    },
    "required": ["destination", "session_id", "record_count", "valid"],
}
DOCUMENT_LIST_RESULT = {
    "type": "object",
    "properties": {
        "active_document": {"type": ["string", "null"]},
        "documents": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["active_document", "documents"],
}
DOCUMENT_RESULT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "label": {"type": "string"},
        "active": {"type": "boolean"},
        "valid": {"type": "boolean"},
    },
    "required": ["name", "label", "active", "valid"],
}
SAVED_DOCUMENT_RESULT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "label": {"type": "string"},
        "destination": {"type": "string"},
        "size_bytes": {"type": "integer"},
        "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        "valid": {"type": "boolean"},
    },
    "required": [
        "name",
        "label",
        "destination",
        "size_bytes",
        "sha256",
        "valid",
    ],
}
CAD_EXPORT_RESULT = {
    "type": "object",
    "properties": {
        "destination": {"type": "string"},
        "format": {"type": "string", "enum": ["stl", "step"]},
        "object": {"type": "string"},
        "label": {"type": "string"},
        "size_bytes": {"type": "integer"},
        "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        "valid": {"type": "boolean"},
    },
    "required": [
        "destination",
        "format",
        "object",
        "label",
        "size_bytes",
        "sha256",
        "valid",
    ],
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

MASS_PROPERTIES_RESULT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "label": {"type": "string"},
        "density_g_cm3": {"type": "number"},
        "volume_mm3": {"type": "number"},
        "mass_g": {"type": "number"},
        "mass_kg": {"type": "number"},
        "center_of_mass_mm": {"type": "array"},
        "solids": {"type": "integer"},
        "valid": {"type": "boolean"},
    },
    "required": [
        "name",
        "label",
        "density_g_cm3",
        "volume_mm3",
        "mass_g",
        "center_of_mass_mm",
        "valid",
    ],
}

PRINT_READINESS_RESULT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "label": {"type": "string"},
        "valid": {"type": "boolean"},
        "solids": {"type": "integer"},
        "closed_solids": {"type": "integer"},
        "build_direction": {"type": "string"},
        "max_overhang_angle_deg": {"type": "number"},
        "bed_z_mm": {"type": "number"},
        "bed_contact_area_mm2": {"type": "number"},
        "overhang_area_mm2": {"type": "number"},
        "overhang_faces": {"type": "array"},
        "overhang_faces_truncated": {"type": "boolean"},
        "floating_solids": {"type": "array"},
        "needs_support": {"type": "boolean"},
        "normals_sampled_at_face_center": {"type": "boolean"},
    },
    "required": [
        "name",
        "label",
        "valid",
        "solids",
        "needs_support",
        "overhang_faces",
        "bed_contact_area_mm2",
    ],
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

CAPTURE_ITEM_RESULT = {
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
        "view",
        "fit",
        "bytes",
        "resource_uri",
    ],
}

CAPTURE_RESULT = {
    "type": "object",
    "properties": {
        **CAPTURE_ITEM_RESULT["properties"],
        "camera_restored": {"type": "boolean"},
    },
    "required": [
        *CAPTURE_ITEM_RESULT["required"],
        "camera_restored",
    ],
}

CAPTURES_RESULT = {
    "type": "object",
    "properties": {
        "views": {"type": "array", "items": {"type": "string"}},
        "count": {"type": "integer"},
        "width": {"type": "integer"},
        "height": {"type": "integer"},
        "fit": {"type": "boolean"},
        "total_bytes": {"type": "integer"},
        "camera_restored": {"type": "boolean"},
        "captures": {"type": "array", "items": CAPTURE_ITEM_RESULT},
    },
    "required": [
        "views",
        "count",
        "width",
        "height",
        "fit",
        "total_bytes",
        "camera_restored",
        "captures",
    ],
}

SECTION_CAPTURE_RESULT = {
    "type": "object",
    "properties": {
        **CAPTURE_RESULT["properties"],
        "plane": {"type": "string"},
        "offset_mm": {"type": "number"},
        "flip": {"type": "boolean"},
        "normal": {
            "type": "array",
            "items": {"type": "number"},
            "minItems": 3,
            "maxItems": 3,
        },
        "kept_side": {
            "type": "string",
            "enum": ["negative_normal", "positive_normal"],
        },
        "capped": {"type": "boolean"},
        "clipping_restored": {"type": "boolean"},
    },
    "required": [
        *CAPTURE_RESULT["required"],
        "plane",
        "offset_mm",
        "flip",
        "normal",
        "kept_side",
        "capped",
        "clipping_restored",
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
        compensatable=risk is ToolRisk.MODIFY,
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

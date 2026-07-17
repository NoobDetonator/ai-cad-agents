"""Composite, bounded model inspection independent of the bridge transport.

The inspection walks a fixed read sequence (context, validation, per-object
reads, optional visuals, final context) through an injected ``read`` callable,
so the flow is unit-testable without FreeCAD or a TCP bridge. State tokens from
the first and last snapshot tell the caller whether the document stayed stable
throughout the multi-read inspection.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


InspectionRead = Callable[[str, dict[str, object]], tuple[bool, "JsonValue"]]

DEFAULT_INSPECTION_VIEWS = ("isometric", "front", "top", "right")
MAX_INSPECTION_OBJECTS = 8
MAX_INSPECTION_VIEWS = 4


class InspectedObject(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reference: str
    measurement: JsonValue = None
    details: JsonValue = None
    dependencies: JsonValue = None


class CadModelInspection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["completed", "partial", "failed"]
    phase: Literal["context"] | None = None
    bridge_calls: int = Field(ge=0)
    state_consistent: bool | None = None
    initial_state_token: JsonValue = None
    final_state_token: JsonValue = None
    context: JsonValue = None
    validation: JsonValue = None
    object_source: (
        Literal["explicit", "selection", "recent", "context"] | None
    ) = None
    inspected_objects: tuple[InspectedObject, ...] = ()
    visuals: JsonValue = None
    response: JsonValue = None


def _check_inspection_arguments(
    objects: list[str] | None,
    max_objects: int,
    views: list[str] | None,
) -> None:
    if isinstance(max_objects, bool) or not isinstance(max_objects, int):
        raise ValueError("The inspection object limit must be an integer.")
    if not 1 <= max_objects <= MAX_INSPECTION_OBJECTS:
        raise ValueError(
            "The inspection object limit must be between 1 and "
            f"{MAX_INSPECTION_OBJECTS}."
        )
    if objects is not None:
        if not objects or len(objects) > max_objects:
            raise ValueError(
                "Inspection objects must contain between one and max_objects items."
            )
        if any(not isinstance(item, str) or not item.strip() for item in objects):
            raise ValueError("Inspection object references must be non-empty strings.")
        if len(objects) != len(set(objects)):
            raise ValueError("Inspection object references must be unique.")
    if views is not None:
        if (
            not views
            or len(views) > MAX_INSPECTION_VIEWS
            or len(views) != len(set(views))
        ):
            raise ValueError(
                "Inspection views must contain one to "
                f"{MAX_INSPECTION_VIEWS} unique views."
            )


def _resolve_targets(
    context_payload: Mapping[str, object],
    objects: list[str] | None,
    max_objects: int,
) -> tuple[list[str], Literal["explicit", "selection", "recent", "context"]]:
    selected = context_payload.get("selection", [])
    recent = context_payload.get("recent_objects", [])
    context_objects = context_payload.get("objects", [])
    source: Literal["explicit", "selection", "recent", "context"]
    if objects is not None:
        targets = list(objects)
        source = "explicit"
    elif isinstance(selected, list) and selected:
        targets = [
            item["name"]
            for item in selected
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        ]
        source = "selection"
    elif isinstance(recent, list) and recent:
        targets = [item for item in recent if isinstance(item, str)]
        source = "recent"
    else:
        targets = (
            [
                item["name"]
                for item in context_objects
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            ]
            if isinstance(context_objects, list)
            else []
        )
        source = "context"
    return list(dict.fromkeys(targets))[:max_objects], source


def inspect_model(
    read: InspectionRead,
    *,
    objects: list[str] | None = None,
    max_objects: int = 3,
    include_details: bool = False,
    include_dependencies: bool = False,
    include_visuals: bool = False,
    views: list[str] | None = None,
) -> CadModelInspection:
    """Run the bounded inspection sequence through one injected read callable."""

    _check_inspection_arguments(objects, max_objects, views)

    bridge_calls = 0
    partial = False

    def call(name: str, arguments: dict[str, object]) -> tuple[bool, JsonValue]:
        nonlocal bridge_calls
        bridge_calls += 1
        return read(name, arguments)

    context_ok, context_payload = call(
        "cad.get_context_snapshot",
        {"detail_level": "work", "max_objects": max_objects, "cursor": 0},
    )
    if not context_ok or not isinstance(context_payload, dict):
        return CadModelInspection(
            status="failed",
            phase="context",
            bridge_calls=bridge_calls,
            response=context_payload,
        )

    initial_token = context_payload.get("state_token")
    targets, object_source = _resolve_targets(context_payload, objects, max_objects)

    validation_ok, validation = call("cad.validate_document", {})
    partial = partial or not validation_ok

    inspections: list[InspectedObject] = []
    for reference in targets:
        measurement_ok, measurement = call("cad.measure_object", {"object": reference})
        partial = partial or not measurement_ok
        details: JsonValue = None
        dependencies: JsonValue = None
        if include_details:
            details_ok, details = call("cad.get_object_details", {"object": reference})
            partial = partial or not details_ok
        if include_dependencies:
            dependencies_ok, dependencies = call(
                "cad.get_dependencies",
                {"object": reference},
            )
            partial = partial or not dependencies_ok
        inspections.append(
            InspectedObject(
                reference=reference,
                measurement=measurement,
                details=details,
                dependencies=dependencies,
            )
        )

    visuals: JsonValue = None
    if include_visuals:
        visuals_ok, visuals = call(
            "cad.capture_views",
            {
                "views": views or list(DEFAULT_INSPECTION_VIEWS),
                "width": 640,
                "height": 480,
                "fit": True,
            },
        )
        partial = partial or not visuals_ok

    final_ok, final_context = call(
        "cad.get_context_snapshot",
        {"detail_level": "minimal", "max_objects": 1, "cursor": 0},
    )
    final_token = (
        final_context.get("state_token")
        if final_ok and isinstance(final_context, dict)
        else None
    )
    state_consistent = initial_token == final_token
    partial = partial or not final_ok or not state_consistent
    return CadModelInspection(
        status="partial" if partial else "completed",
        bridge_calls=bridge_calls,
        state_consistent=state_consistent,
        initial_state_token=initial_token,
        final_state_token=final_token,
        context=context_payload,
        validation=validation,
        object_source=object_source,
        inspected_objects=tuple(inspections),
        visuals=visuals,
    )


__all__ = [
    "CadModelInspection",
    "DEFAULT_INSPECTION_VIEWS",
    "InspectedObject",
    "InspectionRead",
    "inspect_model",
]

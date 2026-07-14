from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Callable

from aicad.core.context import (
    ContextDetailLevel,
    ContextObject,
    ContextPage,
    ContextSelection,
    ContextShapeSummary,
    ContextSnapshot,
    ContextStateTracker,
    ContextSummary,
)


class FreeCadAdapter:
    """Small, explicit boundary around FreeCAD's Python API."""

    def __init__(self, *, context_tracker: ContextStateTracker | None = None) -> None:
        self._context_tracker = context_tracker or ContextStateTracker()

    @staticmethod
    def _modules() -> tuple[Any, Any]:
        try:
            import FreeCAD as App
            import Part
        except ImportError as exc:
            raise RuntimeError("This operation must run inside FreeCAD.") from exc
        return App, Part

    @staticmethod
    def _error_states(item: Any) -> list[str]:
        states = [str(state) for state in item.State]
        error_words = ("error", "invalid", "failed", "exception")
        return [
            state for state in states if any(word in state.lower() for word in error_words)
        ]

    def get_document_summary(self) -> dict[str, Any]:
        app, _ = self._modules()
        document = app.ActiveDocument
        if document is None:
            return {"active": False, "name": None, "objects": []}
        return {
            "active": True,
            "name": document.Name,
            "label": document.Label,
            "objects": [
                {
                    "name": item.Name,
                    "label": item.Label,
                    "type_id": item.TypeId,
                    "has_error": bool(self._error_states(item)),
                }
                for item in document.Objects
            ],
        }

    def get_selection(self) -> dict[str, Any]:
        return {"selection": self._selection_records(required=True)}

    @staticmethod
    def _selection_records(*, required: bool) -> list[dict[str, Any]]:
        try:
            import FreeCADGui as Gui
        except ImportError as exc:
            if not required:
                return []
            raise RuntimeError("This operation must run inside FreeCAD GUI.") from exc
        selection_api = getattr(Gui, "Selection", None)
        if selection_api is None:
            if not required:
                return []
            raise RuntimeError("This operation must run inside FreeCAD GUI.")

        selection = []
        for selected in selection_api.getSelectionEx():
            item = selected.Object
            selection.append(
                {
                    "name": item.Name,
                    "label": item.Label,
                    "type_id": item.TypeId,
                    "subelements": list(selected.SubElementNames),
                }
            )
        return selection

    @staticmethod
    def _finite_float(value: Any) -> float | None:
        try:
            checked = float(value)
        except (TypeError, ValueError):
            return None
        return checked if math.isfinite(checked) else None

    @classmethod
    def _shape_context(cls, item: Any) -> ContextShapeSummary | None:
        shape = getattr(item, "Shape", None)
        if shape is None:
            return None
        is_null = bool(shape.isNull())
        if is_null:
            return ContextShapeSummary(is_null=True, is_valid=False)
        bounds = shape.BoundBox
        bounds_mm = tuple(
            float(value)
            for value in (
                bounds.XMin,
                bounds.YMin,
                bounds.ZMin,
                bounds.XMax,
                bounds.YMax,
                bounds.ZMax,
            )
        )
        return ContextShapeSummary(
            is_null=False,
            is_valid=bool(shape.isValid()),
            volume_mm3=cls._finite_float(getattr(shape, "Volume", None)),
            area_mm2=cls._finite_float(getattr(shape, "Area", None)),
            bounds_mm=bounds_mm,
            solids=len(getattr(shape, "Solids", ())),
            faces=len(getattr(shape, "Faces", ())),
            edges=len(getattr(shape, "Edges", ())),
        )

    @classmethod
    def _parameter_context(cls, item: Any) -> dict[str, Any]:
        parameters: dict[str, Any] = {}
        for name in (
            "Length",
            "Width",
            "Height",
            "Radius",
            "Angle",
            "Diameter",
            "Count",
        ):
            if not hasattr(item, name):
                continue
            raw_value = getattr(item, name)
            value = getattr(raw_value, "Value", raw_value)
            if isinstance(value, bool):
                parameters[name] = value
            elif isinstance(value, (int, float)):
                checked = cls._finite_float(value)
                if checked is not None:
                    parameters[name] = checked
            elif isinstance(value, str) and len(value) <= 256:
                parameters[name] = value
        return parameters

    @classmethod
    def _object_context(cls, item: Any, selected_names: set[str]) -> ContextObject:
        position = None
        rotation = None
        placement = getattr(item, "Placement", None)
        if placement is not None:
            base = placement.Base
            position = (float(base.x), float(base.y), float(base.z))
            rotation = tuple(float(value) for value in placement.Rotation.Q)
        return ContextObject(
            name=item.Name,
            label=item.Label,
            type_id=item.TypeId,
            has_error=bool(cls._error_states(item)),
            selected=item.Name in selected_names,
            parameters=cls._parameter_context(item),
            position_mm=position,
            rotation_quaternion=rotation,
            shape=cls._shape_context(item),
        )

    @staticmethod
    def _fingerprint(value: Any) -> str:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def get_context_snapshot(
        self,
        detail_level: str = "work",
        max_objects: int = 25,
        cursor: int = 0,
    ) -> dict[str, Any]:
        try:
            level = ContextDetailLevel(detail_level)
        except ValueError as exc:
            raise ValueError("Unsupported context detail level.") from exc
        if isinstance(max_objects, bool) or not isinstance(max_objects, int):
            raise ValueError("Context object limit must be an integer.")
        if not 1 <= max_objects <= 100:
            raise ValueError("Context object limit must be between 1 and 100.")
        if isinstance(cursor, bool) or not isinstance(cursor, int) or cursor < 0:
            raise ValueError("Context cursor must be a non-negative integer.")

        app, _ = self._modules()
        document = app.ActiveDocument
        selection_records = self._selection_records(required=False)
        selection = tuple(ContextSelection.model_validate(item) for item in selection_records)
        selection_payload = [item.model_dump(mode="json") for item in selection]
        selection_fingerprint = self._fingerprint(selection_payload)

        if document is None:
            empty_fingerprint = self._fingerprint({"active": False})
            observation = self._context_tracker.observe(
                None,
                empty_fingerprint,
                selection_fingerprint,
                {},
            )
            snapshot = ContextSnapshot(
                detail_level=level,
                active=False,
                state_token=observation.token,
                summary=ContextSummary(
                    object_count=0,
                    error_count=0,
                    selected_count=len(selection),
                ),
                selection=selection if level is ContextDetailLevel.WORK else (),
                page=ContextPage(
                    cursor=0,
                    returned=0,
                    total_objects=0,
                    next_cursor=None,
                    truncated=False,
                ),
            )
            return snapshot.model_dump(mode="json")

        items = sorted(document.Objects, key=lambda item: item.Name)
        if cursor > len(items):
            raise ValueError("Context cursor exceeds the object count.")
        selected_names = {item.name for item in selection}
        context_objects = tuple(
            self._object_context(item, selected_names) for item in items
        )
        object_payloads = [item.model_dump(mode="json") for item in context_objects]
        object_fingerprints = {
            item.name: self._fingerprint(payload)
            for item, payload in zip(context_objects, object_payloads, strict=True)
        }
        document_fingerprint = self._fingerprint(
            {
                "name": document.Name,
                "label": document.Label,
                "objects": object_payloads,
            }
        )
        observation = self._context_tracker.observe(
            document.Name,
            document_fingerprint,
            selection_fingerprint,
            object_fingerprints,
        )

        if level is ContextDetailLevel.MINIMAL:
            returned_objects: tuple[ContextObject, ...] = ()
            next_cursor = 0 if context_objects else None
            page_cursor = 0
        else:
            returned_objects = context_objects[cursor : cursor + max_objects]
            following = cursor + len(returned_objects)
            next_cursor = following if following < len(context_objects) else None
            page_cursor = cursor

        snapshot = ContextSnapshot(
            detail_level=level,
            active=True,
            document_name=document.Name,
            document_label=document.Label,
            state_token=observation.token,
            summary=ContextSummary(
                object_count=len(context_objects),
                error_count=sum(item.has_error for item in context_objects),
                selected_count=len(selection),
            ),
            selection=selection if level is ContextDetailLevel.WORK else (),
            objects=returned_objects,
            recent_objects=observation.recent_objects,
            page=ContextPage(
                cursor=page_cursor,
                returned=len(returned_objects),
                total_objects=len(context_objects),
                next_cursor=next_cursor,
                truncated=next_cursor is not None,
            ),
        )
        return snapshot.model_dump(mode="json")

    @staticmethod
    def _positive_values(*values: float) -> tuple[float, ...]:
        checked = tuple(float(value) for value in values)
        if any(not math.isfinite(value) or value <= 0 for value in checked):
            raise ValueError("All dimensions must be positive.")
        return checked

    @staticmethod
    def _validated_object_name(name: str) -> str:
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", name) is None:
            raise ValueError("The object name has an invalid format.")
        return name

    def _create_validated_shape(
        self,
        name: str,
        configure: Callable[[Any], Any],
    ) -> Any:
        app, _ = self._modules()
        document = app.ActiveDocument or app.newDocument("AICadDocument")
        if document.UndoMode == 0:
            document.UndoMode = 1
        document.openTransaction(f"AI CAD: create {name}")
        try:
            item = configure(document)
            item.Label = name
            document.recompute()
            if item.Shape.isNull() or not item.Shape.isValid():
                raise RuntimeError("FreeCAD produced an invalid shape.")
            validation = self._validate_document(document)
            if not validation["valid"]:
                raise RuntimeError(
                    "FreeCAD document validation failed: "
                    + "; ".join(validation["errors"])
                )
            document.commitTransaction()
            self._context_tracker.record_recent(document.Name, (item.Name,))
        except Exception:
            document.abortTransaction()
            document.recompute()
            raise
        return item

    def create_box(
        self, length: float, width: float, height: float, name: str = "AIBox"
    ) -> dict[str, Any]:
        dimensions = self._positive_values(length, width, height)
        checked_name = self._validated_object_name(name)

        def configure(document: Any) -> Any:
            box = document.addObject("Part::Box", checked_name)
            box.Length, box.Width, box.Height = dimensions
            return box

        box = self._create_validated_shape(checked_name, configure)
        return {
            "name": box.Name,
            "label": box.Label,
            "dimensions_mm": list(dimensions),
            "volume_mm3": float(box.Shape.Volume),
            "valid": True,
        }

    def create_cylinder(
        self,
        diameter: float,
        height: float,
        name: str = "AICylinder",
    ) -> dict[str, Any]:
        checked_diameter, checked_height = self._positive_values(diameter, height)
        checked_name = self._validated_object_name(name)
        radius = checked_diameter / 2

        def configure(document: Any) -> Any:
            cylinder = document.addObject("Part::Cylinder", checked_name)
            cylinder.Radius = radius
            cylinder.Height = checked_height
            cylinder.Angle = 360
            return cylinder

        cylinder = self._create_validated_shape(checked_name, configure)
        return {
            "name": cylinder.Name,
            "label": cylinder.Label,
            "diameter_mm": checked_diameter,
            "radius_mm": radius,
            "height_mm": checked_height,
            "volume_mm3": float(cylinder.Shape.Volume),
            "valid": True,
        }

    def _validate_document(self, document: Any) -> dict[str, Any]:
        if document is None:
            return {"valid": False, "errors": ["No active document."]}
        document.recompute()
        errors: list[str] = []
        for item in document.Objects:
            error_states = self._error_states(item)
            if error_states:
                errors.append(f"{item.Name}: {', '.join(error_states)}")
            shape = getattr(item, "Shape", None)
            if shape is not None and not shape.isNull() and not shape.isValid():
                errors.append(f"{item.Name}: invalid shape")
        return {"valid": not errors, "errors": errors}

    def validate_document(self) -> dict[str, Any]:
        app, _ = self._modules()
        return self._validate_document(app.ActiveDocument)

    def undo(self) -> dict[str, bool]:
        app, _ = self._modules()
        document = app.ActiveDocument
        if document is None or document.UndoCount == 0:
            return {"undone": False}
        document.undo()
        document.recompute()
        return {"undone": True}

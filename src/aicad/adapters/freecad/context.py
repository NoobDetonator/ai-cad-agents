from __future__ import annotations

from typing import Any, Iterable

from aicad.core.context import (
    ContextDetailLevel,
    ContextObject,
    ContextPage,
    ContextSelection,
    ContextShapeSummary,
    ContextSnapshot,
    ContextSummary,
)
from aicad.core.visual_cache import (
    MAX_CAPTURE_BYTES,
    new_capture_path,
    prune_visual_cache,
    read_capture,
)


class ContextReadsMixin:
    """Read-only document, selection, measurement and visual context."""

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

    def get_object_details(self, object: str) -> dict[str, Any]:
        item = self._resolve_document_object(object)
        shape = getattr(item, "Shape", None)
        edges = []
        if shape is not None and not shape.isNull():
            for edge in shape.Edges[:64]:
                signature, payload = self._edge_signature(edge)
                edges.append({"reference": signature, **payload})
        context = self._object_context(item, set())
        return {
            "status": "resolved",
            "object": context.model_dump(mode="json"),
            "editable_parameters": self._editable_parameter_records(item),
            "edge_references": edges,
            "edge_references_truncated": bool(
                shape is not None and len(shape.Edges) > len(edges)
            ),
        }

    def measure_object(self, object: str) -> dict[str, Any]:
        item = self._resolve_document_object(object)
        shape = self._shape_or_error(item)
        bounds = shape.BoundBox
        return {
            "name": item.Name,
            "label": item.Label,
            "length_mm": float(bounds.XLength),
            "width_mm": float(bounds.YLength),
            "height_mm": float(bounds.ZLength),
            "bounds_mm": [
                float(bounds.XMin),
                float(bounds.YMin),
                float(bounds.ZMin),
                float(bounds.XMax),
                float(bounds.YMax),
                float(bounds.ZMax),
            ],
            "center_mm": [
                float(bounds.Center.x),
                float(bounds.Center.y),
                float(bounds.Center.z),
            ],
            "volume_mm3": float(shape.Volume),
            "area_mm2": float(shape.Area),
            "solids": len(shape.Solids),
            "valid": bool(shape.isValid()),
        }

    def get_dependencies(self, object: str) -> dict[str, Any]:
        item = self._resolve_document_object(object)

        def records(items: Iterable[Any]) -> list[dict[str, str]]:
            return [
                {"name": linked.Name, "label": linked.Label, "type_id": linked.TypeId}
                for linked in sorted(items, key=lambda value: value.Name)
            ]

        return {
            "name": item.Name,
            "depends_on": records(getattr(item, "OutList", ())),
            "used_by": records(getattr(item, "InList", ())),
        }

    def resolve_object(self, reference: str = "") -> dict[str, Any]:
        checked = str(reference).strip()
        selection_aliases = {"selected", "selection", "selecionado", "seleção", "ele"}
        if not checked or checked.casefold() in selection_aliases:
            selected = self._selection_records(required=False)
            if len(selected) == 1:
                return {"status": "resolved", "object": selected[0]}
            return {
                "status": "awaiting_selection",
                "required": "one_object",
                "candidates": selected,
            }
        try:
            item = self._resolve_document_object(checked)
        except KeyError:
            return {"status": "not_found", "reference": checked}
        return {
            "status": "resolved",
            "object": {
                "name": item.Name,
                "label": item.Label,
                "type_id": item.TypeId,
                "subelements": [],
            },
        }

    @classmethod
    def _editable_parameter_records(cls, item: Any) -> list[dict[str, Any]]:
        allowed_by_type = {
            "Part::Box": ("Length", "Width", "Height"),
            "Part::Cylinder": ("Radius", "Height", "Angle"),
            "Part::Cone": ("Radius1", "Radius2", "Height", "Angle"),
            "Part::Sphere": ("Radius", "Angle1", "Angle2", "Angle3"),
            "PartDesign::Pad": ("Length",),
        }
        names = allowed_by_type.get(item.TypeId, ())
        records: list[dict[str, Any]] = []
        for name in names:
            if not hasattr(item, name):
                continue
            raw = getattr(item, name)
            value = getattr(raw, "Value", raw)
            checked = cls._finite_float(value)
            if checked is None:
                continue
            records.append(
                {
                    "name": name,
                    "value": checked,
                    "unit": "deg" if name.startswith("Angle") else "mm",
                    "minimum_exclusive": 0,
                }
            )
        return records

    def get_editable_parameters(self, object: str) -> dict[str, Any]:
        item = self._resolve_document_object(object)
        return {
            "name": item.Name,
            "label": item.Label,
            "parameters": self._editable_parameter_records(item),
        }

    def capture_view(self, width: int = 960, height: int = 640) -> dict[str, Any]:
        if not 320 <= int(width) <= 1920 or not 240 <= int(height) <= 1080:
            raise ValueError("Visual capture dimensions are outside the safe limits.")
        try:
            import FreeCADGui as Gui
        except ImportError as exc:
            raise RuntimeError("Visual context requires the FreeCAD GUI.") from exc
        gui_document = Gui.activeDocument()
        if gui_document is None:
            raise RuntimeError("No active GUI document is available.")
        capture_id, path = new_capture_path()
        gui_document.activeView().saveImage(str(path), int(width), int(height), "Current")
        payload = read_capture(capture_id)
        if len(payload) > MAX_CAPTURE_BYTES:
            path.unlink(missing_ok=True)
            raise RuntimeError("The visual capture exceeded the size limit.")
        prune_visual_cache()
        return {
            "capture_id": capture_id,
            "mime_type": "image/png",
            "width": int(width),
            "height": int(height),
            "bytes": len(payload),
            "resource_uri": f"aicad://view/{capture_id}",
        }

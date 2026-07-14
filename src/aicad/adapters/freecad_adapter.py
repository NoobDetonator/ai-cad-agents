from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Callable, Iterable

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
from aicad.core.visual_cache import (
    MAX_CAPTURE_BYTES,
    new_capture_path,
    prune_visual_cache,
    read_capture,
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
    def _active_document() -> Any:
        try:
            import FreeCAD as App
        except ImportError as exc:
            raise RuntimeError("This operation must run inside FreeCAD.") from exc
        document = App.ActiveDocument
        if document is None:
            raise RuntimeError("No active CAD document is available.")
        return document

    @classmethod
    def _resolve_document_object(cls, reference: str) -> Any:
        document = cls._active_document()
        checked = str(reference).strip()
        if not checked:
            raise ValueError("An explicit object reference is required.")
        direct = document.getObject(checked)
        if direct is not None:
            return direct
        folded = checked.casefold()
        matches = [
            item
            for item in document.Objects
            if item.Name.casefold() == folded or str(item.Label).casefold() == folded
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError("The object reference is ambiguous.")
        raise KeyError(f"Unknown CAD object: {checked}")

    @classmethod
    def _edge_signature(cls, edge: Any) -> tuple[str, dict[str, Any]]:
        center = getattr(edge, "CenterOfMass", None)
        center_mm = (
            [float(center.x), float(center.y), float(center.z)]
            if center is not None
            else None
        )
        vertices = [
            [float(vertex.Point.x), float(vertex.Point.y), float(vertex.Point.z)]
            for vertex in getattr(edge, "Vertexes", ())[:2]
        ]
        curve = getattr(edge, "Curve", None)
        payload = {
            "curve": type(curve).__name__ if curve is not None else "unknown",
            "length_mm": round(float(edge.Length), 9),
            "center_mm": center_mm,
            "vertices_mm": vertices,
        }
        signature = "edge:" + cls._fingerprint(payload)[:24]
        return signature, payload

    @classmethod
    def _shape_or_error(cls, item: Any) -> Any:
        shape = getattr(item, "Shape", None)
        if shape is None or shape.isNull() or not shape.isValid():
            raise RuntimeError("The referenced object has no valid shape.")
        return shape

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

    @staticmethod
    def _ensure_undo(document: Any) -> None:
        if document.UndoMode == 0:
            document.UndoMode = 1

    @classmethod
    def _ensure_new_name(cls, document: Any, name: str) -> str:
        checked = cls._validated_object_name(name)
        if document.getObject(checked) is not None:
            raise ValueError(f"A CAD object named {checked} already exists.")
        return checked

    def _run_transaction(
        self,
        title: str,
        operation: Callable[[Any], Any],
    ) -> Any:
        document = self._active_document()
        self._ensure_undo(document)
        document.openTransaction(f"AI CAD: {title}")
        try:
            item = operation(document)
            document.recompute()
            shape = getattr(item, "Shape", None)
            if shape is not None and (shape.isNull() or not shape.isValid()):
                raise RuntimeError("FreeCAD produced an invalid result shape.")
            validation = self._validate_document(document)
            if not validation["valid"]:
                raise RuntimeError(
                    "FreeCAD document validation failed: "
                    + "; ".join(validation["errors"])
                )
            document.commitTransaction()
            self._context_tracker.record_recent(document.Name, (item.Name,))
            return item
        except Exception:
            document.abortTransaction()
            document.recompute()
            raise

    @classmethod
    def _derived_feature(
        cls,
        document: Any,
        name: str,
        shape: Any,
        sources: tuple[Any, ...],
        feature_kind: str,
    ) -> Any:
        if shape.isNull() or not shape.isValid() or not shape.Solids:
            raise RuntimeError("The mechanical operation did not produce a valid solid.")
        checked_name = cls._ensure_new_name(document, name)
        result = document.addObject("PartDesign::Feature", checked_name)
        result.Label = checked_name
        result.Shape = shape
        result.addProperty("App::PropertyLinkList", "SourceObjects", "AI CAD")
        result.SourceObjects = list(sources)
        result.addProperty("App::PropertyString", "FeatureKind", "AI CAD")
        result.FeatureKind = feature_kind
        for source in sources:
            view = getattr(source, "ViewObject", None)
            if view is not None:
                view.Visibility = False
        return result

    def rename_object(self, object: str, name: str) -> dict[str, Any]:
        item = self._resolve_document_object(object)
        checked_name = self._validated_object_name(name)
        if item.Label == checked_name:
            raise ValueError("The object already has that label.")
        if any(
            candidate is not item
            and str(candidate.Label).casefold() == checked_name.casefold()
            for candidate in self._active_document().Objects
        ):
            raise ValueError("Another CAD object already uses that label.")

        def rename(_: Any) -> Any:
            item.Label = checked_name
            return item

        changed = self._run_transaction(f"rename {item.Name}", rename)
        return {"name": changed.Name, "label": changed.Label, "valid": True}

    def set_parameter(
        self,
        object: str,
        parameter: str,
        value: float,
    ) -> dict[str, Any]:
        item = self._resolve_document_object(object)
        checked_value = float(value)
        if not math.isfinite(checked_value) or checked_value <= 0:
            raise ValueError("The parameter value must be positive and finite.")
        records = self._editable_parameter_records(item)
        names = {record["name"].casefold(): record["name"] for record in records}
        resolved = names.get(str(parameter).casefold())
        if resolved is None:
            raise ValueError("The requested parameter is not safely editable.")
        if resolved.startswith("Angle") and checked_value > 360:
            raise ValueError("Angular parameters cannot exceed 360 degrees.")
        current = float(getattr(getattr(item, resolved), "Value", getattr(item, resolved)))
        if math.isclose(current, checked_value, rel_tol=0, abs_tol=1e-12):
            raise ValueError("The parameter already has that value.")

        def update(_: Any) -> Any:
            setattr(item, resolved, checked_value)
            return item

        changed = self._run_transaction(f"set {item.Name}.{resolved}", update)
        return {
            "name": changed.Name,
            "label": changed.Label,
            "parameter": resolved,
            "value": checked_value,
            "valid": True,
        }

    def transform_object(
        self,
        object: str,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
        roll: float | None = None,
        pitch: float | None = None,
        yaw: float | None = None,
    ) -> dict[str, Any]:
        item = self._resolve_document_object(object)
        values = (x, y, z, roll, pitch, yaw)
        if all(value is None for value in values):
            raise ValueError("At least one transform component is required.")
        checked = [self._finite_float(value) if value is not None else None for value in values]
        if any(value is None and original is not None for value, original in zip(checked, values)):
            raise ValueError("Transform components must be finite.")
        app, _ = self._modules()
        current = item.Placement
        px = float(current.Base.x) if checked[0] is None else checked[0]
        py = float(current.Base.y) if checked[1] is None else checked[1]
        pz = float(current.Base.z) if checked[2] is None else checked[2]
        rotation = current.Rotation
        if any(value is not None for value in checked[3:]):
            rotation = app.Rotation(
                checked[5] or 0.0,
                checked[4] or 0.0,
                checked[3] or 0.0,
            )
        next_quaternion = tuple(float(value) for value in rotation.Q)
        current_quaternion = tuple(float(value) for value in current.Rotation.Q)
        if (
            math.isclose(px, float(current.Base.x), abs_tol=1e-12)
            and math.isclose(py, float(current.Base.y), abs_tol=1e-12)
            and math.isclose(pz, float(current.Base.z), abs_tol=1e-12)
            and all(
                math.isclose(left, right, abs_tol=1e-12)
                for left, right in zip(next_quaternion, current_quaternion, strict=True)
            )
        ):
            raise ValueError("The requested transform would not change the object.")

        def transform(_: Any) -> Any:
            item.Placement = app.Placement(app.Vector(px, py, pz), rotation)
            return item

        changed = self._run_transaction(f"transform {item.Name}", transform)
        base = changed.Placement.Base
        return {
            "name": changed.Name,
            "label": changed.Label,
            "position_mm": [float(base.x), float(base.y), float(base.z)],
            "rotation_quaternion": [float(value) for value in changed.Placement.Rotation.Q],
            "valid": True,
        }

    def create_plate(
        self,
        length: float,
        width: float,
        thickness: float,
        name: str = "AIPlate",
    ) -> dict[str, Any]:
        dimensions = self._positive_values(length, width, thickness)
        checked_name = self._validated_object_name(name)

        def configure(document: Any) -> Any:
            self._ensure_new_name(document, checked_name)
            plate = document.addObject("Part::Box", checked_name)
            plate.Length, plate.Width, plate.Height = dimensions
            plate.Label = checked_name
            return plate

        plate = self._run_transaction(f"create plate {checked_name}", configure)
        return {
            "name": plate.Name,
            "label": plate.Label,
            "dimensions_mm": list(dimensions),
            "volume_mm3": float(plate.Shape.Volume),
            "valid": True,
        }

    def _create_hole_result(
        self,
        source_reference: str,
        diameter: float,
        positions: tuple[tuple[float, float], ...],
        name: str,
        feature_kind: str,
    ) -> Any:
        checked_diameter = self._positive_values(diameter)[0]
        source = self._resolve_document_object(source_reference)
        self._shape_or_error(source)
        app, part = self._modules()

        def cut(document: Any) -> Any:
            bounds = source.Shape.BoundBox
            margin = max(1.0, float(bounds.ZLength) * 0.1)
            cutters = [
                part.makeCylinder(
                    checked_diameter / 2,
                    float(bounds.ZLength) + 2 * margin,
                    app.Vector(x, y, float(bounds.ZMin) - margin),
                )
                for x, y in positions
            ]
            cutter = cutters[0]
            for following in cutters[1:]:
                cutter = cutter.fuse(following)
            result_shape = source.Shape.cut(cutter)
            if (
                result_shape.isNull()
                or not result_shape.isValid()
                or not result_shape.Solids
                or float(result_shape.Volume) <= 0
                or float(result_shape.Volume) >= float(source.Shape.Volume) - 1e-9
            ):
                raise ValueError("The requested holes do not cut the selected solid.")
            return self._derived_feature(
                document,
                name,
                result_shape,
                (source,),
                feature_kind,
            )

        return self._run_transaction(feature_kind, cut)

    def create_through_hole(
        self,
        object: str,
        diameter: float,
        x: float,
        y: float,
        name: str = "AIThroughHole",
    ) -> dict[str, Any]:
        checked_x = self._finite_float(x)
        checked_y = self._finite_float(y)
        if checked_x is None or checked_y is None:
            raise ValueError("Hole coordinates must be finite.")
        result = self._create_hole_result(
            object,
            diameter,
            ((checked_x, checked_y),),
            name,
            "through_hole",
        )
        return {
            "name": result.Name,
            "label": result.Label,
            "hole_count": 1,
            "diameter_mm": float(diameter),
            "valid": True,
        }

    def create_rectangular_hole_pattern(
        self,
        object: str,
        diameter: float,
        rows: int,
        columns: int,
        spacing_x: float,
        spacing_y: float,
        origin_x: float,
        origin_y: float,
        name: str = "AIRectangularHolePattern",
    ) -> dict[str, Any]:
        if rows * columns > 64:
            raise ValueError("A hole pattern cannot exceed 64 instances.")
        sx, sy = self._positive_values(spacing_x, spacing_y)
        ox = self._finite_float(origin_x)
        oy = self._finite_float(origin_y)
        if ox is None or oy is None:
            raise ValueError("Pattern origins must be finite.")
        positions = tuple(
            (ox + column * sx, oy + row * sy)
            for row in range(rows)
            for column in range(columns)
        )
        result = self._create_hole_result(
            object,
            diameter,
            positions,
            name,
            "rectangular_hole_pattern",
        )
        return {
            "name": result.Name,
            "label": result.Label,
            "hole_count": len(positions),
            "valid": True,
        }

    def create_circular_hole_pattern(
        self,
        object: str,
        diameter: float,
        count: int,
        pitch_diameter: float,
        start_angle: float = 0,
        name: str = "AICircularHolePattern",
    ) -> dict[str, Any]:
        if count > 64:
            raise ValueError("A hole pattern cannot exceed 64 instances.")
        pitch = self._positive_values(pitch_diameter)[0]
        angle = self._finite_float(start_angle)
        if angle is None:
            raise ValueError("The pattern angle must be finite.")
        source = self._resolve_document_object(object)
        bounds = self._shape_or_error(source).BoundBox
        cx = float(bounds.Center.x)
        cy = float(bounds.Center.y)
        radius = pitch / 2
        positions = tuple(
            (
                cx + radius * math.cos(math.radians(angle + index * 360 / count)),
                cy + radius * math.sin(math.radians(angle + index * 360 / count)),
            )
            for index in range(count)
        )
        result = self._create_hole_result(
            object,
            diameter,
            positions,
            name,
            "circular_hole_pattern",
        )
        return {
            "name": result.Name,
            "label": result.Label,
            "hole_count": count,
            "pitch_diameter_mm": pitch,
            "valid": True,
        }

    def create_rectangular_sketch(
        self,
        width: float,
        height: float,
        name: str = "AIRectangleSketch",
    ) -> dict[str, Any]:
        checked_width, checked_height = self._positive_values(width, height)
        app, part = self._modules()
        try:
            import Sketcher  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("The FreeCAD Sketcher module is unavailable.") from exc

        def create(document: Any) -> Any:
            checked_name = self._ensure_new_name(document, name)
            sketch = document.addObject("Sketcher::SketchObject", checked_name)
            points = (
                app.Vector(0, 0, 0),
                app.Vector(checked_width, 0, 0),
                app.Vector(checked_width, checked_height, 0),
                app.Vector(0, checked_height, 0),
            )
            sketch.addGeometry(
                [
                    part.LineSegment(points[index], points[(index + 1) % 4])
                    for index in range(4)
                ],
                False,
            )
            sketch.Label = checked_name
            return sketch

        sketch = self._run_transaction(f"create sketch {name}", create)
        return {
            "name": sketch.Name,
            "label": sketch.Label,
            "geometry_count": int(sketch.GeometryCount),
            "closed": True,
            "valid": True,
        }

    def pad_sketch(
        self,
        sketch: str,
        length: float,
        name: str = "AIPad",
    ) -> dict[str, Any]:
        checked_length = self._positive_values(length)[0]
        source = self._resolve_document_object(sketch)
        if source.TypeId != "Sketcher::SketchObject":
            raise ValueError("Pad requires an explicit sketch object.")
        app, part = self._modules()

        def pad(document: Any) -> Any:
            document.recompute()
            if not source.Shape.Wires:
                raise RuntimeError("The sketch does not contain a closed wire.")
            face = part.Face(source.Shape.Wires[0])
            shape = face.extrude(app.Vector(0, 0, checked_length))
            return self._derived_feature(document, name, shape, (source,), "pad")

        result = self._run_transaction(f"pad {source.Name}", pad)
        return {
            "name": result.Name,
            "label": result.Label,
            "length_mm": checked_length,
            "volume_mm3": float(result.Shape.Volume),
            "valid": True,
        }

    def boolean_operation(
        self,
        left: str,
        right: str,
        operation: str,
        name: str = "AIBoolean",
    ) -> dict[str, Any]:
        left_item = self._resolve_document_object(left)
        right_item = self._resolve_document_object(right)
        if left_item is right_item:
            raise ValueError("Boolean operands must be different objects.")
        left_shape = self._shape_or_error(left_item)
        right_shape = self._shape_or_error(right_item)
        operations = {
            "fuse": left_shape.fuse,
            "cut": left_shape.cut,
            "common": left_shape.common,
        }
        if operation not in operations:
            raise ValueError("Unsupported boolean operation.")

        def apply(document: Any) -> Any:
            result_shape = operations[operation](right_shape)
            return self._derived_feature(
                document,
                name,
                result_shape,
                (left_item, right_item),
                f"boolean_{operation}",
            )

        result = self._run_transaction(f"boolean {operation}", apply)
        return {
            "name": result.Name,
            "label": result.Label,
            "operation": operation,
            "volume_mm3": float(result.Shape.Volume),
            "valid": True,
        }

    def _resolve_edge(self, item: Any, reference: str) -> Any:
        shape = self._shape_or_error(item)
        matches = [
            edge
            for edge in shape.Edges
            if self._edge_signature(edge)[0] == reference
        ]
        if len(matches) != 1:
            raise ValueError("The geometric edge reference is stale or ambiguous.")
        return matches[0]

    def fillet_edges(
        self,
        object: str,
        radius: float,
        edge_reference: str,
        name: str = "AIFillet",
    ) -> dict[str, Any]:
        checked_radius = self._positive_values(radius)[0]
        source = self._resolve_document_object(object)
        edge = self._resolve_edge(source, edge_reference)

        def fillet(document: Any) -> Any:
            shape = source.Shape.makeFillet(checked_radius, [edge])
            return self._derived_feature(document, name, shape, (source,), "fillet")

        result = self._run_transaction(f"fillet {source.Name}", fillet)
        return {
            "name": result.Name,
            "label": result.Label,
            "radius_mm": checked_radius,
            "edge_reference": edge_reference,
            "valid": True,
        }

    def chamfer_edges(
        self,
        object: str,
        size: float,
        edge_reference: str,
        name: str = "AIChamfer",
    ) -> dict[str, Any]:
        checked_size = self._positive_values(size)[0]
        source = self._resolve_document_object(object)
        edge = self._resolve_edge(source, edge_reference)

        def chamfer(document: Any) -> Any:
            shape = source.Shape.makeChamfer(checked_size, [edge])
            return self._derived_feature(document, name, shape, (source,), "chamfer")

        result = self._run_transaction(f"chamfer {source.Name}", chamfer)
        return {
            "name": result.Name,
            "label": result.Label,
            "size_mm": checked_size,
            "edge_reference": edge_reference,
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

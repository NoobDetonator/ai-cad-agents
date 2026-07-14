from __future__ import annotations

import math
import re
from typing import Any, Callable


class FreeCadAdapter:
    """Small, explicit boundary around FreeCAD's Python API."""

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
        try:
            import FreeCADGui as Gui
        except ImportError as exc:
            raise RuntimeError("This operation must run inside FreeCAD GUI.") from exc

        selection = []
        for selected in Gui.Selection.getSelectionEx():
            item = selected.Object
            selection.append(
                {
                    "name": item.Name,
                    "label": item.Label,
                    "type_id": item.TypeId,
                    "subelements": list(selected.SubElementNames),
                }
            )
        return {"selection": selection}

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

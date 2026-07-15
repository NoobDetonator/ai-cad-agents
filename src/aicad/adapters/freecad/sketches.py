from __future__ import annotations

from typing import Any


class SketchMixin:
    """Closed sketch profiles consumed by pad, revolve, loft and sweep."""

    @staticmethod
    def _sketcher_module() -> Any:
        try:
            import Sketcher
        except ImportError as exc:
            raise RuntimeError("The FreeCAD Sketcher module is unavailable.") from exc
        return Sketcher

    @classmethod
    def _sketch_or_error(cls, reference: str) -> Any:
        sketch = cls._resolve_document_object(reference)
        if sketch.TypeId != "Sketcher::SketchObject":
            raise ValueError("This operation requires an explicit sketch object.")
        return sketch

    @staticmethod
    def _point_position(position: str, *, allow_center: bool = True) -> int:
        positions = {"start": 1, "end": 2}
        if allow_center:
            positions["center"] = 3
        checked = str(position).strip().lower()
        if checked not in positions:
            expected = "start, end or center" if allow_center else "start or end"
            raise ValueError(f"Sketch point position must be {expected}.")
        return positions[checked]

    @staticmethod
    def _geometry_index(sketch: Any, index: int) -> int:
        checked = int(index)
        if isinstance(index, bool) or checked != index or not 0 <= checked < sketch.GeometryCount:
            raise ValueError("Sketch geometry index is out of range.")
        return checked

    @staticmethod
    def _constraint_index(sketch: Any, index: int) -> int:
        checked = int(index)
        count = len(sketch.Constraints)
        if isinstance(index, bool) or checked != index or not 0 <= checked < count:
            raise ValueError("Sketch constraint index is out of range.")
        return checked

    @classmethod
    def _geometry_index_list(cls, sketch: Any, indices: list[int]) -> list[int]:
        if not isinstance(indices, list) or not indices:
            raise ValueError("At least one sketch geometry index is required.")
        checked = [cls._geometry_index(sketch, index) for index in indices]
        if len(set(checked)) != len(checked):
            raise ValueError("Sketch geometry indices must be unique.")
        return checked

    @staticmethod
    def _sketch_result(sketch: Any, **extra: Any) -> dict[str, Any]:
        shape = getattr(sketch, "Shape", None)
        wires = [] if shape is None or shape.isNull() else list(shape.Wires)
        result = {
            "name": sketch.Name,
            "label": sketch.Label,
            "geometry_count": int(sketch.GeometryCount),
            "constraint_count": len(sketch.Constraints),
            "closed_wire_count": sum(1 for wire in wires if wire.isClosed()),
            "open_wire_count": sum(1 for wire in wires if not wire.isClosed()),
            "fully_constrained": bool(getattr(sketch, "FullyConstrained", False)),
            "valid": shape is None or shape.isNull() or bool(shape.isValid()),
        }
        result.update(extra)
        return result

    def _mutate_sketch(self, sketch: Any, title: str, operation: Any) -> Any:
        def mutate(document: Any) -> None:
            operation(document)
            document.recompute()
            messages = str(getattr(sketch, "SolverMessages", "")).casefold()
            if "over-constrained" in messages or "redundant constraint" in messages:
                raise RuntimeError("The sketch solver rejected an over-constrained result.")
            return None

        self._run_transaction(title, mutate, recent_names=(sketch.Name,))
        return sketch

    def create_empty_sketch(
        self,
        plane: str = "xy",
        offset: float = 0,
        name: str = "AISketch",
    ) -> dict[str, Any]:
        checked_plane = str(plane).strip().lower()
        if checked_plane not in {"xy", "xz", "yz"}:
            raise ValueError("Sketch plane must be xy, xz or yz.")
        checked_offset = self._finite_float(offset)
        if checked_offset is None:
            raise ValueError("Sketch plane offset must be finite.")
        checked_name = self._validated_object_name(name)
        app, _ = self._modules()

        def create(document: Any) -> None:
            self._ensure_new_name(document, checked_name)
            sketch = document.addObject("Sketcher::SketchObject", checked_name)
            if checked_plane == "xz":
                sketch.Placement = app.Placement(
                    app.Vector(0, -checked_offset, 0),
                    app.Rotation(app.Vector(1, 0, 0), 90),
                )
            elif checked_plane == "yz":
                sketch.Placement = app.Placement(
                    app.Vector(checked_offset, 0, 0),
                    app.Rotation(app.Vector(0, 1, 0), 90),
                )
            else:
                sketch.Placement = app.Placement(
                    app.Vector(0, 0, checked_offset), app.Rotation()
                )
            sketch.Label = checked_name
            sketch.addProperty("App::PropertyString", "AICadPlane", "Sketch")
            sketch.AICadPlane = checked_plane
            sketch.addProperty("App::PropertyLength", "AICadPlaneOffset", "Sketch")
            sketch.AICadPlaneOffset = checked_offset
            return None

        self._run_transaction(
            f"create empty sketch {checked_name}",
            create,
            recent_names=(checked_name,),
        )
        sketch = self._active_document().getObject(checked_name)
        return self._sketch_result(
            sketch, plane=checked_plane, offset_mm=checked_offset
        )

    def create_rectangular_sketch(
        self,
        width: float,
        height: float,
        name: str = "AIRectangleSketch",
    ) -> dict[str, Any]:
        checked_width, checked_height = self._positive_values(width, height)
        app, part = self._modules()
        try:
            import Sketcher
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
            sketch.addConstraint(
                [
                    Sketcher.Constraint("Coincident", 0, 2, 1, 1),
                    Sketcher.Constraint("Coincident", 1, 2, 2, 1),
                    Sketcher.Constraint("Coincident", 2, 2, 3, 1),
                    Sketcher.Constraint("Coincident", 3, 2, 0, 1),
                    Sketcher.Constraint("Horizontal", 0),
                    Sketcher.Constraint("Horizontal", 2),
                    Sketcher.Constraint("Vertical", 1),
                    Sketcher.Constraint("Vertical", 3),
                    Sketcher.Constraint("Coincident", 0, 1, -1, 1),
                    Sketcher.Constraint("DistanceX", 0, 1, 0, 2, checked_width),
                    Sketcher.Constraint("DistanceY", 1, 1, 1, 2, checked_height),
                ]
            )
            sketch.Label = checked_name
            return sketch

        sketch = self._run_transaction(f"create sketch {name}", create)
        return {
            "name": sketch.Name,
            "label": sketch.Label,
            "geometry_count": int(sketch.GeometryCount),
            "closed": True,
            "fully_constrained": bool(getattr(sketch, "FullyConstrained", False)),
            "valid": True,
        }

    def create_circular_sketch(
        self,
        diameter: float,
        name: str = "AICircleSketch",
    ) -> dict[str, Any]:
        checked_diameter = self._positive_values(diameter)[0]
        app, part = self._modules()
        try:
            import Sketcher
        except ImportError as exc:
            raise RuntimeError("The FreeCAD Sketcher module is unavailable.") from exc

        def create(document: Any) -> Any:
            checked_name = self._ensure_new_name(document, name)
            sketch = document.addObject("Sketcher::SketchObject", checked_name)
            sketch.addGeometry(
                part.Circle(
                    app.Vector(0, 0, 0),
                    app.Vector(0, 0, 1),
                    checked_diameter / 2,
                ),
                False,
            )
            sketch.addConstraint(
                [
                    Sketcher.Constraint("Coincident", 0, 3, -1, 1),
                    Sketcher.Constraint("Diameter", 0, checked_diameter),
                ]
            )
            sketch.Label = checked_name
            return sketch

        sketch = self._run_transaction(f"create sketch {name}", create)
        return {
            "name": sketch.Name,
            "label": sketch.Label,
            "diameter_mm": checked_diameter,
            "closed": True,
            "fully_constrained": bool(getattr(sketch, "FullyConstrained", False)),
            "valid": True,
        }

    def _closed_sketch_wire(self, reference: str) -> tuple[Any, Any]:
        source = self._sketch_or_error(reference)
        if not source.Shape.Wires:
            raise RuntimeError("The sketch does not contain a closed wire.")
        wire = source.Shape.Wires[0]
        if not wire.isClosed():
            raise RuntimeError("The sketch wire is not closed.")
        return source, wire

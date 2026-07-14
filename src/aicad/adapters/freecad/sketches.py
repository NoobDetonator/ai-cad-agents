from __future__ import annotations

from typing import Any


class SketchMixin:
    """Closed sketch profiles consumed by pad, revolve, loft and sweep."""

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
        source = self._resolve_document_object(reference)
        if source.TypeId != "Sketcher::SketchObject":
            raise ValueError("This operation requires an explicit sketch object.")
        if not source.Shape.Wires:
            raise RuntimeError("The sketch does not contain a closed wire.")
        wire = source.Shape.Wires[0]
        if not wire.isClosed():
            raise RuntimeError("The sketch wire is not closed.")
        return source, wire

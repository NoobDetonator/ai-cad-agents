from __future__ import annotations

import math
from typing import Any


class SketchConstraintMixin:
    """Sketch constraints, solver-safe dimension edits and structured reads."""

    def add_sketch_geometric_constraint(
        self,
        sketch: str,
        constraint_type: str,
        first_geometry: int,
        second_geometry: int | None = None,
        first_position: str | None = None,
        second_position: str | None = None,
    ) -> dict[str, Any]:
        target = self._sketch_or_error(sketch)
        first = self._anchor_geometry_index(target, first_geometry)
        checked_type = str(constraint_type).strip().lower()
        sketcher = self._sketcher_module()
        unary = {"horizontal": "Horizontal", "vertical": "Vertical", "block": "Block"}
        binary = {
            "parallel": "Parallel",
            "perpendicular": "Perpendicular",
            "tangent": "Tangent",
            "equal": "Equal",
        }
        if first < 0 and checked_type not in {"coincident", "concentric"}:
            raise ValueError(
                "The sketch origin point only supports coincident and "
                "concentric constraints."
            )
        if checked_type in unary:
            constraint = sketcher.Constraint(unary[checked_type], first)
        elif checked_type in binary:
            if second_geometry is None:
                raise ValueError(f"{checked_type} requires second_geometry.")
            second = self._geometry_index(target, second_geometry)
            if second == first:
                raise ValueError("A binary sketch constraint requires two geometries.")
            constraint = sketcher.Constraint(binary[checked_type], first, second)
        elif checked_type == "coincident":
            if second_geometry is None or first_position is None or second_position is None:
                raise ValueError(
                    "Coincident requires second_geometry and both point positions."
                )
            second = self._anchor_geometry_index(target, second_geometry)
            if second == first:
                raise ValueError("A binary sketch constraint requires two geometries.")
            constraint = sketcher.Constraint(
                "Coincident",
                first,
                self._origin_point_position(first, first_position),
                second,
                self._origin_point_position(second, second_position),
            )
        elif checked_type == "concentric":
            if second_geometry is None:
                raise ValueError("Concentric requires second_geometry.")
            second = self._anchor_geometry_index(target, second_geometry)
            if second == first:
                raise ValueError("A binary sketch constraint requires two geometries.")
            constraint = sketcher.Constraint(
                "Coincident",
                first,
                1 if first < 0 else 3,
                second,
                1 if second < 0 else 3,
            )
        elif checked_type == "point_on_object":
            if second_geometry is None or first_position is None:
                raise ValueError(
                    "Point-on-object requires second_geometry and first_position."
                )
            second = self._geometry_index(target, second_geometry)
            constraint = sketcher.Constraint(
                "PointOnObject",
                first,
                self._point_position(first_position),
                second,
            )
        else:
            raise ValueError("Unsupported sketch geometric constraint type.")
        added = -1

        def add(_: Any) -> None:
            nonlocal added
            added = int(target.addConstraint(constraint))
            if added < 0:
                raise RuntimeError("FreeCAD rejected the sketch constraint.")
            return None

        self._mutate_sketch(target, f"constrain {target.Name}", add)
        return self._sketch_result(
            target,
            added_constraint=added,
            constraint_type=checked_type,
        )

    def add_sketch_dimensional_constraint(
        self,
        sketch: str,
        constraint_type: str,
        geometry: int,
        value: float,
        position: str | None = None,
        second_geometry: int | None = None,
        second_position: str | None = None,
    ) -> dict[str, Any]:
        checked_value = self._positive_values(value)[0]
        target = self._sketch_or_error(sketch)
        first = self._anchor_geometry_index(target, geometry)
        checked_type = str(constraint_type).strip().lower()
        if first < 0 and checked_type not in {"distance", "distance_x", "distance_y"}:
            raise ValueError(
                "The sketch origin point only supports distance dimensions."
            )
        sketcher = self._sketcher_module()
        if checked_type == "length":
            constraint = sketcher.Constraint("Distance", first, checked_value)
            unit = "mm"
        elif checked_type == "radius":
            constraint = sketcher.Constraint("Radius", first, checked_value)
            unit = "mm"
        elif checked_type == "diameter":
            constraint = sketcher.Constraint("Diameter", first, checked_value)
            unit = "mm"
        elif checked_type == "angle":
            if checked_value >= 360:
                raise ValueError("A sketch angle constraint must be below 360 degrees.")
            constraint = sketcher.Constraint("Angle", first, math.radians(checked_value))
            unit = "deg"
        elif checked_type in {"distance", "distance_x", "distance_y"}:
            if position is None:
                raise ValueError(f"{checked_type} requires a first point position.")
            first_pos = self._origin_point_position(first, position)
            freecad_type = {
                "distance": "Distance",
                "distance_x": "DistanceX",
                "distance_y": "DistanceY",
            }[checked_type]
            if second_geometry is None:
                constraint = sketcher.Constraint(
                    freecad_type, first, first_pos, checked_value
                )
            else:
                if second_position is None:
                    raise ValueError(
                        f"{checked_type} between points requires second_position."
                    )
                second = self._anchor_geometry_index(target, second_geometry)
                if second == first:
                    raise ValueError(
                        "A distance between points requires two geometries."
                    )
                constraint = sketcher.Constraint(
                    freecad_type,
                    first,
                    first_pos,
                    second,
                    self._origin_point_position(second, second_position),
                    checked_value,
                )
            unit = "mm"
        else:
            raise ValueError("Unsupported sketch dimensional constraint type.")
        added = -1

        def add(_: Any) -> None:
            nonlocal added
            added = int(target.addConstraint(constraint))
            if added < 0:
                raise RuntimeError("FreeCAD rejected the dimensional constraint.")
            return None

        self._mutate_sketch(target, f"dimension {target.Name}", add)
        return self._sketch_result(
            target,
            added_constraint=added,
            constraint_type=checked_type,
            value=checked_value,
            unit=unit,
        )

    def set_sketch_constraint_value(
        self,
        sketch: str,
        constraint_index: int,
        value: float,
        unit: str = "mm",
    ) -> dict[str, Any]:
        checked_value = self._positive_values(value)[0]
        checked_unit = str(unit).strip().lower()
        if checked_unit not in {"mm", "deg"}:
            raise ValueError("Sketch constraint unit must be mm or deg.")
        target = self._sketch_or_error(sketch)
        index = self._constraint_index(target, constraint_index)
        app, _ = self._modules()

        def change(_: Any) -> None:
            target.setDatum(index, app.Units.Quantity(f"{checked_value} {checked_unit}"))
            return None

        self._mutate_sketch(target, f"change constraint in {target.Name}", change)
        return self._sketch_result(
            target,
            changed_constraint=index,
            value=checked_value,
            unit=checked_unit,
        )

    def set_sketch_constraint_driving(
        self,
        sketch: str,
        constraint_index: int,
        driving: bool,
    ) -> dict[str, Any]:
        if not isinstance(driving, bool):
            raise ValueError("Driving must be a boolean value.")
        target = self._sketch_or_error(sketch)
        index = self._constraint_index(target, constraint_index)

        def change(_: Any) -> None:
            result = target.setDriving(index, driving)
            if result is not None and int(result) < 0:
                raise RuntimeError("FreeCAD could not change the constraint mode.")
            return None

        self._mutate_sketch(target, f"change constraint mode in {target.Name}", change)
        return self._sketch_result(
            target, changed_constraint=index, driving=driving
        )

    def delete_sketch_constraint(
        self, sketch: str, constraint_indices: list[int]
    ) -> dict[str, Any]:
        target = self._sketch_or_error(sketch)
        if not isinstance(constraint_indices, list) or not constraint_indices:
            raise ValueError("At least one sketch constraint index is required.")
        indices = [self._constraint_index(target, index) for index in constraint_indices]
        if len(set(indices)) != len(indices):
            raise ValueError("Sketch constraint indices must be unique.")

        def delete(_: Any) -> None:
            for index in sorted(indices, reverse=True):
                target.delConstraint(index)
            return None

        self._mutate_sketch(target, f"delete constraints from {target.Name}", delete)
        return self._sketch_result(target, deleted_constraints=sorted(indices))

    @staticmethod
    def _vector_payload(vector: Any) -> list[float]:
        return [float(vector.x), float(vector.y)]

    def _sketch_geometry_payload(self, sketch: Any, index: int, geometry: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "index": index,
            "type": type(geometry).__name__,
            "construction": bool(sketch.getConstruction(index)),
        }
        if hasattr(geometry, "StartPoint"):
            payload["start_mm"] = self._vector_payload(geometry.StartPoint)
        if hasattr(geometry, "EndPoint"):
            payload["end_mm"] = self._vector_payload(geometry.EndPoint)
        if hasattr(geometry, "Center"):
            payload["center_mm"] = self._vector_payload(geometry.Center)
        if hasattr(geometry, "Radius"):
            payload["radius_mm"] = float(geometry.Radius)
        if hasattr(geometry, "MajorRadius"):
            payload["major_radius_mm"] = float(geometry.MajorRadius)
        if hasattr(geometry, "MinorRadius"):
            payload["minor_radius_mm"] = float(geometry.MinorRadius)
        if hasattr(geometry, "FirstParameter"):
            payload["first_parameter"] = float(geometry.FirstParameter)
        if hasattr(geometry, "LastParameter"):
            payload["last_parameter"] = float(geometry.LastParameter)
        return payload

    def _sketch_constraint_payload(
        self, sketch: Any, index: int, constraint: Any
    ) -> dict[str, Any]:
        try:
            driving = bool(sketch.getDriving(index))
        except (IndexError, RuntimeError, ValueError):
            driving = bool(getattr(constraint, "isDriving", True))
        try:
            active = bool(sketch.getActive(index))
        except (IndexError, RuntimeError, ValueError):
            active = bool(getattr(constraint, "isActive", True))
        payload = {
            "index": index,
            "type": str(constraint.Type),
            "first_geometry": int(getattr(constraint, "First", -2000)),
            "first_position": int(getattr(constraint, "FirstPos", 0)),
            "second_geometry": int(getattr(constraint, "Second", -2000)),
            "second_position": int(getattr(constraint, "SecondPos", 0)),
            "driving": driving,
            "active": active,
        }
        value = getattr(constraint, "Value", None)
        if value is not None:
            try:
                payload["value"] = float(value)
            except (TypeError, ValueError):
                payload["value"] = str(value)
        label = str(getattr(constraint, "Name", ""))
        if label:
            payload["name"] = label
        return payload

    def get_sketch_info(self, sketch: str) -> dict[str, Any]:
        target = self._sketch_or_error(sketch)
        summary = self._sketch_result(target)
        summary.update(
            {
                "plane": str(getattr(target, "AICadPlane", "custom")),
                "offset_mm": float(getattr(target, "AICadPlaneOffset", 0)),
                "geometry": [
                    self._sketch_geometry_payload(target, index, geometry)
                    for index, geometry in enumerate(target.Geometry)
                ],
                "constraints": [
                    self._sketch_constraint_payload(target, index, constraint)
                    for index, constraint in enumerate(target.Constraints)
                ],
                "external_geometry_count": len(target.ExternalGeometry),
                "solver_messages": str(getattr(target, "SolverMessages", "")),
            }
        )
        return summary

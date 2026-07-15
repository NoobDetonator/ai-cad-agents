from __future__ import annotations

import math
from typing import Any


_Point = tuple[float, float, float]


def _parse_path_points(points: Any) -> tuple[_Point, ...]:
    if not isinstance(points, list) or not 2 <= len(points) <= 16:
        raise ValueError("A sweep path requires between 2 and 16 points.")
    parsed: list[_Point] = []
    for raw in points:
        parts = str(raw).split(",")
        if len(parts) != 3:
            raise ValueError(
                "Each path point must be 'x,y,z' in millimeters."
            )
        try:
            values = tuple(float(part) for part in parts)
        except ValueError as exc:
            raise ValueError(
                "Each path point must be 'x,y,z' in millimeters."
            ) from exc
        if any(not math.isfinite(value) for value in values):
            raise ValueError("Path coordinates must be finite.")
        parsed.append(values)
    if parsed[0] == parsed[-1]:
        raise ValueError("The sweep path must be open, not closed.")
    return tuple(parsed)


def _vector_between(start: _Point, end: _Point) -> _Point:
    return (end[0] - start[0], end[1] - start[1], end[2] - start[2])


def _length(vector: _Point) -> float:
    return math.sqrt(sum(value * value for value in vector))


def _unit(vector: _Point) -> _Point:
    size = _length(vector)
    return (vector[0] / size, vector[1] / size, vector[2] / size)


def _dot(left: _Point, right: _Point) -> float:
    return sum(a * b for a, b in zip(left, right))


def _offset(point: _Point, direction: _Point, distance: float) -> _Point:
    return (
        point[0] + direction[0] * distance,
        point[1] + direction[1] * distance,
        point[2] + direction[2] * distance,
    )


def _planned_corner_arcs(
    points: tuple[_Point, ...],
    corner_radius: float,
) -> tuple[dict[str, _Point] | None, ...]:
    """Compute one tangent arc per interior corner, without FreeCAD.

    Returns one entry per corner: ``None`` for collinear corners (no arc
    needed) or the arc's start, sag midpoint and end points.
    """

    segment_lengths = [
        _length(_vector_between(points[index], points[index + 1]))
        for index in range(len(points) - 1)
    ]
    if any(length < 1e-6 for length in segment_lengths):
        raise ValueError("Consecutive path points must be distinct.")

    arcs: list[dict[str, _Point] | None] = []
    for index in range(1, len(points) - 1):
        corner = points[index]
        toward_previous = _unit(_vector_between(corner, points[index - 1]))
        toward_next = _unit(_vector_between(corner, points[index + 1]))
        cosine = max(-1.0, min(1.0, _dot(toward_previous, toward_next)))
        angle = math.acos(cosine)
        if angle < math.radians(1):
            raise ValueError("The sweep path folds back on itself.")
        if angle > math.radians(179):
            arcs.append(None)
            continue
        if corner_radius <= 0:
            arcs.append(None)
            continue
        trim = corner_radius / math.tan(angle / 2)
        for adjacent in (segment_lengths[index - 1], segment_lengths[index]):
            half = adjacent / 2
            # An exact fit lands a few ulps over half (a 90 degree corner gives
            # trim = radius/tan(45) = radius * 1.0000000000000002), so a bare
            # ">" would reject radii that do fit.
            if trim > half and not math.isclose(trim, half, rel_tol=1e-9):
                raise ValueError(
                    f"A corner radius of {corner_radius:g} mm needs "
                    f"{trim:g} mm of straight run each side of the corner, "
                    f"but it must fit in half of the adjacent "
                    f"{adjacent:g} mm segment ({half:g} mm). Lengthen the "
                    f"segment or reduce the radius."
                )
        bisector = _unit(
            tuple(a + b for a, b in zip(toward_previous, toward_next))
        )
        center_distance = corner_radius / math.sin(angle / 2)
        center = _offset(corner, bisector, center_distance)
        arcs.append(
            {
                "start": _offset(corner, toward_previous, trim),
                "middle": _offset(center, bisector, -corner_radius),
                "end": _offset(corner, toward_next, trim),
            }
        )
    return tuple(arcs)


class SweepMixin:
    """Line/arc trajectories and controlled profile sweeps along them."""

    def create_sweep_path(
        self,
        points: list[str],
        corner_radius: float = 0,
        name: str = "AISweepPath",
    ) -> dict[str, Any]:
        checked_points = _parse_path_points(points)
        checked_radius = self._finite_float(corner_radius)
        if checked_radius is None or checked_radius < 0:
            raise ValueError("The corner radius cannot be negative.")
        arcs = _planned_corner_arcs(checked_points, checked_radius)
        app, part = self._modules()

        def create(document: Any) -> Any:
            checked_name = self._ensure_new_name(document, name)
            edges = []
            cursor = app.Vector(*checked_points[0])
            for index, arc in enumerate(arcs, start=1):
                corner = app.Vector(*checked_points[index])
                if arc is None:
                    edges.append(part.LineSegment(cursor, corner).toShape())
                    cursor = corner
                    continue
                start = app.Vector(*arc["start"])
                if (start - cursor).Length > 1e-9:
                    edges.append(part.LineSegment(cursor, start).toShape())
                edges.append(
                    part.Arc(
                        start,
                        app.Vector(*arc["middle"]),
                        app.Vector(*arc["end"]),
                    ).toShape()
                )
                cursor = app.Vector(*arc["end"])
            final = app.Vector(*checked_points[-1])
            if (final - cursor).Length > 1e-9:
                edges.append(part.LineSegment(cursor, final).toShape())
            wire = part.Wire(edges)
            if wire.isNull() or not wire.isValid() or wire.isClosed():
                raise RuntimeError("FreeCAD did not produce a valid open path.")
            result = document.addObject("Part::Feature", checked_name)
            result.Label = checked_name
            result.Shape = wire
            result.addProperty("App::PropertyString", "FeatureKind", "AI CAD")
            result.FeatureKind = "sweep_path"
            return result

        result = self._run_transaction(f"create sweep path {name}", create)
        return {
            "name": result.Name,
            "label": result.Label,
            "point_count": len(checked_points),
            "corner_radius_mm": checked_radius,
            "length_mm": float(result.Shape.Length),
            "valid": True,
        }

    def sweep_sketch(
        self,
        profile: str,
        path: str,
        name: str = "AISweep",
    ) -> dict[str, Any]:
        source, profile_wire = self._closed_sketch_wire(profile)
        path_item = self._resolve_document_object(path)
        if getattr(path_item, "FeatureKind", "") != "sweep_path":
            raise ValueError(
                "The sweep path must be created by cad.create_sweep_path."
            )
        app, part = self._modules()

        def sweep(document: Any) -> Any:
            document.recompute()
            path_wire = part.Wire(path_item.Shape.Edges)
            first_edge = path_wire.OrderedEdges[0]
            start_point = first_edge.valueAt(first_edge.FirstParameter)
            direction = first_edge.tangentAt(first_edge.FirstParameter)
            placed_profile = source.Shape.Wires[0].copy()
            z_axis = app.Vector(0, 0, 1)
            angle = math.degrees(z_axis.getAngle(direction))
            if angle > 1e-9:
                axis = z_axis.cross(direction)
                if axis.Length < 1e-9:
                    axis = app.Vector(1, 0, 0)
                placed_profile.rotate(app.Vector(0, 0, 0), axis, angle)
            placed_profile.translate(start_point)
            shape = path_wire.makePipeShell([placed_profile], True, False)
            if not shape.Solids or float(shape.Volume) <= 0:
                raise RuntimeError("The sweep did not produce a solid.")
            return self._derived_feature(
                document,
                name,
                shape,
                (source, path_item),
                "sweep",
            )

        result = self._run_transaction(f"sweep {source.Name}", sweep)
        return {
            "name": result.Name,
            "label": result.Label,
            "path_length_mm": float(path_item.Shape.Length),
            "volume_mm3": float(result.Shape.Volume),
            "valid": True,
        }

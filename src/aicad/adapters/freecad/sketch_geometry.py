from __future__ import annotations

import math
from typing import Any


class SketchGeometryMixin:
    """Transactional creation and editing of sketch geometry."""

    def _finite_sketch_values(self, *values: float) -> tuple[float, ...]:
        checked = tuple(self._finite_float(value) for value in values)
        if any(value is None for value in checked):
            raise ValueError("Sketch coordinates and angles must be finite.")
        return tuple(float(value) for value in checked)

    def _parse_sketch_points(self, points: list[str]) -> list[tuple[float, float]]:
        if not isinstance(points, list) or not 2 <= len(points) <= 256:
            raise ValueError("A sketch polyline requires between 2 and 256 points.")
        parsed = []
        for value in points:
            parts = str(value).split(",")
            if len(parts) != 2:
                raise ValueError("Each sketch point must use x,y format.")
            parsed.append(self._finite_sketch_values(parts[0], parts[1]))
        for left, right in zip(parsed, parsed[1:]):
            if math.dist(left, right) <= 1e-9:
                raise ValueError("Consecutive sketch points must be distinct.")
        return parsed

    def _add_sketch_geometry(
        self,
        sketch: Any,
        geometries: list[Any],
        construction: bool,
        title: str,
        **extra: Any,
    ) -> dict[str, Any]:
        if not isinstance(construction, bool):
            raise ValueError("Construction must be a boolean value.")
        before = int(sketch.GeometryCount)

        def add(_: Any) -> None:
            sketch.addGeometry(geometries, construction)
            return None

        self._mutate_sketch(sketch, title, add)
        added = list(range(before, int(sketch.GeometryCount)))
        return self._sketch_result(
            sketch,
            added_geometry=added,
            construction=construction,
            **extra,
        )

    def add_sketch_line(
        self,
        sketch: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        construction: bool = False,
    ) -> dict[str, Any]:
        x1c, y1c, x2c, y2c = self._finite_sketch_values(x1, y1, x2, y2)
        if math.hypot(x2c - x1c, y2c - y1c) <= 1e-9:
            raise ValueError("A sketch line requires two distinct points.")
        target = self._sketch_or_error(sketch)
        app, part = self._modules()
        geometry = part.LineSegment(app.Vector(x1c, y1c, 0), app.Vector(x2c, y2c, 0))
        return self._add_sketch_geometry(
            target, [geometry], construction, f"add line to {target.Name}"
        )

    def add_sketch_polyline(
        self,
        sketch: str,
        points: list[str],
        closed: bool = False,
        construction: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(closed, bool):
            raise ValueError("Closed must be a boolean value.")
        parsed = self._parse_sketch_points(points)
        if closed and math.dist(parsed[0], parsed[-1]) <= 1e-9:
            parsed = parsed[:-1]
        if closed and len(parsed) < 3:
            raise ValueError("A closed sketch polyline requires at least three points.")
        target = self._sketch_or_error(sketch)
        app, part = self._modules()
        pairs = list(zip(parsed, parsed[1:]))
        if closed:
            pairs.append((parsed[-1], parsed[0]))
        geometries = [
            part.LineSegment(app.Vector(*left, 0), app.Vector(*right, 0))
            for left, right in pairs
        ]
        return self._add_sketch_geometry(
            target,
            geometries,
            construction,
            f"add polyline to {target.Name}",
            closed=closed,
        )

    def add_sketch_circle(
        self,
        sketch: str,
        center_x: float,
        center_y: float,
        radius: float,
        construction: bool = False,
    ) -> dict[str, Any]:
        cx, cy = self._finite_sketch_values(center_x, center_y)
        checked_radius = self._positive_values(radius)[0]
        target = self._sketch_or_error(sketch)
        app, part = self._modules()
        geometry = part.Circle(
            app.Vector(cx, cy, 0), app.Vector(0, 0, 1), checked_radius
        )
        return self._add_sketch_geometry(
            target,
            [geometry],
            construction,
            f"add circle to {target.Name}",
            radius_mm=checked_radius,
        )

    def add_sketch_arc(
        self,
        sketch: str,
        center_x: float,
        center_y: float,
        radius: float,
        start_angle: float,
        end_angle: float,
        construction: bool = False,
    ) -> dict[str, Any]:
        cx, cy, start, end = self._finite_sketch_values(
            center_x, center_y, start_angle, end_angle
        )
        checked_radius = self._positive_values(radius)[0]
        sweep = (end - start) % 360
        if sweep <= 1e-7:
            raise ValueError("A sketch arc sweep must be between 0 and 360 degrees.")
        target = self._sketch_or_error(sketch)
        app, part = self._modules()
        circle = part.Circle(
            app.Vector(cx, cy, 0), app.Vector(0, 0, 1), checked_radius
        )
        start_rad = math.radians(start)
        geometry = part.ArcOfCircle(circle, start_rad, start_rad + math.radians(sweep))
        return self._add_sketch_geometry(
            target,
            [geometry],
            construction,
            f"add arc to {target.Name}",
            sweep_angle_deg=sweep,
        )

    def add_sketch_ellipse(
        self,
        sketch: str,
        center_x: float,
        center_y: float,
        major_radius: float,
        minor_radius: float,
        rotation: float = 0,
        construction: bool = False,
    ) -> dict[str, Any]:
        cx, cy, checked_rotation = self._finite_sketch_values(
            center_x, center_y, rotation
        )
        major, minor = self._positive_values(major_radius, minor_radius)
        if major <= minor:
            raise ValueError("Ellipse major radius must exceed its minor radius.")
        target = self._sketch_or_error(sketch)
        app, part = self._modules()
        center = app.Vector(cx, cy, 0)
        geometry = part.Ellipse(center, major, minor)
        if checked_rotation:
            geometry.AngleXU = math.radians(checked_rotation)
        return self._add_sketch_geometry(
            target,
            [geometry],
            construction,
            f"add ellipse to {target.Name}",
            major_radius_mm=major,
            minor_radius_mm=minor,
            rotation_deg=checked_rotation,
        )

    def add_sketch_rectangle(
        self,
        sketch: str,
        x: float,
        y: float,
        width: float,
        height: float,
        rotation: float = 0,
        construction: bool = False,
    ) -> dict[str, Any]:
        x0, y0, checked_rotation = self._finite_sketch_values(x, y, rotation)
        checked_width, checked_height = self._positive_values(width, height)
        angle = math.radians(checked_rotation)
        cosine, sine = math.cos(angle), math.sin(angle)

        def rotate(local_x: float, local_y: float) -> tuple[float, float]:
            return (
                x0 + local_x * cosine - local_y * sine,
                y0 + local_x * sine + local_y * cosine,
            )

        points = [
            rotate(0, 0),
            rotate(checked_width, 0),
            rotate(checked_width, checked_height),
            rotate(0, checked_height),
        ]
        target = self._sketch_or_error(sketch)
        app, part = self._modules()
        geometries = [
            part.LineSegment(app.Vector(*points[index], 0), app.Vector(*points[(index + 1) % 4], 0))
            for index in range(4)
        ]
        sketcher = self._sketcher_module()
        before = int(target.GeometryCount)

        def add(_: Any) -> None:
            target.addGeometry(geometries, construction)
            # A rectangle must stay a closed rectangle under the solver:
            # corner coincidences always, axis alignment when unrotated —
            # the same constraints the GUI rectangle tool creates. Without
            # them, driving one dimension tears the wire open.
            constraints = [
                sketcher.Constraint(
                    "Coincident", before + index, 2, before + (index + 1) % 4, 1
                )
                for index in range(4)
            ]
            if math.isclose(checked_rotation % 360, 0.0):
                constraints.extend(
                    (
                        sketcher.Constraint("Horizontal", before),
                        sketcher.Constraint("Horizontal", before + 2),
                        sketcher.Constraint("Vertical", before + 1),
                        sketcher.Constraint("Vertical", before + 3),
                    )
                )
            target.addConstraint(constraints)
            return None

        self._mutate_sketch(target, f"add rectangle to {target.Name}", add)
        added = list(range(before, int(target.GeometryCount)))
        return self._sketch_result(
            target,
            added_geometry=added,
            construction=construction,
            closed=True,
            width_mm=checked_width,
            height_mm=checked_height,
            rotation_deg=checked_rotation,
        )

    def add_sketch_slot(
        self,
        sketch: str,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        width: float,
        construction: bool = False,
    ) -> dict[str, Any]:
        sx, sy, ex, ey = self._finite_sketch_values(start_x, start_y, end_x, end_y)
        checked_width = self._positive_values(width)[0]
        dx, dy = ex - sx, ey - sy
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            raise ValueError("A sketch slot requires distinct center points.")
        radius = checked_width / 2
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux
        start_top = (sx + nx * radius, sy + ny * radius)
        end_top = (ex + nx * radius, ey + ny * radius)
        start_bottom = (sx - nx * radius, sy - ny * radius)
        end_bottom = (ex - nx * radius, ey - ny * radius)
        theta = math.atan2(dy, dx)
        target = self._sketch_or_error(sketch)
        app, part = self._modules()
        geometries = [
            part.LineSegment(app.Vector(*start_top, 0), app.Vector(*end_top, 0)),
            part.ArcOfCircle(
                part.Circle(app.Vector(ex, ey, 0), app.Vector(0, 0, 1), radius),
                theta - math.pi / 2,
                theta + math.pi / 2,
            ),
            part.LineSegment(app.Vector(*start_bottom, 0), app.Vector(*end_bottom, 0)),
            part.ArcOfCircle(
                part.Circle(app.Vector(sx, sy, 0), app.Vector(0, 0, 1), radius),
                theta + math.pi / 2,
                theta + 3 * math.pi / 2,
            ),
        ]
        return self._add_sketch_geometry(
            target,
            geometries,
            construction,
            f"add slot to {target.Name}",
            closed=True,
            center_distance_mm=length,
            width_mm=checked_width,
        )

    def add_sketch_regular_polygon(
        self,
        sketch: str,
        center_x: float,
        center_y: float,
        radius: float,
        sides: int,
        rotation: float = 0,
        construction: bool = False,
    ) -> dict[str, Any]:
        cx, cy, checked_rotation = self._finite_sketch_values(
            center_x, center_y, rotation
        )
        checked_radius = self._positive_values(radius)[0]
        count = int(sides)
        if isinstance(sides, bool) or count != sides or not 3 <= count <= 128:
            raise ValueError("A regular sketch polygon requires 3 to 128 sides.")
        points = [
            (
                cx + checked_radius * math.cos(math.radians(checked_rotation + index * 360 / count)),
                cy + checked_radius * math.sin(math.radians(checked_rotation + index * 360 / count)),
            )
            for index in range(count)
        ]
        target = self._sketch_or_error(sketch)
        app, part = self._modules()
        geometries = [
            part.LineSegment(app.Vector(*points[index], 0), app.Vector(*points[(index + 1) % count], 0))
            for index in range(count)
        ]
        return self._add_sketch_geometry(
            target,
            geometries,
            construction,
            f"add polygon to {target.Name}",
            closed=True,
            sides=count,
            radius_mm=checked_radius,
        )

    def add_sketch_external_geometry(
        self,
        sketch: str,
        object: str,
        edge_reference: str,
    ) -> dict[str, Any]:
        target = self._sketch_or_error(sketch)
        source = self._resolve_document_object(object)
        if source is target:
            raise ValueError("A sketch cannot use itself as external geometry.")
        edge = self._resolve_edge(source, edge_reference)
        edge_index = next(
            (
                index
                for index, candidate in enumerate(source.Shape.Edges, start=1)
                if candidate.isSame(edge)
            ),
            None,
        )
        if edge_index is None:
            raise ValueError("The external edge could not be resolved.")
        external_index = -1
        external_count = len(target.ExternalGeometry)

        def add(_: Any) -> None:
            nonlocal external_index
            result = target.addExternal(source.Name, f"Edge{edge_index}")
            # FreeCAD 1.1 performs the insertion but returns ``None``.  Older
            # releases return the negative GeoId directly.  External geometry
            # starts at -3 because -1 and -2 identify the sketch axes.
            external_index = (
                int(result)
                if isinstance(result, (int, float)) and not isinstance(result, bool)
                else -3 - external_count
            )
            return None

        self._mutate_sketch(target, f"add external edge to {target.Name}", add)
        return self._sketch_result(
            target,
            external_geometry_index=external_index,
            source_object=source.Name,
            source_edge=f"Edge{edge_index}",
        )

    def move_sketch_point(
        self,
        sketch: str,
        geometry: int,
        position: str,
        x: float,
        y: float,
    ) -> dict[str, Any]:
        checked_x, checked_y = self._finite_sketch_values(x, y)
        target = self._sketch_or_error(sketch)
        index = self._geometry_index(target, geometry)
        point = self._point_position(position)
        app, _ = self._modules()

        def move(_: Any) -> None:
            target.moveGeometry(
                index, point, app.Vector(checked_x, checked_y, 0), False
            )
            return None

        self._mutate_sketch(target, f"move sketch point in {target.Name}", move)
        return self._sketch_result(
            target,
            geometry=index,
            position=position,
            point_mm=[checked_x, checked_y],
        )

    def toggle_sketch_construction(
        self, sketch: str, geometry_indices: list[int]
    ) -> dict[str, Any]:
        target = self._sketch_or_error(sketch)
        indices = self._geometry_index_list(target, geometry_indices)

        def toggle(_: Any) -> None:
            for index in indices:
                target.toggleConstruction(index)
            return None

        self._mutate_sketch(target, f"toggle construction in {target.Name}", toggle)
        return self._sketch_result(target, changed_geometry=indices)

    def delete_sketch_geometry(
        self, sketch: str, geometry_indices: list[int]
    ) -> dict[str, Any]:
        target = self._sketch_or_error(sketch)
        indices = self._geometry_index_list(target, geometry_indices)

        def delete(_: Any) -> None:
            for index in sorted(indices, reverse=True):
                target.delGeometry(index, True)
            return None

        self._mutate_sketch(target, f"delete geometry from {target.Name}", delete)
        return self._sketch_result(target, deleted_geometry=sorted(indices))

    def trim_sketch_geometry(
        self, sketch: str, geometry: int, x: float, y: float
    ) -> dict[str, Any]:
        checked_x, checked_y = self._finite_sketch_values(x, y)
        target = self._sketch_or_error(sketch)
        index = self._geometry_index(target, geometry)
        app, _ = self._modules()
        before = int(target.GeometryCount)

        def trim(_: Any) -> None:
            result = target.trim(index, app.Vector(checked_x, checked_y, 0))
            if isinstance(result, (int, float)) and result < 0:
                raise RuntimeError("FreeCAD could not trim the selected sketch geometry.")
            return None

        self._mutate_sketch(target, f"trim geometry in {target.Name}", trim)
        return self._sketch_result(
            target,
            geometry=index,
            geometry_delta=int(target.GeometryCount) - before,
        )

    def extend_sketch_geometry(
        self,
        sketch: str,
        geometry: int,
        position: str,
        increment: float,
    ) -> dict[str, Any]:
        checked_increment = self._positive_values(increment)[0]
        target = self._sketch_or_error(sketch)
        index = self._geometry_index(target, geometry)
        point = self._point_position(position, allow_center=False)

        def extend(_: Any) -> None:
            result = target.extend(index, checked_increment, point)
            if isinstance(result, (int, float)) and result < 0:
                raise RuntimeError("FreeCAD could not extend the selected geometry.")
            return None

        self._mutate_sketch(target, f"extend geometry in {target.Name}", extend)
        return self._sketch_result(
            target,
            geometry=index,
            position=position,
            increment_mm=checked_increment,
        )

    def fillet_sketch_corner(
        self,
        sketch: str,
        first_geometry: int,
        second_geometry: int,
        first_x: float,
        first_y: float,
        second_x: float,
        second_y: float,
        radius: float,
        trim: bool = True,
    ) -> dict[str, Any]:
        x1, y1, x2, y2 = self._finite_sketch_values(
            first_x, first_y, second_x, second_y
        )
        checked_radius = self._positive_values(radius)[0]
        if not isinstance(trim, bool):
            raise ValueError("Trim must be a boolean value.")
        target = self._sketch_or_error(sketch)
        first = self._geometry_index(target, first_geometry)
        second = self._geometry_index(target, second_geometry)
        if first == second:
            raise ValueError("Sketch fillet requires two different geometries.")
        app, _ = self._modules()
        before = int(target.GeometryCount)

        def fillet(_: Any) -> None:
            result = target.fillet(
                first,
                second,
                app.Vector(x1, y1, 0),
                app.Vector(x2, y2, 0),
                checked_radius,
                trim,
                False,
            )
            if isinstance(result, (int, float)) and result < 0:
                raise RuntimeError("FreeCAD could not create the requested sketch fillet.")
            return None

        self._mutate_sketch(target, f"fillet corner in {target.Name}", fillet)
        return self._sketch_result(
            target,
            added_geometry=list(range(before, int(target.GeometryCount))),
            radius_mm=checked_radius,
            trimmed=trim,
        )

    def copy_sketch_geometry(
        self,
        sketch: str,
        geometry_indices: list[int],
        dx: float,
        dy: float,
        clone_constraints: bool = False,
    ) -> dict[str, Any]:
        checked_dx, checked_dy = self._finite_sketch_values(dx, dy)
        if math.hypot(checked_dx, checked_dy) <= 1e-9:
            raise ValueError("Sketch copy displacement must be non-zero.")
        if not isinstance(clone_constraints, bool):
            raise ValueError("Clone constraints must be a boolean value.")
        target = self._sketch_or_error(sketch)
        indices = self._geometry_index_list(target, geometry_indices)
        app, _ = self._modules()
        before = int(target.GeometryCount)

        def copy(_: Any) -> None:
            result = target.addCopy(
                indices,
                app.Vector(checked_dx, checked_dy, 0),
                clone_constraints,
            )
            if isinstance(result, (int, float)) and result < 0:
                raise RuntimeError("FreeCAD could not copy the selected sketch geometry.")
            return None

        self._mutate_sketch(target, f"copy geometry in {target.Name}", copy)
        return self._sketch_result(
            target,
            source_geometry=indices,
            added_geometry=list(range(before, int(target.GeometryCount))),
            displacement_mm=[checked_dx, checked_dy],
        )

    def mirror_sketch_geometry(
        self,
        sketch: str,
        geometry_indices: list[int],
        axis: str,
        axis_geometry: int | None = None,
    ) -> dict[str, Any]:
        target = self._sketch_or_error(sketch)
        indices = self._geometry_index_list(target, geometry_indices)
        checked_axis = str(axis).strip().lower()
        if checked_axis == "horizontal":
            reference = -1
        elif checked_axis == "vertical":
            reference = -2
        elif checked_axis == "geometry":
            if axis_geometry is None:
                raise ValueError("Mirroring about geometry requires axis_geometry.")
            reference = self._geometry_index(target, axis_geometry)
            if reference in indices:
                raise ValueError("Mirror axis geometry cannot also be mirrored.")
        else:
            raise ValueError("Sketch mirror axis must be horizontal, vertical or geometry.")
        before = int(target.GeometryCount)

        def mirror(_: Any) -> None:
            result = target.addSymmetric(indices, reference)
            if isinstance(result, (int, float)) and result < 0:
                raise RuntimeError("FreeCAD could not mirror the selected sketch geometry.")
            return None

        self._mutate_sketch(target, f"mirror geometry in {target.Name}", mirror)
        return self._sketch_result(
            target,
            source_geometry=indices,
            added_geometry=list(range(before, int(target.GeometryCount))),
            mirror_axis=checked_axis,
            axis_geometry=reference if checked_axis == "geometry" else None,
        )

from __future__ import annotations

import math
from typing import Any


class FeatureMixin:
    """Derived features: holes, pads, revolves, lofts, booleans and finishes."""

    def _create_hole_result(
        self,
        source_reference: str,
        diameter: float,
        positions: tuple[tuple[float, float], ...],
        name: str,
        feature_kind: str,
        z_min: float | None = None,
        z_max: float | None = None,
    ) -> Any:
        checked_diameter = self._positive_values(diameter)[0]
        source = self._resolve_document_object(source_reference)
        self._shape_or_error(source)
        window = self._checked_z_window(z_min, z_max)
        app, part = self._modules()

        def cut(document: Any) -> Any:
            bounds = source.Shape.BoundBox
            if window is None:
                # Unscoped: span the whole solid so the hole is truly through.
                margin = max(1.0, float(bounds.ZLength) * 0.1)
                low = float(bounds.ZMin) - margin
                height = float(bounds.ZLength) + 2 * margin
            else:
                low, high = window
                height = high - low
            cutters = [
                part.makeCylinder(
                    checked_diameter / 2,
                    height,
                    app.Vector(x, y, low),
                )
                for x, y in positions
            ]
            cutter = cutters[0]
            for following in cutters[1:]:
                cutter = cutter.fuse(following)
            result_shape = self._checked_hole_cut(source, cutter)
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
        z_min: float | None = None,
        z_max: float | None = None,
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
            z_min,
            z_max,
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

    def _checked_z_window(
        self,
        z_min: float | None,
        z_max: float | None,
    ) -> tuple[float, float] | None:
        """Resolve an optional Z window that scopes a hole to one feature.

        Without it the cutter spans the whole solid's bounding box, so on a
        fused body a hole drills every feature sharing that (x, y) column.
        """

        if z_min is None and z_max is None:
            return None
        if z_min is None or z_max is None:
            raise ValueError("A hole Z window needs both z_min and z_max.")
        low = self._finite_float(z_min)
        high = self._finite_float(z_max)
        if low is None or high is None:
            raise ValueError("Hole Z window bounds must be finite.")
        if high - low <= 0:
            raise ValueError("A hole Z window requires z_max above z_min.")
        return low, high

    @staticmethod
    def _checked_hole_cut(source: Any, cutter: Any) -> Any:
        result_shape = source.Shape.cut(cutter)
        if (
            result_shape.isNull()
            or not result_shape.isValid()
            or not result_shape.Solids
            or float(result_shape.Volume) <= 0
            or float(result_shape.Volume) >= float(source.Shape.Volume) - 1e-9
        ):
            raise ValueError("The requested holes do not cut the selected solid.")
        return result_shape

    def create_counterbore_hole(
        self,
        object: str,
        diameter: float,
        x: float,
        y: float,
        counterbore_diameter: float,
        counterbore_depth: float,
        name: str = "AICounterboreHole",
    ) -> dict[str, Any]:
        checked_diameter, checked_recess_diameter, checked_depth = self._positive_values(
            diameter, counterbore_diameter, counterbore_depth
        )
        if checked_recess_diameter <= checked_diameter:
            raise ValueError(
                "The counterbore diameter must exceed the hole diameter."
            )
        checked_x = self._finite_float(x)
        checked_y = self._finite_float(y)
        if checked_x is None or checked_y is None:
            raise ValueError("Hole coordinates must be finite.")
        source = self._resolve_document_object(object)
        self._shape_or_error(source)
        app, part = self._modules()

        def cut(document: Any) -> Any:
            bounds = source.Shape.BoundBox
            if checked_depth >= float(bounds.ZLength):
                raise ValueError(
                    "The counterbore depth must be smaller than the solid height."
                )
            margin = max(1.0, float(bounds.ZLength) * 0.1)
            through = part.makeCylinder(
                checked_diameter / 2,
                float(bounds.ZLength) + 2 * margin,
                app.Vector(checked_x, checked_y, float(bounds.ZMin) - margin),
            )
            recess = part.makeCylinder(
                checked_recess_diameter / 2,
                checked_depth + margin,
                app.Vector(checked_x, checked_y, float(bounds.ZMax) - checked_depth),
            )
            result_shape = self._checked_hole_cut(source, through.fuse(recess))
            return self._derived_feature(
                document,
                name,
                result_shape,
                (source,),
                "counterbore_hole",
            )

        result = self._run_transaction("counterbore_hole", cut)
        return {
            "name": result.Name,
            "label": result.Label,
            "diameter_mm": checked_diameter,
            "counterbore_diameter_mm": checked_recess_diameter,
            "counterbore_depth_mm": checked_depth,
            "valid": True,
        }

    def create_countersunk_hole(
        self,
        object: str,
        diameter: float,
        x: float,
        y: float,
        countersink_diameter: float,
        countersink_angle: float = 90,
        name: str = "AICountersunkHole",
    ) -> dict[str, Any]:
        checked_diameter, checked_recess_diameter = self._positive_values(
            diameter, countersink_diameter
        )
        if checked_recess_diameter <= checked_diameter:
            raise ValueError(
                "The countersink diameter must exceed the hole diameter."
            )
        checked_angle = self._finite_float(countersink_angle)
        if checked_angle is None or not 60 <= checked_angle <= 120:
            raise ValueError(
                "The countersink angle must be between 60 and 120 degrees."
            )
        checked_x = self._finite_float(x)
        checked_y = self._finite_float(y)
        if checked_x is None or checked_y is None:
            raise ValueError("Hole coordinates must be finite.")
        depth = (
            (checked_recess_diameter - checked_diameter)
            / 2
            / math.tan(math.radians(checked_angle / 2))
        )
        source = self._resolve_document_object(object)
        self._shape_or_error(source)
        app, part = self._modules()

        def cut(document: Any) -> Any:
            bounds = source.Shape.BoundBox
            if depth >= float(bounds.ZLength):
                raise ValueError(
                    "The countersink does not fit inside the solid height."
                )
            margin = max(1.0, float(bounds.ZLength) * 0.1)
            through = part.makeCylinder(
                checked_diameter / 2,
                float(bounds.ZLength) + 2 * margin,
                app.Vector(checked_x, checked_y, float(bounds.ZMin) - margin),
            )
            cone = part.makeCone(
                checked_diameter / 2,
                checked_recess_diameter / 2,
                depth,
                app.Vector(checked_x, checked_y, float(bounds.ZMax) - depth),
            )
            cap = part.makeCylinder(
                checked_recess_diameter / 2,
                margin,
                app.Vector(checked_x, checked_y, float(bounds.ZMax)),
            )
            result_shape = self._checked_hole_cut(
                source, through.fuse(cone).fuse(cap)
            )
            return self._derived_feature(
                document,
                name,
                result_shape,
                (source,),
                "countersunk_hole",
            )

        result = self._run_transaction("countersunk_hole", cut)
        return {
            "name": result.Name,
            "label": result.Label,
            "diameter_mm": checked_diameter,
            "countersink_diameter_mm": checked_recess_diameter,
            "countersink_angle_deg": checked_angle,
            "countersink_depth_mm": depth,
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
            # Extrude along the sketch's own normal: a global +Z vector would
            # lie inside an xz/yz sketch plane and collapse the pad.
            normal = source.Placement.Rotation.multVec(app.Vector(0, 0, 1))
            shape = face.extrude(normal.multiply(checked_length))
            return self._derived_feature(document, name, shape, (source,), "pad")

        result = self._run_transaction(f"pad {source.Name}", pad)
        return {
            "name": result.Name,
            "label": result.Label,
            "length_mm": checked_length,
            "volume_mm3": float(result.Shape.Volume),
            "valid": True,
        }

    def revolve_sketch(
        self,
        sketch: str,
        angle: float = 360.0,
        axis: str = "x",
        name: str = "AIRevolve",
    ) -> dict[str, Any]:
        checked_angle = self._finite_float(angle)
        if checked_angle is None or not 0 < checked_angle <= 360:
            raise ValueError("The revolution angle must be within (0, 360].")
        directions = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0)}
        if axis not in directions:
            raise ValueError("The revolution axis must be 'x' or 'y'.")
        app, part = self._modules()
        source, wire = self._closed_sketch_wire(sketch)
        bounds = wire.BoundBox
        offset = (
            (float(bounds.YMin), float(bounds.YMax))
            if axis == "x"
            else (float(bounds.XMin), float(bounds.XMax))
        )
        if offset[0] < -1e-9 and offset[1] > 1e-9:
            raise ValueError(
                "The sketch crosses the revolution axis; move it fully to one "
                "side before revolving."
            )

        def revolve(document: Any) -> Any:
            document.recompute()
            face = part.Face(source.Shape.Wires[0])
            shape = face.revolve(
                app.Vector(0, 0, 0),
                app.Vector(*directions[axis]),
                checked_angle,
            )
            if not shape.Solids:
                raise RuntimeError("The revolution did not produce a solid.")
            return self._derived_feature(document, name, shape, (source,), "revolve")

        result = self._run_transaction(f"revolve {source.Name}", revolve)
        return {
            "name": result.Name,
            "label": result.Label,
            "angle_deg": checked_angle,
            "axis": axis,
            "volume_mm3": float(result.Shape.Volume),
            "valid": True,
        }

    def loft_sketches(
        self,
        sketches: list[str],
        ruled: bool = False,
        name: str = "AILoft",
    ) -> dict[str, Any]:
        if not isinstance(sketches, list) or len(sketches) < 2:
            raise ValueError("A loft requires at least two sketches.")
        _, part = self._modules()
        resolved = [self._closed_sketch_wire(reference) for reference in sketches]
        names = [source.Name for source, _ in resolved]
        if len(set(names)) != len(names):
            raise ValueError("Loft sections must be different sketches.")

        def loft(document: Any) -> Any:
            document.recompute()
            wires = [source.Shape.Wires[0] for source, _ in resolved]
            shape = part.makeLoft(wires, True, bool(ruled))
            if not shape.Solids:
                raise RuntimeError("The loft did not produce a solid.")
            return self._derived_feature(
                document,
                name,
                shape,
                tuple(source for source, _ in resolved),
                "loft",
            )

        result = self._run_transaction("loft sketches", loft)
        return {
            "name": result.Name,
            "label": result.Label,
            "section_count": len(resolved),
            "ruled": bool(ruled),
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

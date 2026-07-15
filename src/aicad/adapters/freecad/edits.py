from __future__ import annotations

import math
from typing import Any


class EditMixin:
    """Primitive creation and validated edits on existing objects."""

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

    def translate_object(
        self,
        object: str,
        dx: float = 0,
        dy: float = 0,
        dz: float = 0,
    ) -> dict[str, Any]:
        deltas = tuple(self._finite_float(value) for value in (dx, dy, dz))
        if any(value is None for value in deltas):
            raise ValueError("Translation deltas must be finite.")
        checked_dx, checked_dy, checked_dz = deltas
        if all(math.isclose(value, 0.0, abs_tol=1e-12) for value in deltas):
            raise ValueError("At least one translation delta must be non-zero.")
        item = self._resolve_document_object(object)
        app, _ = self._modules()

        def translate(_: Any) -> Any:
            current = item.Placement
            base = current.Base
            item.Placement = app.Placement(
                app.Vector(
                    base.x + checked_dx,
                    base.y + checked_dy,
                    base.z + checked_dz,
                ),
                current.Rotation,
            )
            return item

        changed = self._run_transaction(f"translate {item.Name}", translate)
        base = changed.Placement.Base
        return {
            "name": changed.Name,
            "label": changed.Label,
            "position_mm": [float(base.x), float(base.y), float(base.z)],
            "rotation_quaternion": [
                float(value) for value in changed.Placement.Rotation.Q
            ],
            "valid": True,
        }

    def rotate_object(
        self,
        object: str,
        axis: str,
        angle: float,
        pivot: str = "object_center",
    ) -> dict[str, Any]:
        checked_axis = str(axis).lower()
        if checked_axis not in {"x", "y", "z"}:
            raise ValueError("Rotation axis must be x, y or z.")
        checked_pivot = str(pivot).lower()
        if checked_pivot not in {"object_center", "global_origin"}:
            raise ValueError("Rotation pivot must be object_center or global_origin.")
        checked_angle = self._finite_float(angle)
        if checked_angle is None or not -360 <= checked_angle <= 360:
            raise ValueError("Rotation angle must be finite and within -360 to 360 degrees.")
        if math.isclose(checked_angle % 360, 0.0, abs_tol=1e-12):
            raise ValueError("Rotation angle must produce a non-zero rotation.")
        item = self._resolve_document_object(object)
        shape = self._shape_or_error(item)
        app, _ = self._modules()
        vectors = {
            "x": app.Vector(1, 0, 0),
            "y": app.Vector(0, 1, 0),
            "z": app.Vector(0, 0, 1),
        }
        pivot_vector = (
            shape.BoundBox.Center
            if checked_pivot == "object_center"
            else app.Vector(0, 0, 0)
        )

        def rotate(_: Any) -> Any:
            current = item.Placement
            delta = app.Rotation(vectors[checked_axis], checked_angle)
            relative_base = current.Base - pivot_vector
            next_base = pivot_vector + delta.multVec(relative_base)
            next_rotation = delta.multiply(current.Rotation)
            item.Placement = app.Placement(next_base, next_rotation)
            return item

        changed = self._run_transaction(f"rotate {item.Name}", rotate)
        base = changed.Placement.Base
        return {
            "name": changed.Name,
            "label": changed.Label,
            "axis": checked_axis,
            "angle_deg": checked_angle,
            "pivot": checked_pivot,
            "pivot_mm": [
                float(pivot_vector.x),
                float(pivot_vector.y),
                float(pivot_vector.z),
            ],
            "position_mm": [float(base.x), float(base.y), float(base.z)],
            "rotation_quaternion": [
                float(value) for value in changed.Placement.Rotation.Q
            ],
            "valid": True,
        }

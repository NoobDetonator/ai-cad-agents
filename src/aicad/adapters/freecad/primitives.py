from __future__ import annotations

import math
from typing import Any


class PrimitiveMixin:
    """Validated creation of fundamental parametric solids."""

    def create_cone(
        self,
        bottom_diameter: float,
        top_diameter: float,
        height: float,
        name: str = "AICone",
    ) -> dict[str, Any]:
        bottom = self._finite_float(bottom_diameter)
        top = self._finite_float(top_diameter)
        checked_height = self._positive_values(height)[0]
        if bottom is None or top is None or bottom < 0 or top < 0:
            raise ValueError("Cone diameters must be finite and non-negative.")
        if math.isclose(bottom, 0.0) and math.isclose(top, 0.0):
            raise ValueError("At least one cone diameter must be greater than zero.")
        checked_name = self._validated_object_name(name)

        def configure(document: Any) -> Any:
            cone = document.addObject("Part::Cone", checked_name)
            cone.Radius1 = bottom / 2
            cone.Radius2 = top / 2
            cone.Height = checked_height
            cone.Angle = 360
            return cone

        cone = self._create_validated_shape(checked_name, configure)
        return {
            "name": cone.Name,
            "label": cone.Label,
            "bottom_diameter_mm": bottom,
            "top_diameter_mm": top,
            "height_mm": checked_height,
            "volume_mm3": float(cone.Shape.Volume),
            "valid": True,
        }

    def create_sphere(
        self,
        diameter: float,
        name: str = "AISphere",
    ) -> dict[str, Any]:
        checked_diameter = self._positive_values(diameter)[0]
        checked_name = self._validated_object_name(name)

        def configure(document: Any) -> Any:
            sphere = document.addObject("Part::Sphere", checked_name)
            sphere.Radius = checked_diameter / 2
            sphere.Angle1 = -90
            sphere.Angle2 = 90
            sphere.Angle3 = 360
            return sphere

        sphere = self._create_validated_shape(checked_name, configure)
        return {
            "name": sphere.Name,
            "label": sphere.Label,
            "diameter_mm": checked_diameter,
            "radius_mm": checked_diameter / 2,
            "volume_mm3": float(sphere.Shape.Volume),
            "valid": True,
        }

    def create_torus(
        self,
        major_diameter: float,
        tube_diameter: float,
        name: str = "AITorus",
    ) -> dict[str, Any]:
        major, tube = self._positive_values(major_diameter, tube_diameter)
        if major <= tube:
            raise ValueError("The torus major diameter must exceed the tube diameter.")
        checked_name = self._validated_object_name(name)

        def configure(document: Any) -> Any:
            torus = document.addObject("Part::Torus", checked_name)
            torus.Radius1 = major / 2
            torus.Radius2 = tube / 2
            torus.Angle1 = -180
            torus.Angle2 = 180
            torus.Angle3 = 360
            return torus

        torus = self._create_validated_shape(checked_name, configure)
        return {
            "name": torus.Name,
            "label": torus.Label,
            "major_diameter_mm": major,
            "tube_diameter_mm": tube,
            "volume_mm3": float(torus.Shape.Volume),
            "valid": True,
        }

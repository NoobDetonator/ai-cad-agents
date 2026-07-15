from __future__ import annotations

from itertools import combinations
import math
from typing import Any


class AssemblyMixin:
    """Reusable mechanical components, placement constraints and verification."""

    def create_planetary_carrier(
        self,
        plate_diameter: float,
        thickness: float,
        center_bore_diameter: float,
        planet_count: int,
        planet_pitch_diameter: float,
        pin_hole_diameter: float,
        name: str = "PlanetaryCarrier",
    ) -> dict[str, Any]:
        plate, height, pitch, pin = self._positive_values(
            plate_diameter, thickness, planet_pitch_diameter, pin_hole_diameter
        )
        bore = self._finite_float(center_bore_diameter)
        if bore is None or bore < 0:
            raise ValueError("The carrier center bore cannot be negative.")
        count = int(planet_count)
        if isinstance(planet_count, bool) or count != planet_count or not 2 <= count <= 16:
            raise ValueError("A planetary carrier requires between 2 and 16 pin holes.")
        plate_radius = plate / 2
        pitch_radius = pitch / 2
        pin_radius = pin / 2
        if pitch_radius + 2 * pin_radius > plate_radius:
            raise ValueError("The carrier needs at least one pin radius of edge wall.")
        if bore / 2 + 2 * pin_radius >= pitch_radius:
            raise ValueError("The center bore and planet pin holes need solid separation.")
        checked_name = self._validated_object_name(name)
        app, part = self._modules()

        def create(document: Any) -> Any:
            disk = part.makeCylinder(plate_radius, height)
            cutters = []
            if bore > 0:
                cutters.append(part.makeCylinder(bore / 2, height))
            for index in range(count):
                angle = math.radians(index * 360 / count)
                cutters.append(
                    part.makeCylinder(
                        pin_radius,
                        height,
                        app.Vector(
                            pitch_radius * math.cos(angle),
                            pitch_radius * math.sin(angle),
                            0,
                        ),
                    )
                )
            cutter = cutters[0]
            for following in cutters[1:]:
                cutter = cutter.fuse(following)
            shape = disk.cut(cutter)
            result = self._derived_feature(
                document, checked_name, shape, (), "planetary_carrier"
            )
            result.addProperty("App::PropertyInteger", "PlanetCount", "Carrier")
            result.PlanetCount = count
            result.addProperty("App::PropertyLength", "PlanetPitchDiameter", "Carrier")
            result.PlanetPitchDiameter = pitch
            result.addProperty("App::PropertyLength", "PinHoleDiameter", "Carrier")
            result.PinHoleDiameter = pin
            return result

        carrier = self._run_transaction(
            f"create planetary carrier {checked_name}", create
        )
        return {
            "name": carrier.Name,
            "label": carrier.Label,
            "plate_diameter_mm": plate,
            "thickness_mm": height,
            "center_bore_diameter_mm": bore,
            "planet_count": count,
            "planet_pitch_diameter_mm": pitch,
            "pin_hole_diameter_mm": pin,
            "volume_mm3": float(carrier.Shape.Volume),
            "valid": True,
        }

    def create_ball_bearing(
        self,
        bore_diameter: float,
        outer_diameter: float,
        width: float,
        ball_count: int,
        ball_diameter: float,
        radial_clearance: float = 0.05,
        name: str = "BallBearing",
    ) -> dict[str, Any]:
        bore, outer, checked_width, ball = self._positive_values(
            bore_diameter, outer_diameter, width, ball_diameter
        )
        clearance = self._finite_float(radial_clearance)
        if clearance is None or clearance < 0:
            raise ValueError("Bearing radial clearance cannot be negative.")
        count = int(ball_count)
        if isinstance(ball_count, bool) or count != ball_count or not 4 <= count <= 64:
            raise ValueError("A ball bearing requires between 4 and 64 balls.")
        if bore >= outer:
            raise ValueError("Bearing outer diameter must exceed its bore diameter.")
        if ball > checked_width:
            raise ValueError("Bearing balls must fit within the bearing width.")
        bore_radius = bore / 2
        outer_radius = outer / 2
        ball_radius = ball / 2
        pitch_radius = (outer_radius + bore_radius) / 2
        radial_space = outer_radius - bore_radius
        if ball + clearance >= radial_space:
            raise ValueError("Bearing balls and clearance do not fit between the races.")
        if 2 * math.pi * pitch_radius / count <= ball + clearance:
            raise ValueError("The requested balls overlap around the pitch circle.")
        inner_outer_radius = pitch_radius - ball_radius - clearance / 2
        outer_inner_radius = pitch_radius + ball_radius + clearance / 2
        checked_name = self._validated_object_name(name)
        app, part = self._modules()

        def create(document: Any) -> Any:
            inner_race = part.makeCylinder(inner_outer_radius, checked_width).cut(
                part.makeCylinder(bore_radius, checked_width)
            )
            outer_race = part.makeCylinder(outer_radius, checked_width).cut(
                part.makeCylinder(outer_inner_radius, checked_width)
            )
            balls = []
            for index in range(count):
                angle = math.radians(index * 360 / count)
                balls.append(
                    part.makeSphere(
                        ball_radius,
                        app.Vector(
                            pitch_radius * math.cos(angle),
                            pitch_radius * math.sin(angle),
                            checked_width / 2,
                        ),
                    )
                )
            shape = part.makeCompound([inner_race, outer_race, *balls])
            result = self._derived_feature(
                document, checked_name, shape, (), "radial_ball_bearing"
            )
            result.addProperty("App::PropertyInteger", "BallCount", "Bearing")
            result.BallCount = count
            result.addProperty("App::PropertyLength", "RadialClearance", "Bearing")
            result.RadialClearance = clearance
            return result

        bearing = self._run_transaction(f"create ball bearing {checked_name}", create)
        return {
            "name": bearing.Name,
            "label": bearing.Label,
            "bore_diameter_mm": bore,
            "outer_diameter_mm": outer,
            "width_mm": checked_width,
            "ball_count": count,
            "ball_diameter_mm": ball,
            "pitch_diameter_mm": 2 * pitch_radius,
            "radial_clearance_mm": clearance,
            "solid_count": len(bearing.Shape.Solids),
            "volume_mm3": float(bearing.Shape.Volume),
            "valid": True,
        }

    def apply_gear_backlash(
        self,
        object: str,
        backlash: float,
        name: str,
    ) -> dict[str, Any]:
        checked_backlash = self._positive_values(backlash)[0]
        source = self._resolve_document_object(object)
        source_shape = self._shape_or_error(source)
        if not hasattr(source, "NumberOfTeeth") or not hasattr(source, "GearModule"):
            raise ValueError("Backlash requires gear tooth-count and module metadata.")
        teeth = int(source.NumberOfTeeth)
        module = float(source.GearModule.Value)
        if checked_backlash > module / 2:
            raise ValueError("Gear backlash cannot exceed half of the module.")
        pitch_radius = module * teeth / 2
        half_angle = math.degrees(checked_backlash / (2 * pitch_radius))
        checked_name = self._validated_object_name(name)
        app, part = self._modules()

        def thin(document: Any) -> Any:
            internal = bool(getattr(source, "InternalGear", False))
            axis = app.Vector(0, 0, 1)
            if internal:
                sources = list(getattr(source, "SourceObjects", ()))
                if not sources or not hasattr(sources[0], "ExternalGear"):
                    raise ValueError(
                        "Internal gear backlash requires its involute source profile."
                    )
                profile_wire = sources[0].Shape
                thickness = float(source.Thickness.Value)
                phase = float(getattr(source, "PhaseAngle", 0).Value)

                def pocket(angle: float) -> Any:
                    wire = profile_wire.copy()
                    wire.rotate(app.Vector(0, 0, 0), axis, phase + angle)
                    shape = part.Face(wire).extrude(app.Vector(0, 0, thickness))
                    shape.Placement = source.Placement
                    return shape

                original_pocket = pocket(0)
                rim = source_shape.fuse(original_pocket)
                widened_pocket = pocket(-half_angle).fuse(pocket(half_angle))
                shape = rim.cut(widened_pocket).removeSplitter()
            else:
                center = source_shape.BoundBox.Center
                left = source_shape.copy()
                right = source_shape.copy()
                left.rotate(center, axis, -half_angle)
                right.rotate(center, axis, half_angle)
                shape = left.common(right).removeSplitter()
            if float(shape.Volume) >= float(source_shape.Volume) - 1e-9:
                raise RuntimeError("Backlash did not remove measurable tooth material.")
            result = self._derived_feature(
                document, checked_name, shape, (source,), "gear_backlash"
            )
            result.addProperty("App::PropertyInteger", "NumberOfTeeth", "Gear")
            result.NumberOfTeeth = teeth
            result.addProperty("App::PropertyLength", "GearModule", "Gear")
            result.GearModule = module
            result.addProperty("App::PropertyLength", "Backlash", "Gear")
            result.Backlash = checked_backlash
            result.addProperty("App::PropertyBool", "InternalGear", "Gear")
            result.InternalGear = bool(getattr(source, "InternalGear", False))
            return result

        gear = self._run_transaction(f"apply backlash to {source.Name}", thin)
        return {
            "name": gear.Name,
            "label": gear.Label,
            "source": source.Name,
            "backlash_mm": checked_backlash,
            "angular_relief_deg": 2 * half_angle,
            "volume_removed_mm3": float(source_shape.Volume) - float(gear.Shape.Volume),
            "valid": True,
        }

    def align_concentric(
        self,
        moving: str,
        reference: str,
        z_alignment: str = "center",
        axial_offset: float = 0,
    ) -> dict[str, Any]:
        moving_item = self._resolve_document_object(moving)
        reference_item = self._resolve_document_object(reference)
        if moving_item is reference_item:
            raise ValueError("Concentric alignment requires two different objects.")
        mode = str(z_alignment).lower()
        if mode not in {"base", "center", "top"}:
            raise ValueError("Z alignment must be base, center or top.")
        offset = self._finite_float(axial_offset)
        if offset is None:
            raise ValueError("The axial offset must be finite.")
        moving_shape = self._shape_or_error(moving_item)
        reference_shape = self._shape_or_error(reference_item)
        app, _ = self._modules()
        moving_bounds = moving_shape.BoundBox
        reference_bounds = reference_shape.BoundBox
        dx = float(reference_bounds.Center.x - moving_bounds.Center.x)
        dy = float(reference_bounds.Center.y - moving_bounds.Center.y)
        moving_z = {
            "base": float(moving_bounds.ZMin),
            "center": float(moving_bounds.Center.z),
            "top": float(moving_bounds.ZMax),
        }[mode]
        reference_z = {
            "base": float(reference_bounds.ZMin),
            "center": float(reference_bounds.Center.z),
            "top": float(reference_bounds.ZMax),
        }[mode]
        dz = reference_z + offset - moving_z
        if all(math.isclose(value, 0.0, abs_tol=1e-12) for value in (dx, dy, dz)):
            raise ValueError("The objects already satisfy the requested alignment.")

        def align(_: Any) -> Any:
            current = moving_item.Placement
            moving_item.Placement = app.Placement(
                current.Base + app.Vector(dx, dy, dz), current.Rotation
            )
            if not hasattr(moving_item, "AlignmentReference"):
                moving_item.addProperty("App::PropertyLink", "AlignmentReference", "AI CAD")
                moving_item.addProperty("App::PropertyString", "AlignmentMode", "AI CAD")
            moving_item.AlignmentReference = reference_item
            moving_item.AlignmentMode = f"concentric_xy/{mode}/offset={offset:g}mm"
            return moving_item

        aligned = self._run_transaction(
            f"align {moving_item.Name} to {reference_item.Name}", align
        )
        base = aligned.Placement.Base
        return {
            "name": aligned.Name,
            "label": aligned.Label,
            "reference": reference_item.Name,
            "z_alignment": mode,
            "axial_offset_mm": offset,
            "position_mm": [float(base.x), float(base.y), float(base.z)],
            "rotation_quaternion": [
                float(value) for value in aligned.Placement.Rotation.Q
            ],
            "valid": True,
        }

    def analyze_interferences(
        self,
        objects: list[str],
        minimum_clearance: float = 0,
        volume_tolerance: float = 1e-4,
    ) -> dict[str, Any]:
        clearance = self._finite_float(minimum_clearance)
        tolerance = self._finite_float(volume_tolerance)
        if clearance is None or clearance < 0:
            raise ValueError("Minimum clearance cannot be negative.")
        if tolerance is None or tolerance < 0:
            raise ValueError("Volume tolerance cannot be negative.")
        if not 2 <= len(objects) <= 32:
            raise ValueError("Interference analysis requires 2 to 32 objects.")
        resolved = [self._resolve_document_object(reference) for reference in objects]
        if len({item.Name for item in resolved}) != len(resolved):
            raise ValueError("Interference analysis object references must be unique.")
        pairs = []
        for left, right in combinations(resolved, 2):
            left_shape = self._shape_or_error(left)
            right_shape = self._shape_or_error(right)
            distance, _, _ = left_shape.distToShape(right_shape)
            distance = float(distance)
            common_volume = 0.0
            if distance <= 1e-7:
                common = left_shape.common(right_shape)
                if not common.isNull():
                    common_volume = float(common.Volume)
            interference = common_volume > tolerance
            contact = distance <= 1e-7 and not interference
            clearance_violation = distance + 1e-9 < clearance
            status = (
                "interference"
                if interference
                else "contact"
                if contact
                else "clearance_violation"
                if clearance_violation
                else "clear"
            )
            pairs.append(
                {
                    "left": left.Name,
                    "right": right.Name,
                    "minimum_distance_mm": distance,
                    "common_volume_mm3": common_volume,
                    "status": status,
                    "clearance_violation": clearance_violation,
                }
            )
        interference_count = sum(
            item["status"] == "interference" for item in pairs
        )
        contact_count = sum(item["status"] == "contact" for item in pairs)
        violation_count = sum(item["clearance_violation"] for item in pairs)
        return {
            "valid": True,
            "passes": interference_count == 0 and violation_count == 0,
            "minimum_clearance_mm": clearance,
            "volume_tolerance_mm3": tolerance,
            "pair_count": len(pairs),
            "interference_count": interference_count,
            "contact_count": contact_count,
            "clearance_violation_count": violation_count,
            "pairs": pairs,
        }

from __future__ import annotations

import math
from typing import Any


class BearingMixin:
    """Validated rolling and plain bearings for machining and additive use."""

    def _bearing_dimensions(
        self,
        bore_diameter: float,
        outer_diameter: float,
        width: float,
        element_count: int,
        element_diameter: float,
        *,
        element_name: str,
    ) -> tuple[float, float, float, int, float, float, float, float]:
        bore, outer, checked_width, element = self._positive_values(
            bore_diameter, outer_diameter, width, element_diameter
        )
        count = int(element_count)
        if (
            isinstance(element_count, bool)
            or count != element_count
            or not 4 <= count <= 64
        ):
            raise ValueError(f"A bearing requires between 4 and 64 {element_name}.")
        if bore >= outer:
            raise ValueError("Bearing outer diameter must exceed its bore diameter.")
        bore_radius = bore / 2
        outer_radius = outer / 2
        pitch_radius = (outer_radius + bore_radius) / 2
        return (
            bore,
            outer,
            checked_width,
            count,
            element,
            bore_radius,
            outer_radius,
            pitch_radius,
        )

    def _checked_clearance(self, value: float, label: str) -> float:
        checked = self._finite_float(value)
        if checked is None or checked < 0:
            raise ValueError(f"{label} cannot be negative.")
        return checked

    @staticmethod
    def _check_circumferential_spacing(
        pitch_radius: float,
        count: int,
        element_diameter: float,
        separation: float,
    ) -> None:
        chord = 2 * pitch_radius * math.sin(math.pi / count)
        if chord <= element_diameter + separation:
            raise ValueError(
                "The rolling elements overlap around the pitch circle: "
                f"{count} elements leave {chord:.2f} mm between centers, but "
                f"each needs more than {element_diameter + separation:.2f} mm. "
                "Reduce the element count or diameter, or enlarge the bearing."
            )

    def _bearing_feature(
        self,
        document: Any,
        name: str,
        shape: Any,
        bearing_type: str,
        element_count: int,
        clearance: float,
    ) -> Any:
        result = self._derived_feature(document, name, shape, (), bearing_type)
        result.addProperty("App::PropertyString", "BearingType", "Bearing")
        result.BearingType = bearing_type
        result.addProperty("App::PropertyInteger", "RollingElementCount", "Bearing")
        result.RollingElementCount = element_count
        result.addProperty("App::PropertyLength", "InternalClearance", "Bearing")
        result.InternalClearance = clearance
        return result

    @staticmethod
    def _rail_cage(
        app: Any,
        part: Any,
        pitch_radius: float,
        radial_half_width: float,
        bottom_z: float,
        top_z: float,
        rail_height: float,
        count: int,
        element_radius: float,
    ) -> Any:
        """Create two continuous rails joined by posts between rolling elements."""

        cage_inner = pitch_radius - radial_half_width
        cage_outer = pitch_radius + radial_half_width

        def rail(z: float) -> Any:
            return part.makeCylinder(
                cage_outer, rail_height, app.Vector(0, 0, z)
            ).cut(
                part.makeCylinder(
                    cage_inner, rail_height, app.Vector(0, 0, z)
                )
            )

        cage = rail(bottom_z).fuse(rail(top_z))
        midpoint_distance = 2 * pitch_radius * math.sin(math.pi / (2 * count))
        tangential_gap = midpoint_distance - element_radius
        post_radius = min(radial_half_width * 0.55, tangential_gap * 0.45)
        if post_radius <= 0:
            raise ValueError("The rolling-element spacing leaves no room for cage posts.")
        post_height = top_z + rail_height - bottom_z
        for index in range(count):
            angle = math.radians((index + 0.5) * 360 / count)
            post = part.makeCylinder(
                post_radius,
                post_height,
                app.Vector(
                    pitch_radius * math.cos(angle),
                    pitch_radius * math.sin(angle),
                    bottom_z,
                ),
            )
            cage = cage.fuse(post)
        return cage.removeSplitter()

    def create_deep_groove_ball_bearing(
        self,
        bore_diameter: float,
        outer_diameter: float,
        width: float,
        ball_count: int,
        ball_diameter: float,
        radial_clearance: float = 0.05,
        groove_conformity: float = 1.04,
        cage: bool = True,
        name: str = "DeepGrooveBearing",
    ) -> dict[str, Any]:
        (
            bore,
            outer,
            checked_width,
            count,
            ball,
            bore_radius,
            outer_radius,
            pitch_radius,
        ) = self._bearing_dimensions(
            bore_diameter,
            outer_diameter,
            width,
            ball_count,
            ball_diameter,
            element_name="balls",
        )
        clearance = self._checked_clearance(radial_clearance, "Radial clearance")
        conformity = self._finite_float(groove_conformity)
        if conformity is None or not 1.0 <= conformity <= 1.25:
            raise ValueError("Groove conformity must be between 1.00 and 1.25.")
        if not isinstance(cage, bool):
            raise ValueError("Cage must be a boolean value.")
        if ball > checked_width:
            raise ValueError("Bearing balls must fit within the bearing width.")
        radial_space = outer_radius - bore_radius
        if ball + clearance >= radial_space:
            raise ValueError("Bearing balls and clearance do not fit between the races.")
        self._check_circumferential_spacing(pitch_radius, count, ball, clearance)
        ball_radius = ball / 2
        groove_radius = ball_radius * conformity + clearance / 2
        groove_depth = ball_radius * 0.38
        inner_outer_radius = pitch_radius - ball_radius + groove_depth
        outer_inner_radius = pitch_radius + ball_radius - groove_depth
        if inner_outer_radius <= bore_radius or outer_inner_radius >= outer_radius:
            raise ValueError("The requested deep grooves leave insufficient race shoulders.")
        checked_name = self._validated_object_name(name)
        app, part = self._modules()

        def create(document: Any) -> Any:
            origin = app.Vector(0, 0, 0)
            groove = part.makeTorus(
                pitch_radius,
                groove_radius,
                app.Vector(0, 0, checked_width / 2),
            )
            inner_race = part.makeCylinder(inner_outer_radius, checked_width, origin).cut(
                part.makeCylinder(bore_radius, checked_width, origin)
            ).cut(groove)
            outer_race = part.makeCylinder(outer_radius, checked_width, origin).cut(
                part.makeCylinder(outer_inner_radius, checked_width, origin)
            ).cut(groove)
            centers = []
            balls = []
            for index in range(count):
                angle = math.radians(index * 360 / count)
                center = app.Vector(
                    pitch_radius * math.cos(angle),
                    pitch_radius * math.sin(angle),
                    checked_width / 2,
                )
                centers.append(center)
                balls.append(part.makeSphere(ball_radius, center))
            components = [inner_race, outer_race, *balls]
            if cage:
                rail_height = min(checked_width * 0.06, ball * 0.10)
                bottom_z = checked_width / 2 - ball_radius - clearance - rail_height
                top_z = checked_width / 2 + ball_radius + clearance
                radial_half_width = (outer_inner_radius - inner_outer_radius) * 0.28
                if bottom_z < 0 or top_z + rail_height > checked_width:
                    raise ValueError("Bearing width leaves no axial room for its cage rails.")
                cage_shape = self._rail_cage(
                    app,
                    part,
                    pitch_radius,
                    radial_half_width,
                    bottom_z,
                    top_z,
                    rail_height,
                    count,
                    ball_radius,
                )
                components.append(cage_shape)
            shape = part.makeCompound(components)
            result = self._bearing_feature(
                document,
                checked_name,
                shape,
                "deep_groove_ball_bearing",
                count,
                clearance,
            )
            result.addProperty("App::PropertyLength", "BallDiameter", "Bearing")
            result.BallDiameter = ball
            result.addProperty("App::PropertyFloat", "GrooveConformity", "Bearing")
            result.GrooveConformity = conformity
            result.addProperty("App::PropertyBool", "HasCage", "Bearing")
            result.HasCage = cage
            return result

        bearing = self._run_transaction(
            f"create deep groove bearing {checked_name}", create
        )
        return {
            "name": bearing.Name,
            "label": bearing.Label,
            "bearing_type": "deep_groove_ball",
            "bore_diameter_mm": bore,
            "outer_diameter_mm": outer,
            "width_mm": checked_width,
            "ball_count": count,
            "ball_diameter_mm": ball,
            "pitch_diameter_mm": 2 * pitch_radius,
            "radial_clearance_mm": clearance,
            "groove_conformity": conformity,
            "has_cage": cage,
            "solid_count": len(bearing.Shape.Solids),
            "volume_mm3": float(bearing.Shape.Volume),
            "valid": True,
        }

    def create_thrust_ball_bearing(
        self,
        bore_diameter: float,
        outer_diameter: float,
        height: float,
        ball_count: int,
        ball_diameter: float,
        axial_clearance: float = 0.05,
        groove_conformity: float = 1.04,
        cage: bool = True,
        name: str = "ThrustBallBearing",
    ) -> dict[str, Any]:
        (
            bore,
            outer,
            checked_height,
            count,
            ball,
            bore_radius,
            outer_radius,
            pitch_radius,
        ) = self._bearing_dimensions(
            bore_diameter,
            outer_diameter,
            height,
            ball_count,
            ball_diameter,
            element_name="balls",
        )
        clearance = self._checked_clearance(axial_clearance, "Axial clearance")
        conformity = self._finite_float(groove_conformity)
        if conformity is None or not 1.0 <= conformity <= 1.25:
            raise ValueError("Groove conformity must be between 1.00 and 1.25.")
        if not isinstance(cage, bool):
            raise ValueError("Cage must be a boolean value.")
        radial_space = outer_radius - bore_radius
        if ball + clearance >= radial_space:
            raise ValueError("Bearing balls do not fit radially between the washer edges.")
        if ball + clearance >= checked_height:
            raise ValueError("Thrust bearing height must exceed ball diameter and clearance.")
        self._check_circumferential_spacing(pitch_radius, count, ball, clearance)
        ball_radius = ball / 2
        groove_radius = ball_radius * conformity + clearance / 2
        groove_depth = ball_radius * 0.32
        washer_thickness = (checked_height - ball - clearance) / 2 + groove_depth
        if washer_thickness <= groove_depth:
            raise ValueError("Thrust bearing washers are too thin for the raceway grooves.")
        checked_name = self._validated_object_name(name)
        app, part = self._modules()

        def create(document: Any) -> Any:
            center_z = checked_height / 2
            groove = part.makeTorus(
                pitch_radius, groove_radius, app.Vector(0, 0, center_z)
            )
            bottom = part.makeCylinder(outer_radius, washer_thickness).cut(
                part.makeCylinder(bore_radius, washer_thickness)
            ).cut(groove)
            top_z = checked_height - washer_thickness
            top = part.makeCylinder(
                outer_radius, washer_thickness, app.Vector(0, 0, top_z)
            ).cut(
                part.makeCylinder(
                    bore_radius, washer_thickness, app.Vector(0, 0, top_z)
                )
            ).cut(groove)
            centers = []
            balls = []
            for index in range(count):
                angle = math.radians(index * 360 / count)
                center = app.Vector(
                    pitch_radius * math.cos(angle),
                    pitch_radius * math.sin(angle),
                    center_z,
                )
                centers.append(center)
                balls.append(part.makeSphere(ball_radius, center))
            components = [bottom, top, *balls]
            if cage:
                cage_height = min(ball * 0.42, checked_height * 0.18)
                cage_z = center_z - cage_height / 2
                cage_margin = (outer_radius - bore_radius) * 0.12
                cage_shape = part.makeCylinder(
                    outer_radius - cage_margin,
                    cage_height,
                    app.Vector(0, 0, cage_z),
                ).cut(
                    part.makeCylinder(
                        bore_radius + cage_margin,
                        cage_height,
                        app.Vector(0, 0, cage_z),
                    )
                )
                pocket_radius = ball_radius + max(clearance, ball_radius * 0.08)
                cage_shape = cage_shape.cut(
                    part.makeCompound(
                        [part.makeSphere(pocket_radius, center) for center in centers]
                    )
                )
                components.append(cage_shape)
            shape = part.makeCompound(components)
            result = self._bearing_feature(
                document,
                checked_name,
                shape,
                "single_direction_thrust_ball_bearing",
                count,
                clearance,
            )
            result.addProperty("App::PropertyString", "LoadDirection", "Bearing")
            result.LoadDirection = "axial_z_single_direction"
            result.addProperty("App::PropertyBool", "HasCage", "Bearing")
            result.HasCage = cage
            return result

        bearing = self._run_transaction(
            f"create thrust ball bearing {checked_name}", create
        )
        return {
            "name": bearing.Name,
            "label": bearing.Label,
            "bearing_type": "single_direction_thrust_ball",
            "bore_diameter_mm": bore,
            "outer_diameter_mm": outer,
            "height_mm": checked_height,
            "ball_count": count,
            "ball_diameter_mm": ball,
            "pitch_diameter_mm": 2 * pitch_radius,
            "axial_clearance_mm": clearance,
            "groove_conformity": conformity,
            "load_direction": "axial_z_single_direction",
            "solid_count": len(bearing.Shape.Solids),
            "volume_mm3": float(bearing.Shape.Volume),
            "valid": True,
        }

    def create_cylindrical_roller_bearing(
        self,
        bore_diameter: float,
        outer_diameter: float,
        width: float,
        roller_count: int,
        roller_diameter: float,
        roller_length: float,
        radial_clearance: float = 0.05,
        cage: bool = True,
        name: str = "CylindricalRollerBearing",
    ) -> dict[str, Any]:
        (
            bore,
            outer,
            checked_width,
            count,
            roller,
            bore_radius,
            outer_radius,
            pitch_radius,
        ) = self._bearing_dimensions(
            bore_diameter,
            outer_diameter,
            width,
            roller_count,
            roller_diameter,
            element_name="rollers",
        )
        checked_length = self._positive_values(roller_length)[0]
        clearance = self._checked_clearance(radial_clearance, "Radial clearance")
        if not isinstance(cage, bool):
            raise ValueError("Cage must be a boolean value.")
        if checked_length >= checked_width:
            raise ValueError("Roller length must be smaller than bearing width.")
        if roller + clearance >= outer_radius - bore_radius:
            raise ValueError("Rollers and clearance do not fit between the races.")
        self._check_circumferential_spacing(pitch_radius, count, roller, clearance)
        roller_radius = roller / 2
        inner_outer_radius = pitch_radius - roller_radius - clearance / 2
        outer_inner_radius = pitch_radius + roller_radius + clearance / 2
        checked_name = self._validated_object_name(name)
        app, part = self._modules()

        def create(document: Any) -> Any:
            inner = part.makeCylinder(inner_outer_radius, checked_width).cut(
                part.makeCylinder(bore_radius, checked_width)
            )
            outer_race = part.makeCylinder(outer_radius, checked_width).cut(
                part.makeCylinder(outer_inner_radius, checked_width)
            )
            roller_z = (checked_width - checked_length) / 2
            centers = []
            rollers = []
            for index in range(count):
                angle = math.radians(index * 360 / count)
                center = app.Vector(
                    pitch_radius * math.cos(angle),
                    pitch_radius * math.sin(angle),
                    roller_z,
                )
                centers.append(center)
                rollers.append(part.makeCylinder(roller_radius, checked_length, center))
            components = [inner, outer_race, *rollers]
            if cage:
                end_space = (checked_width - checked_length) / 2
                rail_height = end_space * 0.30
                bottom_z = end_space * 0.20
                top_z = checked_width - end_space * 0.20 - rail_height
                radial_half_width = (outer_inner_radius - inner_outer_radius) * 0.30
                cage_shape = self._rail_cage(
                    app,
                    part,
                    pitch_radius,
                    radial_half_width,
                    bottom_z,
                    top_z,
                    rail_height,
                    count,
                    roller_radius,
                )
                components.append(cage_shape)
            shape = part.makeCompound(components)
            result = self._bearing_feature(
                document,
                checked_name,
                shape,
                "cylindrical_roller_bearing",
                count,
                clearance,
            )
            result.addProperty("App::PropertyLength", "RollerDiameter", "Bearing")
            result.RollerDiameter = roller
            result.addProperty("App::PropertyLength", "RollerLength", "Bearing")
            result.RollerLength = checked_length
            result.addProperty("App::PropertyBool", "HasCage", "Bearing")
            result.HasCage = cage
            return result

        bearing = self._run_transaction(
            f"create cylindrical roller bearing {checked_name}", create
        )
        return {
            "name": bearing.Name,
            "label": bearing.Label,
            "bearing_type": "cylindrical_roller",
            "bore_diameter_mm": bore,
            "outer_diameter_mm": outer,
            "width_mm": checked_width,
            "roller_count": count,
            "roller_diameter_mm": roller,
            "roller_length_mm": checked_length,
            "pitch_diameter_mm": 2 * pitch_radius,
            "radial_clearance_mm": clearance,
            "has_cage": cage,
            "solid_count": len(bearing.Shape.Solids),
            "volume_mm3": float(bearing.Shape.Volume),
            "valid": True,
        }

    def create_print_in_place_roller_bearing(
        self,
        bore_diameter: float,
        outer_diameter: float,
        width: float,
        roller_count: int,
        roller_diameter: float,
        print_clearance: float = 0.4,
        axial_clearance: float = 1.8,
        name: str = "PrintInPlaceRollerBearing",
    ) -> dict[str, Any]:
        (
            bore,
            outer,
            checked_width,
            count,
            roller,
            bore_radius,
            outer_radius,
            pitch_radius,
        ) = self._bearing_dimensions(
            bore_diameter,
            outer_diameter,
            width,
            roller_count,
            roller_diameter,
            element_name="rollers",
        )
        clearance = self._positive_values(print_clearance)[0]
        axial = self._positive_values(axial_clearance)[0]
        if roller + 2 * clearance >= outer_radius - bore_radius:
            raise ValueError(
                "Rollers and print clearances do not fit between the races: "
                f"roller {roller:.2f} mm plus two clearances of {clearance:.2f} mm "
                f"needs less than the {outer_radius - bore_radius:.2f} mm of radial "
                "space between bore and outer wall."
            )
        self._check_circumferential_spacing(pitch_radius, count, roller, clearance)
        roller_radius = roller / 2
        lip_depth = clearance + roller_radius * 0.25
        lip_height = lip_depth
        if axial <= lip_height + clearance:
            raise ValueError(
                "Axial clearance must exceed the retaining-rim height plus print "
                f"clearance: the {lip_height:.2f} mm rim plus the {clearance:.2f} mm "
                f"clearance requires more than {lip_height + clearance:.2f} mm, but "
                f"axial_clearance is {axial:.2f} mm."
            )
        roller_length = checked_width - 2 * axial
        if roller_length <= 0:
            raise ValueError(
                "Axial clearances leave no printable roller length: width "
                f"{checked_width:.2f} mm minus two ends of {axial:.2f} mm leaves "
                f"{roller_length:.2f} mm."
            )
        inner_outer_radius = pitch_radius - roller_radius - clearance
        outer_inner_radius = pitch_radius + roller_radius + clearance
        lip_inner_radius = outer_inner_radius - lip_depth
        face_opening = lip_inner_radius - inner_outer_radius
        if face_opening >= roller:
            raise ValueError(
                "Retaining rims do not capture the requested rollers: the "
                f"{face_opening:.2f} mm face opening must stay below the "
                f"{roller:.2f} mm roller diameter. Use larger rollers or a "
                "smaller print clearance."
            )
        checked_name = self._validated_object_name(name)
        app, part = self._modules()

        def create(document: Any) -> Any:
            inner = part.makeCylinder(inner_outer_radius, checked_width).cut(
                part.makeCylinder(bore_radius, checked_width)
            )
            outer_race = part.makeCylinder(outer_radius, checked_width).cut(
                part.makeCylinder(outer_inner_radius, checked_width)
            )
            bottom_lip = part.makeCylinder(outer_radius, lip_height).cut(
                part.makeCone(lip_inner_radius, outer_inner_radius, lip_height)
            )
            top_z = checked_width - lip_height
            top_lip = part.makeCylinder(
                outer_radius, lip_height, app.Vector(0, 0, top_z)
            ).cut(
                part.makeCone(
                    outer_inner_radius,
                    lip_inner_radius,
                    lip_height,
                    app.Vector(0, 0, top_z),
                )
            )
            outer_race = outer_race.fuse(bottom_lip).fuse(top_lip).removeSplitter()
            rollers = []
            for index in range(count):
                angle = math.radians(index * 360 / count)
                rollers.append(
                    part.makeCylinder(
                        roller_radius,
                        roller_length,
                        app.Vector(
                            pitch_radius * math.cos(angle),
                            pitch_radius * math.sin(angle),
                            axial,
                        ),
                    )
                )
            shape = part.makeCompound([inner, outer_race, *rollers])
            result = self._bearing_feature(
                document,
                checked_name,
                shape,
                "print_in_place_cylindrical_roller_bearing",
                count,
                2 * clearance,
            )
            result.addProperty("App::PropertyLength", "PrintClearance", "Printing")
            result.PrintClearance = clearance
            result.addProperty("App::PropertyLength", "AxialClearance", "Printing")
            result.AxialClearance = axial
            result.addProperty("App::PropertyString", "PrintOrientation", "Printing")
            result.PrintOrientation = "axis_z_upright"
            result.addProperty("App::PropertyString", "ReleaseMethod", "Printing")
            result.ReleaseMethod = "rotate_after_cooling_and_remove_loose_debris"
            return result

        bearing = self._run_transaction(
            f"create print-in-place roller bearing {checked_name}", create
        )
        return {
            "name": bearing.Name,
            "label": bearing.Label,
            "bearing_type": "print_in_place_cylindrical_roller",
            "bore_diameter_mm": bore,
            "outer_diameter_mm": outer,
            "width_mm": checked_width,
            "roller_count": count,
            "roller_diameter_mm": roller,
            "roller_length_mm": roller_length,
            "pitch_diameter_mm": 2 * pitch_radius,
            "print_clearance_mm_each_side": clearance,
            "axial_clearance_mm_each_end": axial,
            "retaining_rim_angle_deg": 45.0,
            "print_orientation": "axis_z_upright",
            "solid_count": len(bearing.Shape.Solids),
            "volume_mm3": float(bearing.Shape.Volume),
            "valid": True,
        }

    def create_printed_plain_bushing(
        self,
        shaft_diameter: float,
        outer_diameter: float,
        length: float,
        running_clearance: float = 0.3,
        channel_count: int = 6,
        channel_width: float = 0.8,
        channel_depth: float = 0.4,
        elephant_foot_relief: float = 0.2,
        name: str = "PrintedPlainBushing",
    ) -> dict[str, Any]:
        shaft, outer, checked_length, width, depth = self._positive_values(
            shaft_diameter, outer_diameter, length, channel_width, channel_depth
        )
        clearance = self._positive_values(running_clearance)[0]
        relief = self._checked_clearance(
            elephant_foot_relief, "Elephant-foot relief"
        )
        count = int(channel_count)
        if isinstance(channel_count, bool) or count != channel_count or not 0 <= count <= 24:
            raise ValueError("A printed bushing accepts between 0 and 24 channels.")
        bore = shaft + clearance
        if bore >= outer:
            raise ValueError("Bushing outer diameter must exceed its running bore.")
        bore_radius = bore / 2
        outer_radius = outer / 2
        wall = outer_radius - bore_radius
        if depth >= wall * 0.65:
            raise ValueError("Lubrication channels leave insufficient bushing wall.")
        if width >= 2 * math.pi * bore_radius / max(count, 1):
            raise ValueError("Lubrication channels overlap around the running bore.")
        if relief >= wall * 0.5:
            raise ValueError("Elephant-foot relief leaves insufficient bottom wall.")
        checked_name = self._validated_object_name(name)
        app, part = self._modules()

        def create(document: Any) -> Any:
            shape = part.makeCylinder(outer_radius, checked_length).cut(
                part.makeCylinder(bore_radius, checked_length)
            )
            if count:
                cutters = []
                for index in range(count):
                    cutter = part.makeBox(
                        depth + 0.02,
                        width,
                        checked_length + 0.02,
                        app.Vector(bore_radius - 0.01, -width / 2, -0.01),
                    )
                    cutter.rotate(
                        app.Vector(0, 0, 0),
                        app.Vector(0, 0, 1),
                        index * 360 / count,
                    )
                    cutters.append(cutter)
                shape = shape.cut(part.makeCompound(cutters))
            relief_height = min(max(0.4, relief * 2), checked_length * 0.2)
            if relief:
                shape = shape.cut(
                    part.makeCylinder(bore_radius + relief, relief_height)
                )
            shape = shape.removeSplitter()
            result = self._bearing_feature(
                document,
                checked_name,
                shape,
                "additive_plain_bushing",
                0,
                clearance,
            )
            result.addProperty("App::PropertyInteger", "ChannelCount", "Printing")
            result.ChannelCount = count
            result.addProperty("App::PropertyLength", "ChannelDepth", "Printing")
            result.ChannelDepth = depth
            result.addProperty("App::PropertyLength", "ElephantFootRelief", "Printing")
            result.ElephantFootRelief = relief
            result.addProperty("App::PropertyString", "PrintOrientation", "Printing")
            result.PrintOrientation = "axis_z_upright"
            return result

        bushing = self._run_transaction(
            f"create printed plain bushing {checked_name}", create
        )
        return {
            "name": bushing.Name,
            "label": bushing.Label,
            "bearing_type": "additive_plain_bushing",
            "shaft_diameter_mm": shaft,
            "running_bore_diameter_mm": bore,
            "outer_diameter_mm": outer,
            "length_mm": checked_length,
            "running_clearance_mm": clearance,
            "channel_count": count,
            "channel_width_mm": width,
            "channel_depth_mm": depth,
            "elephant_foot_relief_mm": relief,
            "print_orientation": "axis_z_upright",
            "solid_count": len(bushing.Shape.Solids),
            "volume_mm3": float(bushing.Shape.Volume),
            "valid": True,
        }

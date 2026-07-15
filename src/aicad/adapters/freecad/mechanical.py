from __future__ import annotations

import math
from typing import Any


class MechanicalMixin:
    """Niche mechanical parts: gears and threads."""

    @staticmethod
    def _checked_gear_phase(phase: Any) -> float:
        checked_phase = float(phase)
        if not math.isfinite(checked_phase) or not -360 <= checked_phase <= 360:
            raise ValueError("The gear phase must be between -360 and 360 degrees.")
        return checked_phase

    def create_spur_gear(
        self,
        teeth: int,
        module: float,
        thickness: float,
        bore_diameter: float,
        pressure_angle: float = 20,
        phase: float = 0,
        name: str = "SpurGear",
    ) -> dict[str, Any]:
        checked_teeth = int(teeth)
        if isinstance(teeth, bool) or checked_teeth != teeth or not 6 <= checked_teeth <= 200:
            raise ValueError("A spur gear requires between 6 and 200 whole teeth.")
        checked_module, checked_thickness = self._positive_values(module, thickness)
        checked_bore = float(bore_diameter)
        checked_pressure = float(pressure_angle)
        checked_phase = self._checked_gear_phase(phase)
        if not math.isfinite(checked_bore) or checked_bore < 0:
            raise ValueError("The bore diameter cannot be negative.")
        if not math.isfinite(checked_pressure) or not 14.5 <= checked_pressure <= 25:
            raise ValueError("The pressure angle must be between 14.5 and 25 degrees.")
        root_diameter = checked_module * (checked_teeth - 2.5)
        if checked_bore >= root_diameter:
            raise ValueError("The bore does not fit inside the gear root diameter.")
        checked_name = self._validated_object_name(name)
        app, part = self._modules()

        def create(document: Any) -> Any:
            self._ensure_new_name(document, checked_name)
            profile_name = self._ensure_new_name(
                document,
                f"{checked_name[:56]}Profile",
            )
            from PartDesign import InvoluteGearFeature

            profile = InvoluteGearFeature.makeInvoluteGear(profile_name)
            profile.Label = f"{checked_name} profile"
            profile.NumberOfTeeth = checked_teeth
            profile.Modules = checked_module
            profile.PressureAngle = checked_pressure
            profile.HighPrecision = True
            profile.ExternalGear = True
            document.recompute()
            wire = profile.Shape
            if wire.isNull() or not wire.isValid() or not wire.isClosed():
                raise RuntimeError("FreeCAD did not produce a valid closed gear profile.")
            if checked_phase:
                wire = wire.copy()
                wire.rotate(app.Vector(0, 0, 0), app.Vector(0, 0, 1), checked_phase)
            shape = part.Face(wire).extrude(app.Vector(0, 0, checked_thickness))
            if checked_bore > 0:
                bore = part.makeCylinder(checked_bore / 2, checked_thickness)
                shape = shape.cut(bore)
            result = self._derived_feature(
                document,
                checked_name,
                shape,
                (profile,),
                "involute_spur_gear",
            )
            result.addProperty("App::PropertyInteger", "NumberOfTeeth", "Gear")
            result.NumberOfTeeth = checked_teeth
            result.addProperty("App::PropertyLength", "GearModule", "Gear")
            result.GearModule = checked_module
            result.addProperty("App::PropertyAngle", "PressureAngle", "Gear")
            result.PressureAngle = checked_pressure
            result.addProperty("App::PropertyAngle", "PhaseAngle", "Gear")
            result.PhaseAngle = checked_phase
            result.addProperty("App::PropertyLength", "Thickness", "Gear")
            result.Thickness = checked_thickness
            result.addProperty("App::PropertyLength", "BoreDiameter", "Gear")
            result.BoreDiameter = checked_bore
            return result

        gear = self._run_transaction(f"create spur gear {checked_name}", create)
        return {
            "name": gear.Name,
            "label": gear.Label,
            "teeth": checked_teeth,
            "module_mm": checked_module,
            "pressure_angle_deg": checked_pressure,
            "phase_deg": checked_phase,
            "thickness_mm": checked_thickness,
            "bore_diameter_mm": checked_bore,
            "pitch_diameter_mm": checked_module * checked_teeth,
            "outside_diameter_mm": checked_module * (checked_teeth + 2),
            "mesh_phase_deg": 180 / checked_teeth,
            "volume_mm3": float(gear.Shape.Volume),
            "valid": True,
        }

    def create_helical_gear(
        self,
        teeth: int,
        module: float,
        thickness: float,
        helix_angle: float,
        bore_diameter: float,
        pressure_angle: float = 20,
        phase: float = 0,
        name: str = "HelicalGear",
    ) -> dict[str, Any]:
        checked_teeth = int(teeth)
        if isinstance(teeth, bool) or checked_teeth != teeth or not 6 <= checked_teeth <= 200:
            raise ValueError("A helical gear requires between 6 and 200 whole teeth.")
        checked_module, checked_thickness = self._positive_values(module, thickness)
        checked_helix = self._finite_float(helix_angle)
        if checked_helix is None or not 1 <= abs(checked_helix) <= 45:
            raise ValueError(
                "The helix angle magnitude must be between 1 and 45 degrees."
            )
        checked_bore = float(bore_diameter)
        checked_pressure = float(pressure_angle)
        checked_phase = self._checked_gear_phase(phase)
        if not math.isfinite(checked_bore) or checked_bore < 0:
            raise ValueError("The bore diameter cannot be negative.")
        if not math.isfinite(checked_pressure) or not 14.5 <= checked_pressure <= 25:
            raise ValueError("The pressure angle must be between 14.5 and 25 degrees.")
        root_diameter = checked_module * (checked_teeth - 2.5)
        if checked_bore >= root_diameter:
            raise ValueError("The bore does not fit inside the gear root diameter.")
        checked_name = self._validated_object_name(name)
        pitch_radius = checked_module * checked_teeth / 2
        twist_deg = math.degrees(
            checked_thickness * math.tan(math.radians(checked_helix)) / pitch_radius
        )
        app, part = self._modules()

        def create(document: Any) -> Any:
            self._ensure_new_name(document, checked_name)
            profile_name = self._ensure_new_name(
                document,
                f"{checked_name[:56]}Profile",
            )
            from PartDesign import InvoluteGearFeature

            profile = InvoluteGearFeature.makeInvoluteGear(profile_name)
            profile.Label = f"{checked_name} profile"
            profile.NumberOfTeeth = checked_teeth
            profile.Modules = checked_module
            profile.PressureAngle = checked_pressure
            profile.HighPrecision = True
            profile.ExternalGear = True
            document.recompute()
            wire = profile.Shape
            if wire.isNull() or not wire.isValid() or not wire.isClosed():
                raise RuntimeError("FreeCAD did not produce a valid closed gear profile.")
            base_wire = wire.copy()
            if checked_phase:
                base_wire.rotate(app.Vector(0, 0, 0), app.Vector(0, 0, 1), checked_phase)
            # ponytail: helicoid approximated by lofted sections every <=5
            # degrees of twist; switch to a true helix sweep if flank
            # accuracy ever matters beyond printing.
            section_count = max(2, int(math.ceil(abs(twist_deg) / 5)) + 1)
            sections = []
            for index in range(section_count):
                fraction = index / (section_count - 1)
                section = base_wire.copy()
                section.rotate(
                    app.Vector(0, 0, 0),
                    app.Vector(0, 0, 1),
                    twist_deg * fraction,
                )
                section.translate(app.Vector(0, 0, checked_thickness * fraction))
                sections.append(section)
            shape = part.makeLoft(sections, True, False)
            if checked_bore > 0:
                bore = part.makeCylinder(checked_bore / 2, checked_thickness)
                shape = shape.cut(bore)
            result = self._derived_feature(
                document,
                checked_name,
                shape,
                (profile,),
                "involute_helical_gear",
            )
            result.addProperty("App::PropertyInteger", "NumberOfTeeth", "Gear")
            result.NumberOfTeeth = checked_teeth
            result.addProperty("App::PropertyLength", "GearModule", "Gear")
            result.GearModule = checked_module
            result.addProperty("App::PropertyAngle", "PressureAngle", "Gear")
            result.PressureAngle = checked_pressure
            result.addProperty("App::PropertyAngle", "HelixAngle", "Gear")
            result.HelixAngle = checked_helix
            result.addProperty("App::PropertyAngle", "PhaseAngle", "Gear")
            result.PhaseAngle = checked_phase
            result.addProperty("App::PropertyLength", "Thickness", "Gear")
            result.Thickness = checked_thickness
            result.addProperty("App::PropertyLength", "BoreDiameter", "Gear")
            result.BoreDiameter = checked_bore
            return result

        gear = self._run_transaction(f"create helical gear {checked_name}", create)
        return {
            "name": gear.Name,
            "label": gear.Label,
            "teeth": checked_teeth,
            "module_mm": checked_module,
            "pressure_angle_deg": checked_pressure,
            "helix_angle_deg": checked_helix,
            "phase_deg": checked_phase,
            "thickness_mm": checked_thickness,
            "bore_diameter_mm": checked_bore,
            "pitch_diameter_mm": checked_module * checked_teeth,
            "outside_diameter_mm": checked_module * (checked_teeth + 2),
            "mesh_phase_deg": 180 / checked_teeth,
            "volume_mm3": float(gear.Shape.Volume),
            "valid": True,
        }

    def create_external_thread(
        self,
        diameter: float,
        pitch: float,
        length: float,
        name: str = "AIThread",
    ) -> dict[str, Any]:
        checked_diameter, checked_pitch, checked_length = self._positive_values(
            diameter, pitch, length
        )
        if checked_pitch >= checked_diameter / 4:
            raise ValueError(
                "The thread pitch must be smaller than a quarter of the diameter."
            )
        if checked_length < checked_pitch:
            raise ValueError("The thread length must cover at least one pitch.")
        if checked_length / checked_pitch > 64:
            raise ValueError("The thread cannot exceed 64 turns.")
        profile_height = checked_pitch * math.sqrt(3) / 2
        major_radius = checked_diameter / 2
        minor_radius = major_radius - 5 * profile_height / 8
        checked_name = self._validated_object_name(name)
        app, part = self._modules()

        def create(document: Any) -> Any:
            self._ensure_new_name(document, checked_name)
            helix = part.makeHelix(checked_pitch, checked_length, minor_radius)
            overlap = checked_pitch / 10
            profile = part.makePolygon(
                [
                    app.Vector(minor_radius - overlap, 0, -checked_pitch * 7 / 16),
                    app.Vector(minor_radius - overlap, 0, checked_pitch * 7 / 16),
                    app.Vector(major_radius, 0, 0),
                    app.Vector(minor_radius - overlap, 0, -checked_pitch * 7 / 16),
                ]
            )
            ridge = part.Wire(helix.Edges).makePipeShell([profile], True, True)
            core = part.makeCylinder(minor_radius, checked_length)
            shape = core.fuse(ridge)
            trim = part.makeCylinder(
                major_radius + checked_pitch,
                checked_length,
            )
            shape = shape.common(trim)
            if not shape.Solids or float(shape.Volume) <= float(core.Volume):
                raise RuntimeError("FreeCAD did not produce a valid thread ridge.")
            return self._derived_feature(
                document,
                checked_name,
                shape,
                (),
                "external_thread",
            )

        thread = self._run_transaction(f"create thread {checked_name}", create)
        return {
            "name": thread.Name,
            "label": thread.Label,
            "diameter_mm": checked_diameter,
            "pitch_mm": checked_pitch,
            "length_mm": checked_length,
            "minor_diameter_mm": 2 * minor_radius,
            "volume_mm3": float(thread.Shape.Volume),
            "valid": True,
        }

    def create_internal_gear(
        self,
        teeth: int,
        module: float,
        thickness: float,
        rim_thickness: float,
        pressure_angle: float = 20,
        phase: float = 0,
        name: str = "InternalGear",
    ) -> dict[str, Any]:
        checked_teeth = int(teeth)
        if (
            isinstance(teeth, bool)
            or checked_teeth != teeth
            or not 12 <= checked_teeth <= 240
        ):
            raise ValueError("An internal gear requires between 12 and 240 whole teeth.")
        checked_module, checked_thickness, checked_rim = self._positive_values(
            module, thickness, rim_thickness
        )
        checked_pressure = float(pressure_angle)
        checked_phase = self._checked_gear_phase(phase)
        if not math.isfinite(checked_pressure) or not 14.5 <= checked_pressure <= 25:
            raise ValueError("The pressure angle must be between 14.5 and 25 degrees.")
        if checked_rim < checked_module:
            raise ValueError("The internal gear rim must be at least one module thick.")
        checked_name = self._validated_object_name(name)
        pitch_radius = checked_module * checked_teeth / 2
        dedendum = 1.25 * checked_module
        outer_radius = pitch_radius + dedendum + checked_rim
        app, part = self._modules()

        def create(document: Any) -> Any:
            self._ensure_new_name(document, checked_name)
            profile_name = self._ensure_new_name(
                document, f"{checked_name[:56]}Profile"
            )
            from PartDesign import InvoluteGearFeature

            profile = InvoluteGearFeature.makeInvoluteGear(profile_name)
            profile.Label = f"{checked_name} profile"
            profile.NumberOfTeeth = checked_teeth
            profile.Modules = checked_module
            profile.PressureAngle = checked_pressure
            # Internal-gear pockets are boolean-heavy; the single four-point
            # involute keeps the exact pitch geometry while avoiding hundreds
            # of B-spline fragments in later backlash and interference checks.
            profile.HighPrecision = False
            profile.ExternalGear = False
            profile.AddendumCoefficient = 0.6
            profile.DedendumCoefficient = 1.25
            profile.RootFilletCoefficient = 0.38
            document.recompute()
            wire = profile.Shape
            if wire.isNull() or not wire.isValid() or not wire.isClosed():
                raise RuntimeError(
                    "FreeCAD did not produce a valid closed internal gear profile."
                )
            if checked_phase:
                wire = wire.copy()
                wire.rotate(app.Vector(0, 0, 0), app.Vector(0, 0, 1), checked_phase)
            pocket = part.Face(wire).extrude(app.Vector(0, 0, checked_thickness))
            rim = part.makeCylinder(outer_radius, checked_thickness)
            shape = rim.cut(pocket)
            result = self._derived_feature(
                document,
                checked_name,
                shape,
                (profile,),
                "involute_internal_gear",
            )
            result.addProperty("App::PropertyInteger", "NumberOfTeeth", "Gear")
            result.NumberOfTeeth = checked_teeth
            result.addProperty("App::PropertyLength", "GearModule", "Gear")
            result.GearModule = checked_module
            result.addProperty("App::PropertyAngle", "PressureAngle", "Gear")
            result.PressureAngle = checked_pressure
            result.addProperty("App::PropertyAngle", "PhaseAngle", "Gear")
            result.PhaseAngle = checked_phase
            result.addProperty("App::PropertyLength", "Thickness", "Gear")
            result.Thickness = checked_thickness
            result.addProperty("App::PropertyLength", "RimThickness", "Gear")
            result.RimThickness = checked_rim
            result.addProperty("App::PropertyBool", "InternalGear", "Gear")
            result.InternalGear = True
            return result

        gear = self._run_transaction(f"create internal gear {checked_name}", create)
        return {
            "name": gear.Name,
            "label": gear.Label,
            "teeth": checked_teeth,
            "module_mm": checked_module,
            "pressure_angle_deg": checked_pressure,
            "phase_deg": checked_phase,
            "thickness_mm": checked_thickness,
            "rim_thickness_mm": checked_rim,
            "pitch_diameter_mm": checked_module * checked_teeth,
            "inner_tip_diameter_mm": checked_module * (checked_teeth - 1.2),
            "root_diameter_mm": checked_module * (checked_teeth + 2.5),
            "outside_diameter_mm": 2 * outer_radius,
            "mesh_phase_deg": 180 / checked_teeth,
            "volume_mm3": float(gear.Shape.Volume),
            "valid": True,
        }

    def create_threaded_hole(
        self,
        object: str,
        diameter: float,
        pitch: float,
        x: float,
        y: float,
        depth: float,
        name: str = "AIThreadedHole",
    ) -> dict[str, Any]:
        checked_diameter, checked_pitch, checked_depth = self._positive_values(
            diameter, pitch, depth
        )
        if checked_pitch >= checked_diameter / 4:
            raise ValueError(
                "The thread pitch must be smaller than a quarter of the diameter."
            )
        if checked_depth < checked_pitch:
            raise ValueError("The threaded hole depth must cover at least one pitch.")
        if checked_depth / checked_pitch > 64:
            raise ValueError("The threaded hole cannot exceed 64 turns.")
        checked_x = self._finite_float(x)
        checked_y = self._finite_float(y)
        if checked_x is None or checked_y is None:
            raise ValueError("Hole coordinates must be finite.")
        profile_height = checked_pitch * math.sqrt(3) / 2
        major_radius = checked_diameter / 2
        minor_radius = major_radius - 5 * profile_height / 8
        source = self._resolve_document_object(object)
        self._shape_or_error(source)
        app, part = self._modules()

        def cut(document: Any) -> Any:
            bounds = source.Shape.BoundBox
            if checked_depth >= float(bounds.ZLength):
                raise ValueError(
                    "The threaded hole depth must be smaller than the solid height."
                )
            top = float(bounds.ZMax)
            base = top - checked_depth
            # A tap-drill bore plus a helical ridge that removes material out to
            # the major radius; subtracting it leaves an internal 60-degree thread.
            helix = part.makeHelix(checked_pitch, checked_depth, minor_radius)
            overlap = checked_pitch / 10
            ridge_profile = part.makePolygon(
                [
                    app.Vector(minor_radius - overlap, 0, -checked_pitch * 7 / 16),
                    app.Vector(minor_radius - overlap, 0, checked_pitch * 7 / 16),
                    app.Vector(major_radius, 0, 0),
                    app.Vector(minor_radius - overlap, 0, -checked_pitch * 7 / 16),
                ]
            )
            ridge = part.Wire(helix.Edges).makePipeShell([ridge_profile], True, True)
            bore = part.makeCylinder(minor_radius, checked_depth)
            cutter = bore.fuse(ridge)
            trim = part.makeCylinder(major_radius + checked_pitch, checked_depth)
            cutter = cutter.common(trim)
            cutter.translate(app.Vector(checked_x, checked_y, base))
            result_shape = source.Shape.cut(cutter)
            if (
                result_shape.isNull()
                or not result_shape.isValid()
                or not result_shape.Solids
                or float(result_shape.Volume) <= 0
                or float(result_shape.Volume) >= float(source.Shape.Volume) - 1e-9
            ):
                raise ValueError("The threaded hole does not cut the selected solid.")
            return self._derived_feature(
                document,
                name,
                result_shape,
                (source,),
                "threaded_hole",
            )

        result = self._run_transaction("threaded_hole", cut)
        return {
            "name": result.Name,
            "label": result.Label,
            "diameter_mm": checked_diameter,
            "pitch_mm": checked_pitch,
            "depth_mm": checked_depth,
            "minor_diameter_mm": 2 * minor_radius,
            "valid": True,
        }

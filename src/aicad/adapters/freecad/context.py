from __future__ import annotations

import math
from typing import Any, Iterable

from aicad.core.context import (
    ContextDetailLevel,
    ContextObject,
    ContextPage,
    ContextSelection,
    ContextShapeSummary,
    ContextSnapshot,
    ContextSummary,
)
from aicad.core.visual_cache import (
    MAX_CAPTURE_BATCH_BYTES,
    MAX_CAPTURE_BYTES,
    capture_path,
    new_capture_path,
    prune_visual_cache,
    read_capture,
)


# "current" keeps whatever camera the user left in the GUI; the rest are the
# standard orientations, so a caller can ask for a reproducible framing.
_CAPTURE_VIEWS = {
    "current": None,
    "isometric": "viewAxonometric",
    "top": "viewTop",
    "bottom": "viewBottom",
    "front": "viewFront",
    "rear": "viewRear",
    "left": "viewLeft",
    "right": "viewRight",
}
_DEFAULT_CAPTURE_VIEWS = ("isometric", "front", "top", "right")


class ContextReadsMixin:
    """Read-only document, selection, measurement and visual context."""

    def get_document_summary(self) -> dict[str, Any]:
        app, _ = self._modules()
        document = app.ActiveDocument
        if document is None:
            return {"active": False, "name": None, "objects": []}
        return {
            "active": True,
            "name": document.Name,
            "label": document.Label,
            "objects": [
                {
                    "name": item.Name,
                    "label": item.Label,
                    "type_id": item.TypeId,
                    "has_error": bool(self._error_states(item)),
                }
                for item in document.Objects
            ],
        }

    def get_selection(self) -> dict[str, Any]:
        return {"selection": self._selection_records(required=True)}

    @staticmethod
    def _selection_records(*, required: bool) -> list[dict[str, Any]]:
        try:
            import FreeCADGui as Gui
        except ImportError as exc:
            if not required:
                return []
            raise RuntimeError("This operation must run inside FreeCAD GUI.") from exc
        selection_api = getattr(Gui, "Selection", None)
        if selection_api is None:
            if not required:
                return []
            raise RuntimeError("This operation must run inside FreeCAD GUI.")

        selection = []
        for selected in selection_api.getSelectionEx():
            item = selected.Object
            selection.append(
                {
                    "name": item.Name,
                    "label": item.Label,
                    "type_id": item.TypeId,
                    "subelements": list(selected.SubElementNames),
                }
            )
        return selection

    @classmethod
    def _shape_context(cls, item: Any) -> ContextShapeSummary | None:
        shape = getattr(item, "Shape", None)
        if shape is None:
            return None
        is_null = bool(shape.isNull())
        if is_null:
            return ContextShapeSummary(is_null=True, is_valid=False)
        bounds = shape.BoundBox
        bounds_mm = tuple(
            float(value)
            for value in (
                bounds.XMin,
                bounds.YMin,
                bounds.ZMin,
                bounds.XMax,
                bounds.YMax,
                bounds.ZMax,
            )
        )
        return ContextShapeSummary(
            is_null=False,
            is_valid=bool(shape.isValid()),
            volume_mm3=cls._finite_float(getattr(shape, "Volume", None)),
            area_mm2=cls._finite_float(getattr(shape, "Area", None)),
            bounds_mm=bounds_mm,
            solids=len(getattr(shape, "Solids", ())),
            faces=len(getattr(shape, "Faces", ())),
            edges=len(getattr(shape, "Edges", ())),
        )

    @classmethod
    def _parameter_context(cls, item: Any) -> dict[str, Any]:
        parameters: dict[str, Any] = {}
        for name in (
            "Length",
            "Width",
            "Height",
            "Radius",
            "Angle",
            "Diameter",
            "Count",
        ):
            if not hasattr(item, name):
                continue
            raw_value = getattr(item, name)
            value = getattr(raw_value, "Value", raw_value)
            if isinstance(value, bool):
                parameters[name] = value
            elif isinstance(value, (int, float)):
                checked = cls._finite_float(value)
                if checked is not None:
                    parameters[name] = checked
            elif isinstance(value, str) and len(value) <= 256:
                parameters[name] = value
        return parameters

    @classmethod
    def _object_context(cls, item: Any, selected_names: set[str]) -> ContextObject:
        position = None
        rotation = None
        placement = getattr(item, "Placement", None)
        if placement is not None:
            base = placement.Base
            position = (float(base.x), float(base.y), float(base.z))
            rotation = tuple(float(value) for value in placement.Rotation.Q)
        return ContextObject(
            name=item.Name,
            label=item.Label,
            type_id=item.TypeId,
            has_error=bool(cls._error_states(item)),
            selected=item.Name in selected_names,
            parameters=cls._parameter_context(item),
            position_mm=position,
            rotation_quaternion=rotation,
            shape=cls._shape_context(item),
        )

    def get_context_snapshot(
        self,
        detail_level: str = "work",
        max_objects: int = 25,
        cursor: int = 0,
    ) -> dict[str, Any]:
        try:
            level = ContextDetailLevel(detail_level)
        except ValueError as exc:
            raise ValueError("Unsupported context detail level.") from exc
        if isinstance(max_objects, bool) or not isinstance(max_objects, int):
            raise ValueError("Context object limit must be an integer.")
        if not 1 <= max_objects <= 100:
            raise ValueError("Context object limit must be between 1 and 100.")
        if isinstance(cursor, bool) or not isinstance(cursor, int) or cursor < 0:
            raise ValueError("Context cursor must be a non-negative integer.")

        app, _ = self._modules()
        document = app.ActiveDocument
        selection_records = self._selection_records(required=False)
        selection = tuple(ContextSelection.model_validate(item) for item in selection_records)
        selection_payload = [item.model_dump(mode="json") for item in selection]
        selection_fingerprint = self._fingerprint(selection_payload)

        if document is None:
            empty_fingerprint = self._fingerprint({"active": False})
            observation = self._context_tracker.observe(
                None,
                empty_fingerprint,
                selection_fingerprint,
                {},
            )
            snapshot = ContextSnapshot(
                detail_level=level,
                active=False,
                state_token=observation.token,
                summary=ContextSummary(
                    object_count=0,
                    error_count=0,
                    selected_count=len(selection),
                ),
                selection=selection if level is ContextDetailLevel.WORK else (),
                page=ContextPage(
                    cursor=0,
                    returned=0,
                    total_objects=0,
                    next_cursor=None,
                    truncated=False,
                ),
            )
            return snapshot.model_dump(mode="json")

        items = sorted(document.Objects, key=lambda item: item.Name)
        if cursor > len(items):
            raise ValueError("Context cursor exceeds the object count.")
        selected_names = {item.name for item in selection}
        context_objects = tuple(
            self._object_context(item, selected_names) for item in items
        )
        object_payloads = [item.model_dump(mode="json") for item in context_objects]
        object_fingerprints = {
            item.name: self._fingerprint(payload)
            for item, payload in zip(context_objects, object_payloads, strict=True)
        }
        document_fingerprint = self._fingerprint(
            {
                "name": document.Name,
                "label": document.Label,
                "objects": object_payloads,
            }
        )
        observation = self._context_tracker.observe(
            document.Name,
            document_fingerprint,
            selection_fingerprint,
            object_fingerprints,
        )

        if level is ContextDetailLevel.MINIMAL:
            returned_objects: tuple[ContextObject, ...] = ()
            next_cursor = 0 if context_objects else None
            page_cursor = 0
        else:
            returned_objects = context_objects[cursor : cursor + max_objects]
            following = cursor + len(returned_objects)
            next_cursor = following if following < len(context_objects) else None
            page_cursor = cursor

        snapshot = ContextSnapshot(
            detail_level=level,
            active=True,
            document_name=document.Name,
            document_label=document.Label,
            state_token=observation.token,
            summary=ContextSummary(
                object_count=len(context_objects),
                error_count=sum(item.has_error for item in context_objects),
                selected_count=len(selection),
            ),
            selection=selection if level is ContextDetailLevel.WORK else (),
            objects=returned_objects,
            recent_objects=observation.recent_objects,
            page=ContextPage(
                cursor=page_cursor,
                returned=len(returned_objects),
                total_objects=len(context_objects),
                next_cursor=next_cursor,
                truncated=next_cursor is not None,
            ),
        )
        return snapshot.model_dump(mode="json")

    def get_object_details(self, object: str) -> dict[str, Any]:
        item = self._resolve_document_object(object)
        shape = getattr(item, "Shape", None)
        edges = []
        if shape is not None and not shape.isNull():
            for edge in shape.Edges[:64]:
                signature, payload = self._edge_signature(edge)
                edges.append({"reference": signature, **payload})
        context = self._object_context(item, set())
        return {
            "status": "resolved",
            "object": context.model_dump(mode="json"),
            "editable_parameters": self._editable_parameter_records(item),
            "edge_references": edges,
            "edge_references_truncated": bool(
                shape is not None and len(shape.Edges) > len(edges)
            ),
        }

    def measure_object(self, object: str) -> dict[str, Any]:
        item = self._resolve_document_object(object)
        shape = self._shape_or_error(item)
        bounds = shape.BoundBox
        return {
            "name": item.Name,
            "label": item.Label,
            "length_mm": float(bounds.XLength),
            "width_mm": float(bounds.YLength),
            "height_mm": float(bounds.ZLength),
            "bounds_mm": [
                float(bounds.XMin),
                float(bounds.YMin),
                float(bounds.ZMin),
                float(bounds.XMax),
                float(bounds.YMax),
                float(bounds.ZMax),
            ],
            "center_mm": [
                float(bounds.Center.x),
                float(bounds.Center.y),
                float(bounds.Center.z),
            ],
            "volume_mm3": float(shape.Volume),
            "area_mm2": float(shape.Area),
            "solids": len(shape.Solids),
            "valid": bool(shape.isValid()),
        }

    def measure_mass_properties(self, object: str, density: float) -> dict[str, Any]:
        item = self._resolve_document_object(object)
        shape = self._shape_or_error(item)
        solids = shape.Solids
        if not solids:
            raise ValueError(
                "Mass properties require at least one solid; "
                f"{item.Label} has none."
            )
        total_volume = sum(float(solid.Volume) for solid in solids)
        if total_volume <= 0:
            raise ValueError(
                f"Mass properties require positive volume; {item.Label} "
                f"reports {total_volume:.6f} mm³."
            )
        # CenterOfMass em compostos não é definido de forma uniforme; a média
        # ponderada por volume dos sólidos vale para peça única e composto.
        center = [0.0, 0.0, 0.0]
        for solid in solids:
            weight = float(solid.Volume)
            solid_center = solid.CenterOfMass
            center[0] += float(solid_center.x) * weight
            center[1] += float(solid_center.y) * weight
            center[2] += float(solid_center.z) * weight
        center = [axis / total_volume for axis in center]
        mass_g = total_volume / 1000.0 * float(density)
        return {
            "name": item.Name,
            "label": item.Label,
            "density_g_cm3": float(density),
            "volume_mm3": total_volume,
            "mass_g": mass_g,
            "mass_kg": mass_g / 1000.0,
            "center_of_mass_mm": center,
            "solids": len(solids),
            "valid": bool(shape.isValid()),
        }

    def analyze_print_readiness(
        self,
        object: str,
        max_overhang_angle_deg: float = 45.0,
    ) -> dict[str, Any]:
        item = self._resolve_document_object(object)
        shape = self._shape_or_error(item)
        solids = shape.Solids
        if not solids:
            raise ValueError(
                "Print readiness requires at least one solid; "
                f"{item.Label} has none."
            )
        bounds = shape.BoundBox
        bed_z = float(bounds.ZMin)
        bed_tolerance = 0.01
        # Impressão em pé no plano da mesa: precisa de suporte a face voltada
        # para baixo mais rasa que o limite (normal amostrada no meio do domínio
        # UV — em faces curvas isso é uma heurística, não um veredicto).
        support_threshold = math.cos(math.radians(max_overhang_angle_deg))
        bed_contact_area = 0.0
        overhang_area = 0.0
        overhang_faces: list[dict[str, Any]] = []
        for index, face in enumerate(shape.Faces, start=1):
            u_min, u_max, v_min, v_max = face.ParameterRange
            normal = face.normalAt((u_min + u_max) / 2, (v_min + v_max) / 2)
            length = float(normal.Length)
            if length <= 0:
                continue
            downward = -float(normal.z) / length
            if downward <= 0:
                continue
            face_bounds = face.BoundBox
            on_bed = (
                downward > 0.999
                and float(face_bounds.ZMax) <= bed_z + bed_tolerance
            )
            if on_bed:
                bed_contact_area += float(face.Area)
                continue
            if downward > support_threshold:
                area = float(face.Area)
                overhang_area += area
                overhang_faces.append(
                    {
                        "face": f"Face{index}",
                        "area_mm2": area,
                        "downward_angle_deg": math.degrees(math.acos(downward)),
                        "center_mm": [
                            float(face_bounds.Center.x),
                            float(face_bounds.Center.y),
                            float(face_bounds.Center.z),
                        ],
                    }
                )
        overhang_faces.sort(key=lambda entry: entry["area_mm2"], reverse=True)
        floating_solids = []
        for index, solid in enumerate(solids, start=1):
            gap = float(solid.BoundBox.ZMin) - bed_z
            if gap > bed_tolerance:
                floating_solids.append(
                    {"solid": index, "gap_mm": gap}
                )
        return {
            "name": item.Name,
            "label": item.Label,
            "valid": bool(shape.isValid()),
            "solids": len(solids),
            "closed_solids": sum(bool(solid.isClosed()) for solid in solids),
            "build_direction": "+z",
            "max_overhang_angle_deg": float(max_overhang_angle_deg),
            "bed_z_mm": bed_z,
            "bed_contact_area_mm2": bed_contact_area,
            "overhang_area_mm2": overhang_area,
            "overhang_faces": overhang_faces[:16],
            "overhang_faces_truncated": len(overhang_faces) > 16,
            "floating_solids": floating_solids[:16],
            "needs_support": bool(overhang_faces),
            "normals_sampled_at_face_center": True,
        }

    def measure_distance(self, left: str, right: str) -> dict[str, Any]:
        left_item = self._resolve_document_object(left)
        right_item = self._resolve_document_object(right)
        if left_item is right_item:
            raise ValueError("Distance operands must be different objects.")
        left_shape = self._shape_or_error(left_item)
        right_shape = self._shape_or_error(right_item)
        minimum_distance, point_pairs, _ = left_shape.distToShape(right_shape)
        left_center = left_shape.BoundBox.Center
        right_center = right_shape.BoundBox.Center
        center_distance = (right_center - left_center).Length
        closest_points = []
        if point_pairs:
            left_point, right_point = point_pairs[0]
            closest_points = [
                [float(left_point.x), float(left_point.y), float(left_point.z)],
                [float(right_point.x), float(right_point.y), float(right_point.z)],
            ]
        return {
            "left": {"name": left_item.Name, "label": left_item.Label},
            "right": {"name": right_item.Name, "label": right_item.Label},
            "minimum_distance_mm": float(minimum_distance),
            "center_distance_mm": float(center_distance),
            "closest_points_mm": closest_points,
            "intersects_or_touches": float(minimum_distance) <= 1e-7,
        }

    def get_dependencies(self, object: str) -> dict[str, Any]:
        item = self._resolve_document_object(object)

        def records(items: Iterable[Any]) -> list[dict[str, str]]:
            return [
                {"name": linked.Name, "label": linked.Label, "type_id": linked.TypeId}
                for linked in sorted(items, key=lambda value: value.Name)
            ]

        return {
            "name": item.Name,
            "depends_on": records(getattr(item, "OutList", ())),
            "used_by": records(getattr(item, "InList", ())),
        }

    def resolve_object(self, reference: str = "") -> dict[str, Any]:
        checked = str(reference).strip()
        selection_aliases = {"selected", "selection", "selecionado", "seleção", "ele"}
        if not checked or checked.casefold() in selection_aliases:
            selected = self._selection_records(required=False)
            if len(selected) == 1:
                return {"status": "resolved", "object": selected[0]}
            return {
                "status": "awaiting_selection",
                "required": "one_object",
                "candidates": selected,
            }
        try:
            item = self._resolve_document_object(checked)
        except KeyError:
            return {"status": "not_found", "reference": checked}
        return {
            "status": "resolved",
            "object": {
                "name": item.Name,
                "label": item.Label,
                "type_id": item.TypeId,
                "subelements": [],
            },
        }

    @classmethod
    def _editable_parameter_records(cls, item: Any) -> list[dict[str, Any]]:
        allowed_by_type = {
            "Part::Box": ("Length", "Width", "Height"),
            "Part::Cylinder": ("Radius", "Height", "Angle"),
            "Part::Cone": ("Radius1", "Radius2", "Height", "Angle"),
            "Part::Sphere": ("Radius", "Angle1", "Angle2", "Angle3"),
            "PartDesign::Pad": ("Length",),
        }
        names = allowed_by_type.get(item.TypeId, ())
        records: list[dict[str, Any]] = []
        for name in names:
            if not hasattr(item, name):
                continue
            raw = getattr(item, name)
            value = getattr(raw, "Value", raw)
            checked = cls._finite_float(value)
            if checked is None:
                continue
            records.append(
                {
                    "name": name,
                    "value": checked,
                    "unit": "deg" if name.startswith("Angle") else "mm",
                    "minimum_exclusive": 0,
                }
            )
        return records

    def get_editable_parameters(self, object: str) -> dict[str, Any]:
        item = self._resolve_document_object(object)
        return {
            "name": item.Name,
            "label": item.Label,
            "parameters": self._editable_parameter_records(item),
        }

    def capture_view(
        self,
        width: int = 960,
        height: int = 640,
        view: str = "current",
        fit: bool = False,
    ) -> dict[str, Any]:
        checked_width, checked_height = self._capture_dimensions(width, height)
        checked_view = self._capture_view_name(view)
        self._validate_capture_fit(fit)
        active_view = self._active_gui_view()
        original_camera = active_view.getCamera()
        animation_enabled = bool(active_view.isAnimationEnabled())
        overlay_state = None
        capture_path = None
        try:
            active_view.setAnimationEnabled(False)
            overlay_state = self._hide_capture_overlays(active_view)
            self._restore_camera(active_view, original_camera)
            self._apply_capture_view(active_view, checked_view, fit)
            result, capture_path = self._capture_active_view(
                active_view,
                width=checked_width,
                height=checked_height,
                view=checked_view,
                fit=fit,
            )
        finally:
            restore_error = None
            try:
                self._restore_camera(active_view, original_camera)
            except Exception as exc:
                restore_error = exc
            if overlay_state is not None:
                try:
                    self._restore_capture_overlays(active_view, overlay_state)
                except Exception as exc:
                    restore_error = restore_error or exc
            try:
                active_view.setAnimationEnabled(animation_enabled)
            except Exception as exc:
                restore_error = restore_error or exc
            if restore_error is not None:
                if capture_path is not None:
                    capture_path.unlink(missing_ok=True)
                raise RuntimeError(
                    "The original FreeCAD visual state could not be restored."
                ) from restore_error
        prune_visual_cache()
        return {**result, "camera_restored": True}

    def capture_views(
        self,
        views: list[str] | None = None,
        width: int = 640,
        height: int = 480,
        fit: bool = True,
    ) -> dict[str, Any]:
        """Capture independent standard views and restore the user's camera."""

        checked_width, checked_height = self._capture_dimensions(width, height)
        self._validate_capture_fit(fit)
        if views is None:
            checked_views = _DEFAULT_CAPTURE_VIEWS
        else:
            if not isinstance(views, list) or not 1 <= len(views) <= 8:
                raise ValueError("Capture views requires between one and eight views.")
            checked_views = tuple(self._capture_view_name(view) for view in views)
            if len(set(checked_views)) != len(checked_views):
                raise ValueError("Capture views must be unique.")

        active_view = self._active_gui_view()
        original_camera = active_view.getCamera()
        animation_enabled = bool(active_view.isAnimationEnabled())
        overlay_state = None
        captures: list[dict[str, Any]] = []
        paths = []
        try:
            active_view.setAnimationEnabled(False)
            overlay_state = self._hide_capture_overlays(active_view)
            for checked_view in checked_views:
                self._restore_camera(active_view, original_camera)
                self._apply_capture_view(active_view, checked_view, fit)
                result, path = self._capture_active_view(
                    active_view,
                    width=checked_width,
                    height=checked_height,
                    view=checked_view,
                    fit=fit,
                )
                captures.append(result)
                paths.append(path)
                if sum(int(item["bytes"]) for item in captures) > (
                    MAX_CAPTURE_BATCH_BYTES
                ):
                    raise RuntimeError("The visual capture batch exceeded its size limit.")
        except Exception:
            for path in paths:
                path.unlink(missing_ok=True)
            raise
        finally:
            restore_error = None
            try:
                self._restore_camera(active_view, original_camera)
            except Exception as exc:
                restore_error = exc
            if overlay_state is not None:
                try:
                    self._restore_capture_overlays(active_view, overlay_state)
                except Exception as exc:
                    restore_error = restore_error or exc
            try:
                active_view.setAnimationEnabled(animation_enabled)
            except Exception as exc:
                restore_error = restore_error or exc
            if restore_error is not None:
                for path in paths:
                    path.unlink(missing_ok=True)
                raise RuntimeError(
                    "The original FreeCAD visual state could not be restored."
                ) from restore_error

        prune_visual_cache()
        return {
            "views": list(checked_views),
            "count": len(captures),
            "width": checked_width,
            "height": checked_height,
            "fit": fit,
            "total_bytes": sum(int(item["bytes"]) for item in captures),
            "camera_restored": True,
            "captures": captures,
        }

    def capture_section_view(
        self,
        plane: str = "xy",
        offset: float = 0.0,
        flip: bool = False,
        width: int = 640,
        height: int = 480,
        view: str = "isometric",
        fit: bool = True,
    ) -> dict[str, Any]:
        """Capture a temporary principal-plane clipping section."""

        checked_plane = str(plane).strip().lower()
        if checked_plane not in {"xy", "xz", "yz"}:
            raise ValueError("Section plane must be one of: xy, xz, yz.")
        if (
            isinstance(offset, bool)
            or not isinstance(offset, (int, float))
            or not math.isfinite(float(offset))
            or abs(float(offset)) > 1_000_000
        ):
            raise ValueError("Section offset must be finite and within safe limits.")
        if not isinstance(flip, bool):
            raise ValueError("Section flip must be a boolean value.")
        checked_width, checked_height = self._capture_dimensions(width, height)
        checked_view = self._capture_view_name(view)
        self._validate_capture_fit(fit)

        active_view = self._active_gui_view()
        has_clipping_plane = getattr(active_view, "hasClippingPlane", None)
        toggle_clipping_plane = getattr(active_view, "toggleClippingPlane", None)
        if has_clipping_plane is None or toggle_clipping_plane is None:
            raise RuntimeError("Visual section capture is unavailable in this FreeCAD.")
        if bool(has_clipping_plane()):
            raise RuntimeError(
                "A clipping plane is already active; disable it before capture."
            )

        app, _ = self._modules()
        point, normal = self._section_plane_definition(
            checked_plane,
            float(offset),
            flip,
        )
        placement = app.Placement(
            app.Vector(*point),
            app.Rotation(app.Vector(0, 0, 1), app.Vector(*normal)),
        )
        result = None
        cleanup_required = False
        try:
            cleanup_required = True
            toggle_clipping_plane(1, False, True, placement)
            active_view.redraw()
            self._sync_gui()
            if not bool(has_clipping_plane()):
                raise RuntimeError("The FreeCAD clipping plane could not be activated.")
            result = self.capture_view(
                width=checked_width,
                height=checked_height,
                view=checked_view,
                fit=fit,
            )
        finally:
            restore_error = None
            if cleanup_required:
                try:
                    if bool(has_clipping_plane()):
                        toggle_clipping_plane(0)
                    active_view.redraw()
                    self._sync_gui()
                    if bool(has_clipping_plane()):
                        raise RuntimeError("The clipping plane remains active.")
                except Exception as exc:
                    restore_error = exc
            if restore_error is not None:
                if result is not None:
                    capture_path(str(result["capture_id"])).unlink(missing_ok=True)
                raise RuntimeError(
                    "The original FreeCAD clipping state could not be restored."
                ) from restore_error

        return {
            **result,
            "plane": checked_plane,
            "offset_mm": float(offset),
            "flip": flip,
            "normal": list(normal),
            "kept_side": "positive_normal" if flip else "negative_normal",
            "capped": False,
            "clipping_restored": True,
        }

    @staticmethod
    def _section_plane_definition(
        plane: str,
        offset: float,
        flip: bool,
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        points = {
            "xy": (0.0, 0.0, offset),
            "xz": (0.0, offset, 0.0),
            "yz": (offset, 0.0, 0.0),
        }
        normals = {
            "xy": (0.0, 0.0, 1.0),
            "xz": (0.0, 1.0, 0.0),
            "yz": (1.0, 0.0, 0.0),
        }
        normal = normals[plane]
        if flip:
            normal = tuple(-component for component in normal)
        return points[plane], normal

    @staticmethod
    def _capture_dimensions(width: int, height: int) -> tuple[int, int]:
        if (
            isinstance(width, bool)
            or not isinstance(width, int)
            or isinstance(height, bool)
            or not isinstance(height, int)
            or not 320 <= width <= 1920
            or not 240 <= height <= 1080
        ):
            raise ValueError("Visual capture dimensions are outside the safe limits.")
        return width, height

    @staticmethod
    def _capture_view_name(view: str) -> str:
        checked_view = str(view).strip().lower()
        if checked_view not in _CAPTURE_VIEWS:
            raise ValueError(
                "Capture view must be one of: "
                + ", ".join(sorted(_CAPTURE_VIEWS))
                + "."
            )
        return checked_view

    @staticmethod
    def _validate_capture_fit(fit: bool) -> None:
        if not isinstance(fit, bool):
            raise ValueError("Capture fit must be a boolean value.")

    @staticmethod
    def _active_gui_view() -> Any:
        try:
            import FreeCADGui as Gui
        except ImportError as exc:
            raise RuntimeError("Visual context requires the FreeCAD GUI.") from exc
        gui_document = Gui.activeDocument()
        if gui_document is None:
            raise RuntimeError("No active GUI document is available.")
        return gui_document.activeView()

    @staticmethod
    def _apply_capture_view(active_view: Any, view: str, fit: bool) -> None:
        orientation = _CAPTURE_VIEWS[view]
        if orientation is not None:
            getattr(active_view, orientation)()
        if fit:
            active_view.fitAll()
        active_view.redraw()
        ContextReadsMixin._sync_gui()

    @staticmethod
    def _restore_camera(active_view: Any, camera: str) -> None:
        active_view.setCamera(camera)
        active_view.redraw()
        ContextReadsMixin._sync_gui()

    @staticmethod
    def _hide_capture_overlays(
        active_view: Any,
    ) -> tuple[Any, bool | None, bool | None, bool | None]:
        viewer = None
        navi_cube_visible = None
        axis_cross_visible = None
        corner_cross_visible = None
        get_viewer = getattr(active_view, "getViewer", None)
        if get_viewer is not None:
            viewer = get_viewer()
            is_navi_enabled = getattr(viewer, "isEnabledNaviCube", None)
            if is_navi_enabled is not None:
                navi_cube_visible = bool(is_navi_enabled())
        has_axis_cross = getattr(active_view, "hasAxisCross", None)
        if has_axis_cross is not None:
            axis_cross_visible = bool(has_axis_cross())
        is_corner_cross_visible = getattr(active_view, "isCornerCrossVisible", None)
        if is_corner_cross_visible is not None:
            corner_cross_visible = bool(is_corner_cross_visible())
        state = (
            viewer,
            navi_cube_visible,
            axis_cross_visible,
            corner_cross_visible,
        )
        try:
            if viewer is not None and navi_cube_visible is not None:
                viewer.setEnabledNaviCube(False)
            if axis_cross_visible is not None:
                active_view.setAxisCross(False)
            if corner_cross_visible is not None:
                active_view.setCornerCrossVisible(False)
            active_view.redraw()
            ContextReadsMixin._sync_gui()
        except Exception:
            ContextReadsMixin._restore_capture_overlays(active_view, state)
            raise
        return state

    @staticmethod
    def _restore_capture_overlays(
        active_view: Any,
        state: tuple[Any, bool | None, bool | None, bool | None],
    ) -> None:
        (
            viewer,
            navi_cube_visible,
            axis_cross_visible,
            corner_cross_visible,
        ) = state
        if viewer is not None and navi_cube_visible is not None:
            viewer.setEnabledNaviCube(navi_cube_visible)
        if axis_cross_visible is not None:
            active_view.setAxisCross(axis_cross_visible)
        if corner_cross_visible is not None:
            active_view.setCornerCrossVisible(corner_cross_visible)
        active_view.redraw()
        ContextReadsMixin._sync_gui()

    @staticmethod
    def _sync_gui() -> None:
        import FreeCADGui as Gui

        Gui.updateGui()

    @staticmethod
    def _capture_active_view(
        active_view: Any,
        *,
        width: int,
        height: int,
        view: str,
        fit: bool,
    ) -> tuple[dict[str, Any], Any]:
        capture_id, path = new_capture_path()
        try:
            ContextReadsMixin._save_viewport_image(
                active_view,
                path=path,
                width=width,
                height=height,
            )
            payload = read_capture(capture_id)
            if len(payload) > MAX_CAPTURE_BYTES:
                raise RuntimeError("The visual capture exceeded the size limit.")
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return (
            {
                "capture_id": capture_id,
                "mime_type": "image/png",
                "width": width,
                "height": height,
                "view": view,
                "fit": fit,
                "bytes": len(payload),
                "resource_uri": f"aicad://view/{capture_id}",
            },
            path,
        )

    @staticmethod
    def _save_viewport_image(
        active_view: Any,
        *,
        path: Any,
        width: int,
        height: int,
    ) -> None:
        """Save the visible OpenGL framebuffer, centered at the target ratio."""

        get_viewer = getattr(active_view, "getViewer", None)
        if get_viewer is None:
            # Small neutral adapters used outside FreeCAD expose saveImage only.
            active_view.saveImage(str(path), width, height, "Current")
            return

        viewer = get_viewer()
        image = ContextReadsMixin._grab_stable_framebuffer(active_view, viewer)

        source_width = int(image.width())
        source_height = int(image.height())
        target_ratio = width / height
        source_ratio = source_width / source_height
        if source_ratio > target_ratio:
            crop_width = max(1, round(source_height * target_ratio))
            image = image.copy(
                (source_width - crop_width) // 2,
                0,
                crop_width,
                source_height,
            )
        elif source_ratio < target_ratio:
            crop_height = max(1, round(source_width / target_ratio))
            image = image.copy(
                0,
                (source_height - crop_height) // 2,
                source_width,
                crop_height,
            )

        from PySide import QtCore

        image = image.scaled(
            width,
            height,
            QtCore.Qt.IgnoreAspectRatio,
            QtCore.Qt.SmoothTransformation,
        )
        if not image.save(str(path), "PNG"):
            raise RuntimeError("The FreeCAD viewport image could not be saved.")

    @staticmethod
    def _grab_stable_framebuffer(active_view: Any, viewer: Any) -> Any:
        """Wait for two equal OpenGL frames after a visual-state change."""

        previous = None
        repaint = getattr(viewer, "repaint", None)
        for _ in range(6):
            active_view.redraw()
            ContextReadsMixin._sync_gui()
            if repaint is not None:
                repaint()
                ContextReadsMixin._sync_gui()
            image = viewer.grabFramebuffer()
            if image.isNull() or image.width() <= 0 or image.height() <= 0:
                raise RuntimeError("The FreeCAD viewport framebuffer is unavailable.")
            if previous is not None and image == previous:
                return image
            previous = image
        raise RuntimeError(
            "The FreeCAD viewport did not stabilize before visual capture."
        )

from __future__ import annotations

from typing import Any


class ObjectMixin:
    """Safe lifecycle operations for document objects."""

    def duplicate_object(
        self,
        object: str,
        name: str,
        offset_x: float = 0,
        offset_y: float = 0,
        offset_z: float = 0,
    ) -> dict[str, Any]:
        checked_name = self._validated_object_name(name)
        offsets = tuple(
            self._finite_float(value) for value in (offset_x, offset_y, offset_z)
        )
        if any(value is None for value in offsets):
            raise ValueError("Duplicate offsets must be finite.")
        dx, dy, dz = offsets
        source = self._resolve_document_object(object)
        source_shape = self._shape_or_error(source)
        app, _ = self._modules()

        def duplicate(document: Any) -> Any:
            self._ensure_new_name(document, checked_name)
            copied_shape = source_shape.copy()
            copied_shape.Placement = app.Placement()
            result = document.addObject("Part::Feature", checked_name)
            result.Label = checked_name
            result.Shape = copied_shape
            source_placement = source.Placement
            base = source_placement.Base
            result.Placement = app.Placement(
                app.Vector(base.x + dx, base.y + dy, base.z + dz),
                source_placement.Rotation,
            )
            result.addProperty("App::PropertyString", "FeatureKind", "AI CAD")
            result.FeatureKind = "independent_duplicate"
            result.addProperty("App::PropertyString", "CopiedFrom", "AI CAD")
            result.CopiedFrom = source.Name
            return result

        result = self._run_transaction(f"duplicate {source.Name}", duplicate)
        return {
            "name": result.Name,
            "label": result.Label,
            "source": source.Name,
            "offset_mm": [dx, dy, dz],
            "valid": True,
        }

    def delete_object(self, object: str) -> dict[str, Any]:
        item = self._resolve_document_object(object)
        dependents = tuple(
            linked for linked in getattr(item, "InList", ()) if linked is not item
        )
        if dependents:
            names = ", ".join(sorted(linked.Name for linked in dependents))
            raise ValueError(
                "The object is used by other document objects and cannot be "
                f"deleted safely: {names}."
            )
        name = item.Name
        label = str(item.Label)

        def remove(document: Any) -> None:
            document.removeObject(name)
            return None

        self._run_transaction(f"delete {name}", remove, recent_names=())
        return {"name": name, "label": label, "deleted": True}

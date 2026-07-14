from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


class ExportMixin:
    """Controlled artifact export with explicit destinations and hashes."""

    _EXPORT_SUFFIXES = {
        "stl": (".stl",),
        "step": (".step", ".stp"),
        "fcstd": (".fcstd",),
    }

    @classmethod
    def _checked_export_destination(
        cls, destination: str, format_name: str, overwrite: bool
    ) -> Path:
        """Validate the destination before touching FreeCAD or the file."""

        path = Path(str(destination).strip())
        if not path.is_absolute():
            raise ValueError("The export destination must be an absolute path.")
        allowed = cls._EXPORT_SUFFIXES[format_name]
        if path.suffix.casefold() not in allowed:
            raise ValueError(
                "The export destination must end with "
                + " or ".join(allowed)
                + "."
            )
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError("The export destination must not be a symlink.")
        if not path.parent.is_dir():
            raise ValueError("The export destination directory does not exist.")
        if path.exists() and not overwrite:
            raise FileExistsError(
                "The export destination already exists; pass overwrite=true "
                "to replace it."
            )
        return path

    def _export_shape(
        self,
        format_name: str,
        destination: str,
        object: str,
        overwrite: bool,
    ) -> dict[str, Any]:
        path = self._checked_export_destination(destination, format_name, overwrite)
        document = self._active_document()
        validation = self._validate_document(document)
        if not validation["valid"]:
            raise RuntimeError(
                "The document has errors and cannot be exported: "
                + "; ".join(validation["errors"])
            )
        item = self._resolve_document_object(object)
        shape = self._shape_or_error(item)
        if not shape.Solids:
            raise RuntimeError("The referenced object has no solid to export.")

        partial = path.with_name(path.name + ".partial")
        try:
            if format_name == "stl":
                # ponytail: default tessellation; expose deflection if print
                # quality complaints appear.
                shape.exportStl(str(partial))
            else:
                shape.exportStep(str(partial))
            if not partial.is_file() or partial.stat().st_size == 0:
                raise RuntimeError("FreeCAD produced an empty export file.")
            partial.replace(path)
        finally:
            partial.unlink(missing_ok=True)
        payload = path.read_bytes()
        return {
            "destination": str(path),
            "format": format_name,
            "object": item.Name,
            "label": item.Label,
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "valid": True,
        }

    def export_stl(
        self, destination: str, object: str, overwrite: bool = False
    ) -> dict[str, Any]:
        return self._export_shape("stl", destination, object, overwrite)

    def export_step(
        self, destination: str, object: str, overwrite: bool = False
    ) -> dict[str, Any]:
        return self._export_shape("step", destination, object, overwrite)

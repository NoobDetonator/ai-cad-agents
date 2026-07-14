from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


class DocumentMixin:
    """Multi-document management: list, create, activate and save.

    Saving reuses the export destination checks provided by ``ExportMixin``.
    """

    def list_documents(self) -> dict[str, Any]:
        app, _ = self._modules()
        active = app.ActiveDocument
        return {
            "active_document": active.Name if active is not None else None,
            "documents": [
                {
                    "name": document.Name,
                    "label": document.Label,
                    "file_path": str(document.FileName) or None,
                    "object_count": len(document.Objects),
                }
                for document in app.listDocuments().values()
            ],
        }

    def new_document(self, name: str = "AICadDoc") -> dict[str, Any]:
        checked_name = self._validated_object_name(name)
        app, _ = self._modules()
        if checked_name in app.listDocuments():
            raise ValueError(f"A document named {checked_name} is already open.")
        document = app.newDocument(checked_name)
        document.UndoMode = 1
        return {
            "name": document.Name,
            "label": document.Label,
            "active": True,
            "valid": True,
        }

    def _resolve_open_document(self, reference: str) -> Any:
        app, _ = self._modules()
        checked = str(reference).strip()
        if not checked:
            raise ValueError("An explicit document reference is required.")
        documents = app.listDocuments()
        if checked in documents:
            return documents[checked]
        folded = checked.casefold()
        matches = [
            document
            for document in documents.values()
            if document.Name.casefold() == folded
            or str(document.Label).casefold() == folded
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError("The document reference is ambiguous.")
        raise KeyError(f"Unknown open document: {checked}")

    def set_active_document(self, document: str) -> dict[str, Any]:
        app, _ = self._modules()
        target = self._resolve_open_document(document)
        app.setActiveDocument(target.Name)
        return {
            "name": target.Name,
            "label": target.Label,
            "active": True,
            "valid": True,
        }

    def save_document(
        self, destination: str = "", overwrite: bool = False
    ) -> dict[str, Any]:
        checked_destination = str(destination).strip()
        path = (
            self._checked_export_destination(checked_destination, "fcstd", overwrite)
            if checked_destination
            else None
        )
        document = self._active_document()
        if path is None:
            existing = str(document.FileName)
            if not existing:
                raise ValueError(
                    "The document was never saved; pass an absolute .FCStd "
                    "destination."
                )
            document.save()
            saved = Path(existing)
        else:
            document.saveAs(str(path))
            saved = path
        payload = saved.read_bytes()
        return {
            "name": document.Name,
            "label": document.Label,
            "destination": str(saved),
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "valid": True,
        }

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Callable

from aicad.core.context import ContextStateTracker
from aicad.core.transactions import (
    CadTransactionOutcome,
    current_transaction_trace,
    mark_transaction,
    mark_undone_transaction,
    transaction_title,
)


class FreeCadAdapterBase:
    """Shared helpers, validation and the transactional mutation core."""

    def __init__(self, *, context_tracker: ContextStateTracker | None = None) -> None:
        self._context_tracker = context_tracker or ContextStateTracker()
        self._audited_transactions: list[tuple[str, str, int]] = []

    @staticmethod
    def _modules() -> tuple[Any, Any]:
        try:
            import FreeCAD as App
            import Part
        except ImportError as exc:
            raise RuntimeError("This operation must run inside FreeCAD.") from exc
        return App, Part

    @staticmethod
    def _error_states(item: Any) -> list[str]:
        states = [str(state) for state in item.State]
        error_words = ("error", "invalid", "failed", "exception")
        return [
            state for state in states if any(word in state.lower() for word in error_words)
        ]

    @staticmethod
    def _finite_float(value: Any) -> float | None:
        try:
            checked = float(value)
        except (TypeError, ValueError):
            return None
        return checked if math.isfinite(checked) else None

    @staticmethod
    def _fingerprint(value: Any) -> str:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _positive_values(*values: float) -> tuple[float, ...]:
        checked = tuple(float(value) for value in values)
        if any(not math.isfinite(value) or value <= 0 for value in checked):
            raise ValueError("All dimensions must be positive.")
        return checked

    @staticmethod
    def _validated_object_name(name: str) -> str:
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", name) is None:
            raise ValueError("The object name has an invalid format.")
        return name

    @staticmethod
    def _active_document() -> Any:
        try:
            import FreeCAD as App
        except ImportError as exc:
            raise RuntimeError("This operation must run inside FreeCAD.") from exc
        document = App.ActiveDocument
        if document is None:
            raise RuntimeError("No active CAD document is available.")
        return document

    @classmethod
    def _resolve_document_object(cls, reference: str) -> Any:
        document = cls._active_document()
        checked = str(reference).strip()
        if not checked:
            raise ValueError("An explicit object reference is required.")
        direct = document.getObject(checked)
        if direct is not None:
            return direct
        folded = checked.casefold()
        matches = [
            item
            for item in document.Objects
            if item.Name.casefold() == folded or str(item.Label).casefold() == folded
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError("The object reference is ambiguous.")
        raise KeyError(f"Unknown CAD object: {checked}")

    @classmethod
    def _shape_or_error(cls, item: Any) -> Any:
        shape = getattr(item, "Shape", None)
        if shape is None or shape.isNull() or not shape.isValid():
            raise RuntimeError("The referenced object has no valid shape.")
        return shape

    @classmethod
    def _edge_signature(cls, edge: Any) -> tuple[str, dict[str, Any]]:
        center = getattr(edge, "CenterOfMass", None)
        center_mm = (
            [float(center.x), float(center.y), float(center.z)]
            if center is not None
            else None
        )
        vertices = [
            [float(vertex.Point.x), float(vertex.Point.y), float(vertex.Point.z)]
            for vertex in getattr(edge, "Vertexes", ())[:2]
        ]
        curve = getattr(edge, "Curve", None)
        payload = {
            "curve": type(curve).__name__ if curve is not None else "unknown",
            "length_mm": round(float(edge.Length), 9),
            "center_mm": center_mm,
            "vertices_mm": vertices,
        }
        signature = "edge:" + cls._fingerprint(payload)[:24]
        return signature, payload

    def _resolve_edge(self, item: Any, reference: str) -> Any:
        shape = self._shape_or_error(item)
        matches = [
            edge
            for edge in shape.Edges
            if self._edge_signature(edge)[0] == reference
        ]
        if len(matches) != 1:
            raise ValueError("The geometric edge reference is stale or ambiguous.")
        return matches[0]

    @staticmethod
    def _ensure_undo(document: Any) -> None:
        if document.UndoMode == 0:
            document.UndoMode = 1

    @classmethod
    def _ensure_new_name(cls, document: Any, name: str) -> str:
        checked = cls._validated_object_name(name)
        if document.getObject(checked) is not None:
            raise ValueError(f"A CAD object named {checked} already exists.")
        return checked

    def _create_validated_shape(
        self,
        name: str,
        configure: Callable[[Any], Any],
    ) -> Any:
        app, _ = self._modules()
        document = app.ActiveDocument or app.newDocument("AICadDocument")
        if document.UndoMode == 0:
            document.UndoMode = 1
        label = transaction_title(f"create {name}")
        document.openTransaction(label)
        try:
            item = configure(document)
            item.Label = name
            document.recompute()
            if item.Shape.isNull() or not item.Shape.isValid():
                raise RuntimeError("FreeCAD produced an invalid shape.")
            validation = self._validate_document(document)
            if not validation["valid"]:
                raise RuntimeError(
                    "FreeCAD document validation failed: "
                    + "; ".join(validation["errors"])
                )
            document.commitTransaction()
            mark_transaction(CadTransactionOutcome.COMMITTED)
            self._remember_audited_transaction(label, document.UndoCount)
            self._context_tracker.record_recent(document.Name, (item.Name,))
        except Exception:
            document.abortTransaction()
            mark_transaction(CadTransactionOutcome.ABORTED)
            document.recompute()
            raise
        return item

    def _run_transaction(
        self,
        title: str,
        operation: Callable[[Any], Any],
        *,
        recent_names: tuple[str, ...] | None = None,
    ) -> Any:
        document = self._active_document()
        self._ensure_undo(document)
        label = transaction_title(title)
        document.openTransaction(label)
        try:
            item = operation(document)
            document.recompute()
            shape = getattr(item, "Shape", None)
            if shape is not None and (shape.isNull() or not shape.isValid()):
                raise RuntimeError("FreeCAD produced an invalid result shape.")
            validation = self._validate_document(document)
            if not validation["valid"]:
                raise RuntimeError(
                    "FreeCAD document validation failed: "
                    + "; ".join(validation["errors"])
                )
            document.commitTransaction()
            mark_transaction(CadTransactionOutcome.COMMITTED)
            self._remember_audited_transaction(label, document.UndoCount)
            recorded_names = recent_names
            if recorded_names is None:
                item_name = getattr(item, "Name", None)
                recorded_names = (item_name,) if item_name else ()
            if recorded_names:
                self._context_tracker.record_recent(document.Name, recorded_names)
            return item
        except Exception:
            document.abortTransaction()
            mark_transaction(CadTransactionOutcome.ABORTED)
            document.recompute()
            raise

    def _remember_audited_transaction(self, label: str, undo_count: int) -> None:
        trace = current_transaction_trace()
        if trace is not None:
            self._audited_transactions.append(
                (trace.transaction_id, label, int(undo_count))
            )

    @classmethod
    def _derived_feature(
        cls,
        document: Any,
        name: str,
        shape: Any,
        sources: tuple[Any, ...],
        feature_kind: str,
    ) -> Any:
        if shape.isNull() or not shape.isValid() or not shape.Solids:
            raise RuntimeError("The mechanical operation did not produce a valid solid.")
        checked_name = cls._ensure_new_name(document, name)
        result = document.addObject("PartDesign::Feature", checked_name)
        result.Label = checked_name
        result.Shape = shape
        result.addProperty("App::PropertyLinkList", "SourceObjects", "AI CAD")
        result.SourceObjects = list(sources)
        result.addProperty("App::PropertyString", "FeatureKind", "AI CAD")
        result.FeatureKind = feature_kind
        for source in sources:
            view = getattr(source, "ViewObject", None)
            if view is not None:
                view.Visibility = False
        return result

    def _validate_document(self, document: Any) -> dict[str, Any]:
        if document is None:
            return {"valid": False, "errors": ["No active document."]}
        document.recompute()
        errors: list[str] = []
        for item in document.Objects:
            error_states = self._error_states(item)
            if error_states:
                errors.append(f"{item.Name}: {', '.join(error_states)}")
            shape = getattr(item, "Shape", None)
            if shape is not None and not shape.isNull() and not shape.isValid():
                errors.append(f"{item.Name}: invalid shape")
        return {"valid": not errors, "errors": errors}

    def validate_document(self) -> dict[str, Any]:
        app, _ = self._modules()
        return self._validate_document(app.ActiveDocument)

    def undo(self) -> dict[str, bool]:
        app, _ = self._modules()
        document = app.ActiveDocument
        if document is None or document.UndoCount == 0:
            return {"undone": False}
        undo_count = int(document.UndoCount)
        while (
            self._audited_transactions
            and self._audited_transactions[-1][2] > undo_count
        ):
            self._audited_transactions.pop()
        audited = (
            self._audited_transactions[-1]
            if self._audited_transactions
            and self._audited_transactions[-1][2] == undo_count
            else None
        )
        document.undo()
        document.recompute()
        if audited is not None:
            transaction_id, label, _ = self._audited_transactions.pop()
            mark_undone_transaction(transaction_id, label)
        else:
            trace = current_transaction_trace()
            if trace is not None:
                trace.label = "FreeCAD undo of an untracked transaction"
                trace.outcome = CadTransactionOutcome.UNDONE
        return {"undone": True}

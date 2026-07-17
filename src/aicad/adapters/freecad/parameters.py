from __future__ import annotations

from typing import Any

from aicad.core.expressions import validate_expression
from aicad.core.partdesign_registry import feature_by_type


_PARAMETER_GROUP = "Parameters"
_KIND_PROPERTIES = {
    "length": "App::PropertyLength",
    "angle": "App::PropertyAngle",
    "count": "App::PropertyInteger",
    "factor": "App::PropertyFloat",
}
_PARAMETER_NAME = r"[a-z][a-z0-9_]{0,63}"


class ParameterMixin:
    """Master parameters (App::VarSet) driving dimensions by expression."""

    @classmethod
    def _varset_or_error(cls, reference: str | None) -> Any:
        document = cls._active_document()
        varsets = [
            item for item in document.Objects if item.TypeId == "App::VarSet"
        ]
        if reference:
            varset = cls._resolve_document_object(reference)
            if varset.TypeId != "App::VarSet":
                raise ValueError(
                    "The referenced object is not a parameter set (App::VarSet)."
                )
            return varset
        if len(varsets) == 1:
            return varsets[0]
        if not varsets:
            raise ValueError(
                "No parameter set exists; create one with "
                "cad.create_parameter_set first."
            )
        names = ", ".join(item.Name for item in varsets)
        raise ValueError(f"Multiple parameter sets exist; specify one of: {names}.")

    @staticmethod
    def _validated_parameter_name(name: str) -> str:
        import re

        if re.fullmatch(_PARAMETER_NAME, str(name)) is None:
            raise ValueError(
                "Parameter names must be lowercase identifiers such as "
                "wall_thickness."
            )
        return str(name)

    @classmethod
    def _parameter_names(cls, varset: Any) -> list[str]:
        return [
            item
            for item in varset.PropertiesList
            if varset.getGroupOfProperty(item) == _PARAMETER_GROUP
        ]

    def create_parameter_set(self, name: str = "Params") -> dict[str, Any]:
        app, _ = self._modules()
        document = app.ActiveDocument or app.newDocument("AICadDocument")
        self._ensure_undo(document)
        checked_name = self._ensure_new_name(document, name)

        def create(document: Any) -> Any:
            return document.addObject("App::VarSet", checked_name)

        varset = self._run_transaction(
            f"create parameter set {checked_name}", create, allow_null_shape=True
        )
        return {"name": varset.Name, "label": varset.Label, "valid": True}

    def set_master_parameter(
        self,
        name: str,
        value: float,
        set: str | None = None,
        kind: str = "length",
    ) -> dict[str, Any]:
        varset = self._varset_or_error(set)
        checked_name = self._validated_parameter_name(name)
        checked_value = self._finite_float(value)
        if checked_value is None:
            raise ValueError("The parameter value must be a finite number.")
        checked_kind = str(kind).strip().lower()
        if checked_kind not in _KIND_PROPERTIES:
            allowed = ", ".join(sorted(_KIND_PROPERTIES))
            raise ValueError(f"Parameter kind must be one of: {allowed}.")
        if checked_kind == "count" and checked_value != int(checked_value):
            raise ValueError("A count parameter requires an integer value.")

        created = checked_name not in varset.PropertiesList

        def mutate(document: Any) -> Any:
            if created:
                varset.addProperty(
                    _KIND_PROPERTIES[checked_kind],
                    checked_name,
                    _PARAMETER_GROUP,
                )
            applied: Any = checked_value
            if checked_kind == "count":
                applied = int(checked_value)
            setattr(varset, checked_name, applied)
            return varset

        self._run_transaction(
            f"set parameter {checked_name}", mutate, allow_null_shape=True
        )
        return {
            "set": varset.Name,
            "name": checked_name,
            "value": checked_value,
            "kind": checked_kind,
            "created": created,
            "valid": True,
        }

    def list_master_parameters(self, set: str | None = None) -> dict[str, Any]:
        document = self._active_document()
        varsets = (
            [self._varset_or_error(set)]
            if set
            else [
                item
                for item in document.Objects
                if item.TypeId == "App::VarSet"
            ]
        )
        sets = []
        for varset in varsets:
            parameters = []
            for parameter in self._parameter_names(varset):
                raw = getattr(varset, parameter)
                parameters.append(
                    {
                        "name": parameter,
                        "value": float(raw),
                        "type": varset.getTypeIdOfProperty(parameter),
                    }
                )
            sets.append(
                {
                    "name": varset.Name,
                    "label": varset.Label,
                    "parameters": parameters,
                }
            )
        return {"count": len(sets), "sets": sets}

    def rename_sketch_constraint(
        self, sketch: str, constraint: int, name: str
    ) -> dict[str, Any]:
        target = self._sketch_or_error(sketch)
        index = self._constraint_index(target, constraint)
        checked_name = self._validated_parameter_name(name)
        existing = [item.Name for item in target.Constraints]
        if checked_name in existing:
            raise ValueError(
                f"The sketch already has a constraint named {checked_name}."
            )

        def mutate(document: Any) -> Any:
            target.renameConstraint(index, checked_name)
            return target

        self._run_transaction(
            f"rename constraint {index} on {target.Name}", mutate
        )
        return {
            "name": target.Name,
            "label": target.Label,
            "constraint_index": index,
            "constraint_name": checked_name,
            "valid": True,
        }

    def bind_sketch_datum(
        self,
        sketch: str,
        constraint: str,
        expression: str | None,
    ) -> dict[str, Any]:
        target = self._sketch_or_error(sketch)
        wanted = str(constraint).strip()
        named = [item.Name for item in target.Constraints]
        if wanted not in named:
            raise ValueError(
                f"The sketch has no constraint named {wanted}; name it first "
                "with cad.rename_sketch_constraint."
            )
        checked = (
            validate_expression(expression) if expression is not None else None
        )

        def mutate(document: Any) -> Any:
            target.setExpression(f"Constraints.{wanted}", checked)
            return target

        self._run_transaction(
            f"bind constraint {wanted} on {target.Name}", mutate
        )
        return {
            "name": target.Name,
            "label": target.Label,
            "constraint_name": wanted,
            "expression": checked,
            "value": float(target.getDatum(wanted)),
            "valid": True,
        }

    def bind_feature_parameter(
        self,
        feature: str,
        parameter: str,
        expression: str | None,
    ) -> dict[str, Any]:
        target = self._resolve_document_object(feature)
        definition = feature_by_type(target.TypeId)
        allowlist = definition.scalar_allowlist()
        if parameter not in allowlist:
            allowed = ", ".join(sorted(allowlist)) or "none"
            raise ValueError(
                f"{definition.freecad_type} does not accept {parameter}. "
                f"Bindable parameters: {allowed}."
            )
        freecad_property = allowlist[parameter].freecad_property
        checked = (
            validate_expression(expression) if expression is not None else None
        )

        def mutate(document: Any) -> Any:
            target.setExpression(freecad_property, checked)
            return target

        self._run_transaction(
            f"bind {freecad_property} on {target.Name}", mutate
        )
        return {
            "name": target.Name,
            "label": target.Label,
            "parameter": parameter,
            "freecad_property": freecad_property,
            "expression": checked,
            "value": float(getattr(target, freecad_property)),
            "valid": True,
        }

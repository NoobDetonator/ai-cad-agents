from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
import re
from collections.abc import Mapping
from typing import Any, Callable


class ToolRisk(StrEnum):
    READ = "read"
    MODIFY = "modify"
    EXPORT = "export"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    risk: ToolRisk
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    family: str = "general"
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    essential: bool = False
    canonical_order: int = 1000


class ToolInputError(ValueError):
    """Raised before a handler runs when tool arguments do not match its schema."""


class ToolConfirmationRequired(PermissionError):
    """Raised when a risky tool is called without an explicit confirmation."""


class ToolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}

    def register(
        self, spec: ToolSpec, handler: Callable[..., Any] | None = None
    ) -> None:
        if spec.name in self._specs:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._specs[spec.name] = spec
        if handler is not None:
            self._handlers[spec.name] = handler

    def list_specs(self) -> tuple[ToolSpec, ...]:
        return tuple(self._specs.values())

    def get_spec(self, name: str) -> ToolSpec:
        if name not in self._specs:
            raise KeyError(f"Unknown tool: {name}")
        return self._specs[name]

    def bind(self, name: str, handler: Callable[..., Any]) -> None:
        self.get_spec(name)
        if name in self._handlers:
            raise ValueError(f"Tool already has a connected handler: {name}")
        self._handlers[name] = handler

    def has_handler(self, name: str) -> bool:
        self.get_spec(name)
        return name in self._handlers

    def execute(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        confirmed: bool = False,
    ) -> Any:
        spec = self.get_spec(name)
        if name not in self._handlers:
            raise RuntimeError(f"Tool has no connected handler: {name}")
        if spec.risk is not ToolRisk.READ and not confirmed:
            raise ToolConfirmationRequired(
                f"Tool requires explicit confirmation: {name}"
            )
        checked_arguments = self.validate_arguments(name, arguments)
        return self._handlers[name](**checked_arguments)

    def validate_arguments(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate one call without executing or requiring a connected handler."""

        spec = self.get_spec(name)
        if arguments is None:
            checked_arguments: dict[str, Any] = {}
        elif isinstance(arguments, Mapping):
            checked_arguments = dict(arguments)
        else:
            raise ToolInputError(f"Arguments for {name} must be an object.")
        self._validate_arguments(spec, checked_arguments)
        return checked_arguments

    @staticmethod
    def _validate_arguments(spec: ToolSpec, arguments: dict[str, Any]) -> None:
        schema = spec.input_schema
        if schema.get("type") != "object":
            raise RuntimeError(f"Unsupported input schema for tool: {spec.name}")

        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        missing = sorted(required - arguments.keys())
        if missing:
            raise ToolInputError(
                f"Missing required arguments for {spec.name}: {', '.join(missing)}"
            )

        if schema.get("additionalProperties") is False:
            unexpected = sorted(arguments.keys() - properties.keys())
            if unexpected:
                raise ToolInputError(
                    f"Unexpected arguments for {spec.name}: {', '.join(unexpected)}"
                )

        for argument_name, value in arguments.items():
            property_schema = properties.get(argument_name)
            if property_schema is None:
                continue
            expected_type = property_schema.get("type")
            if expected_type == "number":
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ToolInputError(f"{argument_name} must be a number.")
                if not math.isfinite(float(value)):
                    raise ToolInputError(f"{argument_name} must be finite.")
                minimum = property_schema.get("exclusiveMinimum")
                if minimum is not None and value <= minimum:
                    raise ToolInputError(
                        f"{argument_name} must be greater than {minimum}."
                    )
                inclusive_minimum = property_schema.get("minimum")
                inclusive_maximum = property_schema.get("maximum")
                if inclusive_minimum is not None and value < inclusive_minimum:
                    raise ToolInputError(
                        f"{argument_name} must be at least {inclusive_minimum}."
                    )
                if inclusive_maximum is not None and value > inclusive_maximum:
                    raise ToolInputError(
                        f"{argument_name} must be at most {inclusive_maximum}."
                    )
            elif expected_type == "integer":
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ToolInputError(f"{argument_name} must be an integer.")
                minimum = property_schema.get("minimum")
                maximum = property_schema.get("maximum")
                if minimum is not None and value < minimum:
                    raise ToolInputError(
                        f"{argument_name} must be at least {minimum}."
                    )
                if maximum is not None and value > maximum:
                    raise ToolInputError(
                        f"{argument_name} must be at most {maximum}."
                    )
            elif expected_type == "string":
                if not isinstance(value, str):
                    raise ToolInputError(f"{argument_name} must be a string.")
                minimum_length = property_schema.get("minLength")
                maximum_length = property_schema.get("maxLength")
                pattern = property_schema.get("pattern")
                if minimum_length is not None and len(value) < minimum_length:
                    raise ToolInputError(f"{argument_name} is too short.")
                if maximum_length is not None and len(value) > maximum_length:
                    raise ToolInputError(f"{argument_name} is too long.")
                if pattern is not None and re.fullmatch(pattern, value) is None:
                    raise ToolInputError(f"{argument_name} has an invalid format.")
                allowed_values = property_schema.get("enum")
                if allowed_values is not None and value not in allowed_values:
                    raise ToolInputError(
                        f"{argument_name} must be one of the allowed values."
                    )
            elif expected_type == "boolean":
                if not isinstance(value, bool):
                    raise ToolInputError(f"{argument_name} must be a boolean.")
            elif expected_type == "array":
                if not isinstance(value, list):
                    raise ToolInputError(f"{argument_name} must be an array.")
                min_items = property_schema.get("minItems")
                max_items = property_schema.get("maxItems")
                if min_items is not None and len(value) < min_items:
                    raise ToolInputError(
                        f"{argument_name} requires at least {min_items} items."
                    )
                if max_items is not None and len(value) > max_items:
                    raise ToolInputError(
                        f"{argument_name} accepts at most {max_items} items."
                    )
                if property_schema.get("uniqueItems") and len(value) != len(
                    {repr(element) for element in value}
                ):
                    raise ToolInputError(f"{argument_name} items must be unique.")
                items_schema = property_schema.get("items", {})
                item_type = items_schema.get("type")
                if item_type not in {"string", "integer", "number", "boolean"}:
                    raise RuntimeError(
                        f"Unsupported array item type for {spec.name}."
                    )
                for element in value:
                    if item_type == "string" and not isinstance(element, str):
                        raise ToolInputError(
                            f"{argument_name} items must be strings."
                        )
                    if item_type == "integer" and (
                        not isinstance(element, int) or isinstance(element, bool)
                    ):
                        raise ToolInputError(
                            f"{argument_name} items must be integers."
                        )
                    if item_type == "number" and (
                        not isinstance(element, (int, float))
                        or isinstance(element, bool)
                    ):
                        raise ToolInputError(
                            f"{argument_name} items must be numbers."
                        )
                    if item_type == "number" and not math.isfinite(float(element)):
                        raise ToolInputError(
                            f"{argument_name} items must be finite."
                        )
                    if item_type == "boolean" and not isinstance(element, bool):
                        raise ToolInputError(
                            f"{argument_name} items must be booleans."
                        )
                    minimum_length = items_schema.get("minLength")
                    maximum_length = items_schema.get("maxLength")
                    if (
                        item_type == "string"
                        and minimum_length is not None
                        and len(element) < minimum_length
                    ):
                        raise ToolInputError(f"{argument_name} has an empty item.")
                    if (
                        item_type == "string"
                        and maximum_length is not None
                        and len(element) > maximum_length
                    ):
                        raise ToolInputError(
                            f"{argument_name} has an item that is too long."
                        )
                    pattern = items_schema.get("pattern")
                    if (
                        item_type == "string"
                        and pattern is not None
                        and re.fullmatch(pattern, element) is None
                    ):
                        raise ToolInputError(
                            f"{argument_name} has an item with an invalid format."
                        )
                    allowed_values = items_schema.get("enum")
                    if allowed_values is not None and element not in allowed_values:
                        raise ToolInputError(
                            f"{argument_name} has an item outside the allowed values."
                        )
                    minimum = items_schema.get("minimum")
                    maximum = items_schema.get("maximum")
                    if minimum is not None and element < minimum:
                        raise ToolInputError(
                            f"{argument_name} has an item below the minimum."
                        )
                    if maximum is not None and element > maximum:
                        raise ToolInputError(
                            f"{argument_name} has an item above the maximum."
                        )
            else:
                raise RuntimeError(
                    f"Unsupported argument type for {spec.name}: {expected_type}"
                )

def build_default_registry() -> ToolRegistry:
    """Build the provider-neutral catalog without importing a CAD backend."""

    from aicad.core.tool_catalog import default_tool_specs

    registry = ToolRegistry()
    for spec in default_tool_specs():
        registry.register(spec)
    return registry

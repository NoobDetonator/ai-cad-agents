from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json

from pydantic import JsonValue, ValidationError

from aicad.core.tool_selector import ToolSelector
from aicad.core.tool_registry import ToolInputError, ToolRegistry, ToolRisk
from aicad.orchestration.models import (
    OrchestrationPlan,
    PlannedToolCall,
    ProviderRequest,
    ProviderResponse,
    ProviderToolDefinition,
    tool_definition_from_spec,
)
from aicad.orchestration.provider import AiProvider


DEFAULT_PROVIDER_INSTRUCTIONS = (
    "You are the planning component of a CAD workbench. Return a structured "
    "intention, explicit assumptions, an ordered plan, and only calls to the "
    "tools supplied in this request. Never return Python or executable code. "
    "Do not invent tools or arguments. A proposed tool call is not permission "
    "to execute it; risky CAD operations require separate user confirmation."
)


class OrchestrationError(RuntimeError):
    """Base error for safe orchestration failures."""


class OrchestrationInputError(OrchestrationError):
    """The local request exceeds a limit or contains invalid input."""


class ProviderUnavailableError(OrchestrationError):
    """The provider failed without leaking its raw error or credentials."""


class InvalidProviderResponseError(OrchestrationError):
    """The provider response violates the structured planning contract."""


class OrchestrationLimitError(OrchestrationError):
    """The provider attempted to exceed a configured orchestration limit."""


@dataclass(frozen=True, slots=True)
class OrchestrationLimits:
    max_tool_calls: int = 8
    max_user_message_chars: int = 4000
    max_context_bytes: int = 64 * 1024
    max_allowed_tools: int = 64

    def __post_init__(self) -> None:
        values = (
            self.max_tool_calls,
            self.max_user_message_chars,
            self.max_context_bytes,
            self.max_allowed_tools,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValueError("Orchestration limits must be integers.")
        if any(value < 1 for value in values):
            raise ValueError("Orchestration limits must be positive.")


class AiOrchestrator:
    """Create a bounded, validated CAD plan without executing provider output."""

    def __init__(
        self,
        registry: ToolRegistry,
        provider: AiProvider,
        *,
        limits: OrchestrationLimits | None = None,
        tool_selector: ToolSelector | None = None,
    ) -> None:
        self._registry = registry
        self._provider = provider
        self._limits = limits or OrchestrationLimits()
        self._tool_selector = tool_selector or ToolSelector(registry)

    def create_plan(
        self,
        user_message: str,
        *,
        context: Mapping[str, JsonValue] | None = None,
        allowed_tool_names: Sequence[str] | None = None,
    ) -> OrchestrationPlan:
        cleaned_message = self._validate_user_message(user_message)
        checked_context = self._validate_context(context)
        definitions = self._select_tool_definitions(
            cleaned_message,
            checked_context,
            allowed_tool_names,
        )
        request = ProviderRequest(
            instructions=DEFAULT_PROVIDER_INSTRUCTIONS,
            user_message=cleaned_message,
            context=checked_context,
            tools=definitions,
            max_tool_calls=self._limits.max_tool_calls if definitions else 0,
        )

        try:
            raw_response = self._provider.create_response(request)
        except Exception as exc:
            raise ProviderUnavailableError(
                "The AI provider is unavailable or did not respond."
            ) from exc

        try:
            response = ProviderResponse.model_validate(raw_response)
        except ValidationError as exc:
            raise InvalidProviderResponseError(
                "The AI provider returned an invalid structured response."
            ) from exc

        if len(response.tool_calls) > request.max_tool_calls:
            raise OrchestrationLimitError(
                "The AI provider proposed more tool calls than allowed."
            )

        allowed_names = {definition.name for definition in definitions}
        seen_call_ids: set[str] = set()
        planned_calls: list[PlannedToolCall] = []
        for call in response.tool_calls:
            if call.call_id in seen_call_ids:
                raise InvalidProviderResponseError(
                    "The AI provider returned a duplicate tool call ID."
                )
            seen_call_ids.add(call.call_id)
            if call.name not in allowed_names:
                raise InvalidProviderResponseError(
                    "The AI provider proposed a tool that was not allowed."
                )
            try:
                arguments = self._registry.validate_arguments(
                    call.name,
                    call.arguments,
                )
                spec = self._registry.get_spec(call.name)
            except (KeyError, ToolInputError, RuntimeError) as exc:
                raise InvalidProviderResponseError(
                    "The AI provider proposed an invalid tool call."
                ) from exc
            planned_calls.append(
                PlannedToolCall(
                    call_id=call.call_id,
                    name=call.name,
                    arguments=arguments,
                    risk=spec.risk,
                    requires_confirmation=spec.risk is not ToolRisk.READ,
                )
            )

        return OrchestrationPlan(
            intention=response.intention,
            assumptions=response.assumptions,
            steps=response.plan,
            message=response.message,
            tool_calls=tuple(planned_calls),
        )

    def _validate_user_message(self, user_message: str) -> str:
        if not isinstance(user_message, str):
            raise OrchestrationInputError("The user message must be text.")
        cleaned = user_message.strip()
        if not cleaned:
            raise OrchestrationInputError("The user message cannot be empty.")
        if len(cleaned) > self._limits.max_user_message_chars:
            raise OrchestrationInputError("The user message is too long.")
        return cleaned

    def _validate_context(
        self,
        context: Mapping[str, JsonValue] | None,
    ) -> dict[str, JsonValue]:
        if context is None:
            checked: dict[str, JsonValue] = {}
        elif isinstance(context, Mapping):
            checked = dict(context)
        else:
            raise OrchestrationInputError("The orchestration context must be an object.")
        try:
            encoded = json.dumps(
                checked,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise OrchestrationInputError(
                "The orchestration context must contain only JSON values."
            ) from exc
        if len(encoded) > self._limits.max_context_bytes:
            raise OrchestrationInputError("The orchestration context is too large.")
        return json.loads(encoded)

    def _select_tool_definitions(
        self,
        user_message: str,
        context: Mapping[str, JsonValue],
        allowed_tool_names: Sequence[str] | None,
    ) -> tuple[ProviderToolDefinition, ...]:
        specs_by_name = {spec.name: spec for spec in self._registry.list_specs()}
        if allowed_tool_names is None:
            names = self._tool_selector.select(
                user_message,
                context=context,
            ).tool_names
        else:
            if isinstance(allowed_tool_names, (str, bytes)):
                raise OrchestrationInputError("Allowed tool names must be a sequence.")
            requested_names = tuple(allowed_tool_names)
            if any(not isinstance(name, str) for name in requested_names):
                raise OrchestrationInputError(
                    "Every allowed tool name must be text."
                )
            names = tuple(dict.fromkeys(requested_names))
            unknown = [name for name in names if name not in specs_by_name]
            if unknown:
                raise OrchestrationInputError(
                    "The allowed tool list contains an unknown tool."
                )
        if len(names) > self._limits.max_allowed_tools:
            raise OrchestrationLimitError("Too many tools were exposed to the provider.")
        return tuple(tool_definition_from_spec(specs_by_name[name]) for name in names)

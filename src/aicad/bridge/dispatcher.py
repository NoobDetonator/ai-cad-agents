from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import json
import math
from threading import Event, Lock, get_ident
import time
from typing import Any
from uuid import UUID

from aicad.audit.models import AuditSource
from aicad.audit.redaction import redact_text
from aicad.audit.service import AuditService
from aicad.bridge.protocol import (
    BridgeError,
    BridgeErrorCode,
    BridgeRequest,
    BridgeResponse,
    BridgeResponseStatus,
    BridgeTiming,
    validate_request_payload,
)
from aicad.core.tool_registry import ToolRegistry, ToolRisk
from aicad.core.transactions import (
    CadTransactionOutcome,
    last_transaction_trace,
)
from aicad.core.tool_results import (
    ToolErrorCategory,
    ToolRecoveryAction,
    ToolRecoveryActionType,
)


DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_TRACKED_REQUESTS = 512

# Exception types the adapter raises on purpose, with a message written for
# the caller. Everything else is an implementation detail.
_DOMAIN_ERRORS = (ValueError, RuntimeError, KeyError)

# How long the GUI-hosted dispatcher works a request before expiring it. Any
# client of that bridge must be willing to wait at least this long, so this
# lives here rather than in the UI package that happens to configure it.
GUI_REQUEST_TIMEOUT_SECONDS = 120.0


@dataclass(slots=True)
class _DispatchEntry:
    request: BridgeRequest
    fingerprint: str
    risk: ToolRisk
    deadline: float
    submitted_at: float
    response: BridgeResponse | None = None
    event: Event = field(default_factory=Event)
    executing: bool = False
    audit_action_id: UUID | None = None
    confirmation_started_at: float | None = None
    execution_started_at: float | None = None


@dataclass(frozen=True, slots=True)
class _FailureDiagnostic:
    message: str
    category: ToolErrorCategory
    retryable: bool
    suggested_actions: tuple[ToolRecoveryAction, ...]


class BridgeDispatcher:
    """Queue bridge requests for execution by one owning GUI thread."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        audit_service: AuditService | None = None,
        on_confirmation_requested: Callable[[BridgeRequest], None] | None = None,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
        max_tracked_requests: int = DEFAULT_MAX_TRACKED_REQUESTS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if (
            isinstance(request_timeout, bool)
            or not isinstance(request_timeout, (int, float))
            or not math.isfinite(float(request_timeout))
            or request_timeout <= 0
        ):
            raise ValueError("The dispatcher timeout must be positive and finite.")
        if (
            isinstance(max_tracked_requests, bool)
            or not isinstance(max_tracked_requests, int)
            or max_tracked_requests < 1
        ):
            raise ValueError("The dispatcher request limit must be a positive integer.")

        self._registry = registry
        self._audit_service = audit_service
        self._on_confirmation_requested = on_confirmation_requested or (lambda _: None)
        self._request_timeout = float(request_timeout)
        self._max_tracked_requests = max_tracked_requests
        self._clock = clock
        self._owner_thread_id = get_ident()
        self._lock = Lock()
        self._queue: deque[UUID] = deque()
        self._entries: dict[UUID, _DispatchEntry] = {}
        self._active_confirmation: UUID | None = None
        self._closed = False

    @property
    def queued_count(self) -> int:
        with self._lock:
            return sum(
                1
                for request_id in self._queue
                if request_id in self._entries
                and not self._is_terminal(self._entries[request_id].response)
            )

    @property
    def active_confirmation(self) -> BridgeRequest | None:
        with self._lock:
            if self._active_confirmation is None:
                return None
            entry = self._entries.get(self._active_confirmation)
            return entry.request if entry is not None else None

    def submit(self, payload: Mapping[str, Any]) -> BridgeResponse:
        """Validate and enqueue a transport request from any worker thread."""

        request = validate_request_payload(payload, self._registry)
        fingerprint = self._fingerprint(request)
        now = self._clock()

        with self._lock:
            self._expire_locked(now)
            existing = self._entries.get(request.request_id)
            if existing is not None:
                if existing.fingerprint != fingerprint:
                    return self._error_response(
                        request.request_id,
                        BridgeResponseStatus.REJECTED,
                        BridgeErrorCode.INVALID_REQUEST,
                        "The request ID is already associated with different content.",
                    )
                if existing.response is not None:
                    return existing.response
                wait_event = existing.event
                deadline = existing.deadline
            else:
                if self._closed:
                    return self._error_response(
                        request.request_id,
                        BridgeResponseStatus.FAILED,
                        BridgeErrorCode.GUI_UNAVAILABLE,
                        "The GUI bridge dispatcher is closed.",
                    )
                if not self._make_room_locked():
                    return self._error_response(
                        request.request_id,
                        BridgeResponseStatus.REJECTED,
                        BridgeErrorCode.QUEUE_FULL,
                        "The GUI bridge request queue is full.",
                    )

                risk = self._registry.get_spec(request.tool_name).risk
                response = None
                if risk is not ToolRisk.READ:
                    response = BridgeResponse(
                        request_id=request.request_id,
                        status=BridgeResponseStatus.PENDING_CONFIRMATION,
                    )
                entry = _DispatchEntry(
                    request=request,
                    fingerprint=fingerprint,
                    risk=risk,
                    deadline=now + self._request_timeout,
                    submitted_at=now,
                    response=response,
                    audit_action_id=(
                        self._audit_service.begin_tool(
                            self._registry,
                            request.tool_name,
                            request.arguments,
                            source=AuditSource.MCP,
                            original_request=(
                                f"MCP request: {request.tool_name}"
                            ),
                            intention=f"Executar requisição MCP {request.tool_name}.",
                            call_id=f"mcp-{request.request_id}",
                            action_id=request.request_id,
                        )
                        if self._audit_service is not None
                        else None
                    ),
                )
                self._entries[request.request_id] = entry
                self._queue.append(request.request_id)
                if response is not None:
                    return response
                wait_event = entry.event
                deadline = entry.deadline

        remaining = max(0.0, deadline - self._clock())
        wait_event.wait(remaining)
        with self._lock:
            entry = self._entries.get(request.request_id)
            if entry is None:
                return self._error_response(
                    request.request_id,
                    BridgeResponseStatus.FAILED,
                    BridgeErrorCode.GUI_UNAVAILABLE,
                    "The GUI bridge request state is unavailable.",
                )
            if entry.response is None:
                self._expire_entry_locked(entry)
            return entry.response or self._error_response(
                request.request_id,
                BridgeResponseStatus.FAILED,
                BridgeErrorCode.EXECUTION_ERROR,
                "The GUI bridge request did not produce a response.",
            )

    def process_next(self) -> bool:
        """Process one queued item; must be called periodically by the GUI thread."""

        self._ensure_owner_thread()
        request_to_execute: BridgeRequest | None = None
        audit_action_id: UUID | None = None
        confirmation_to_show: BridgeRequest | None = None

        with self._lock:
            self._expire_locked(self._clock())
            if self._active_confirmation is not None:
                return False
            while self._queue:
                request_id = self._queue.popleft()
                entry = self._entries.get(request_id)
                if entry is None or self._is_terminal(entry.response):
                    continue
                if entry.risk is ToolRisk.READ:
                    entry.executing = True
                    entry.execution_started_at = self._clock()
                    request_to_execute = entry.request
                    audit_action_id = entry.audit_action_id
                    break
                self._active_confirmation = request_id
                entry.confirmation_started_at = self._clock()
                confirmation_to_show = entry.request
                break

        if confirmation_to_show is not None:
            try:
                self._on_confirmation_requested(confirmation_to_show)
            except Exception:
                if self._audit_service is not None:
                    entry = self._entries.get(confirmation_to_show.request_id)
                    if entry is not None and entry.audit_action_id is not None:
                        self._audit_service.cancel(
                            entry.audit_action_id,
                            source="system",
                            error_code="confirmation_unavailable",
                        )
                self._finish_with_error(
                    confirmation_to_show.request_id,
                    BridgeResponseStatus.FAILED,
                    BridgeErrorCode.EXECUTION_ERROR,
                    "The confirmation request could not be presented.",
                )
            return True

        if request_to_execute is None:
            return False
        try:
            if self._audit_service is not None and audit_action_id is not None:
                result = self._audit_service.execute_tool(
                    audit_action_id,
                    self._registry,
                )
            else:
                result = self._registry.execute(
                    request_to_execute.tool_name,
                    request_to_execute.arguments,
                )
            response = BridgeResponse(
                request_id=request_to_execute.request_id,
                status=BridgeResponseStatus.COMPLETED,
                result=result,
            )
        except Exception as exc:
            diagnostic = self._failure_diagnostic(
                "The CAD read operation failed.",
                exc,
            )
            response = self._error_response(
                request_to_execute.request_id,
                BridgeResponseStatus.FAILED,
                BridgeErrorCode.EXECUTION_ERROR,
                diagnostic.message,
                category=diagnostic.category,
                retryable=diagnostic.retryable,
                safe_state_restored=True,
                suggested_actions=diagnostic.suggested_actions,
            )
        self._finish(request_to_execute.request_id, response)
        return True

    def resolve_confirmation(
        self,
        request_id: UUID,
        *,
        approved: bool,
        automatic: bool = False,
    ) -> BridgeResponse:
        """Resolve and optionally execute the active mutation on the GUI thread."""

        self._ensure_owner_thread()
        with self._lock:
            self._expire_locked(self._clock())
            entry = self._entries.get(request_id)
            if entry is None:
                return self._error_response(
                    request_id,
                    BridgeResponseStatus.REJECTED,
                    BridgeErrorCode.INVALID_REQUEST,
                    "No matching bridge request is pending.",
                )
            if self._active_confirmation != request_id:
                return entry.response or self._error_response(
                    request_id,
                    BridgeResponseStatus.REJECTED,
                    BridgeErrorCode.INVALID_REQUEST,
                    "The bridge request is not awaiting confirmation.",
                )
            if self._is_terminal(entry.response):
                self._active_confirmation = None
                return entry.response
            if not approved:
                if self._audit_service is not None and entry.audit_action_id is not None:
                    self._audit_service.cancel(
                        entry.audit_action_id,
                        source="ui",
                        denied=True,
                    )
                response = self._error_response(
                    request_id,
                    BridgeResponseStatus.CANCELLED,
                    BridgeErrorCode.CONFIRMATION_DENIED,
                    "The CAD operation was cancelled by the user.",
                )
                response = response.model_copy(
                    update={"timing": self._timing(entry, self._clock())}
                )
                entry.response = response
                entry.event.set()
                self._active_confirmation = None
                return response
            entry.executing = True
            entry.execution_started_at = self._clock()
            request = entry.request
            audit_action_id = entry.audit_action_id

        try:
            if self._audit_service is not None and audit_action_id is not None:
                self._audit_service.approve(
                    audit_action_id,
                    automatic=automatic,
                    source="quick_test" if automatic else "ui",
                )
                result = self._audit_service.execute_tool(
                    audit_action_id,
                    self._registry,
                )
            else:
                result = self._registry.execute(
                    request.tool_name,
                    request.arguments,
                    confirmed=True,
                )
            response = BridgeResponse(
                request_id=request_id,
                status=BridgeResponseStatus.COMPLETED,
                result=result,
            )
        except Exception as exc:
            diagnostic = self._failure_diagnostic(
                "The confirmed CAD operation failed.",
                exc,
            )
            response = self._error_response(
                request_id,
                BridgeResponseStatus.FAILED,
                BridgeErrorCode.EXECUTION_ERROR,
                diagnostic.message,
                category=diagnostic.category,
                retryable=diagnostic.retryable,
                safe_state_restored=self._safe_state_after_failure(
                    entry.risk, expected_action_id=audit_action_id
                ),
                suggested_actions=diagnostic.suggested_actions,
            )
        response = response.model_copy(
            update={"timing": self._timing(entry, self._clock())}
        )
        self._finish(request_id, response)
        return response

    def expire_requests(self) -> int:
        self._ensure_owner_thread()
        with self._lock:
            return self._expire_locked(self._clock())

    def close(self) -> None:
        self._ensure_owner_thread()
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._queue.clear()
            self._active_confirmation = None
            for entry in self._entries.values():
                if self._is_terminal(entry.response):
                    continue
                entry.response = self._error_response(
                    entry.request.request_id,
                    BridgeResponseStatus.CANCELLED,
                    BridgeErrorCode.GUI_UNAVAILABLE,
                    "The GUI bridge dispatcher was closed.",
                )
                entry.executing = False
                entry.event.set()
                self._cancel_audit(
                    entry,
                    source="system",
                    error_code="gui_unavailable",
                )

    def _finish(self, request_id: UUID, response: BridgeResponse) -> None:
        with self._lock:
            entry = self._entries.get(request_id)
            if entry is None or self._is_terminal(entry.response):
                return
            if response.timing is None:
                response = response.model_copy(
                    update={"timing": self._timing(entry, self._clock())}
                )
            entry.response = response
            entry.executing = False
            entry.event.set()
            if self._active_confirmation == request_id:
                self._active_confirmation = None

    def _finish_with_error(
        self,
        request_id: UUID,
        status: BridgeResponseStatus,
        code: BridgeErrorCode,
        message: str,
    ) -> None:
        self._finish(
            request_id,
            self._error_response(request_id, status, code, message),
        )

    def _expire_locked(self, now: float) -> int:
        expired = 0
        for entry in self._entries.values():
            if (
                not entry.executing
                and entry.deadline <= now
                and not self._is_terminal(entry.response)
            ):
                self._expire_entry_locked(entry)
                expired += 1
        return expired

    def _expire_entry_locked(self, entry: _DispatchEntry) -> None:
        response = self._error_response(
            entry.request.request_id,
            BridgeResponseStatus.EXPIRED,
            BridgeErrorCode.TIMEOUT,
            "The bridge request expired before completion.",
        )
        entry.response = response.model_copy(
            update={"timing": self._timing(entry, self._clock())}
        )
        entry.executing = False
        entry.event.set()
        self._cancel_audit(
            entry,
            source="system",
            error_code="timeout",
        )
        if self._active_confirmation == entry.request.request_id:
            self._active_confirmation = None

    def _make_room_locked(self) -> bool:
        if len(self._entries) < self._max_tracked_requests:
            return True
        for request_id, entry in tuple(self._entries.items()):
            if self._is_terminal(entry.response):
                del self._entries[request_id]
                return True
        return False

    def _ensure_owner_thread(self) -> None:
        if get_ident() != self._owner_thread_id:
            raise RuntimeError("The bridge dispatcher must run on its owner thread.")

    def _cancel_audit(
        self,
        entry: _DispatchEntry,
        *,
        source: str,
        error_code: str,
    ) -> None:
        if self._audit_service is not None and entry.audit_action_id is not None:
            self._audit_service.cancel(
                entry.audit_action_id,
                source=source,
                error_code=error_code,
            )

    @staticmethod
    def _fingerprint(request: BridgeRequest) -> str:
        return json.dumps(
            request.model_dump(mode="json"),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _is_terminal(response: BridgeResponse | None) -> bool:
        return (
            response is not None
            and response.status is not BridgeResponseStatus.PENDING_CONFIRMATION
        )

    @staticmethod
    def _timing(entry: _DispatchEntry, finished_at: float) -> BridgeTiming:
        queue_finished_at = (
            entry.confirmation_started_at
            if entry.confirmation_started_at is not None
            else entry.execution_started_at
            if entry.execution_started_at is not None
            else finished_at
        )
        confirmation_finished_at = (
            entry.execution_started_at
            if entry.execution_started_at is not None
            else finished_at
        )
        confirmation_wait = (
            confirmation_finished_at - entry.confirmation_started_at
            if entry.confirmation_started_at is not None
            else 0.0
        )
        execution = (
            finished_at - entry.execution_started_at
            if entry.execution_started_at is not None
            else 0.0
        )
        return BridgeTiming(
            queue_wait_ms=max(0.0, queue_finished_at - entry.submitted_at) * 1000,
            confirmation_wait_ms=max(0.0, confirmation_wait) * 1000,
            execution_ms=max(0.0, execution) * 1000,
            gui_total_ms=max(0.0, finished_at - entry.submitted_at) * 1000,
        )

    @staticmethod
    def _error_response(
        request_id: UUID,
        status: BridgeResponseStatus,
        code: BridgeErrorCode,
        message: str,
        *,
        category: ToolErrorCategory | None = None,
        retryable: bool | None = None,
        safe_state_restored: bool | None = None,
        suggested_actions: tuple[ToolRecoveryAction, ...] | None = None,
    ) -> BridgeResponse:
        overrides: dict[str, Any] = {}
        if category is not None:
            overrides["category"] = category
        if retryable is not None:
            overrides["retryable"] = retryable
        if safe_state_restored is not None:
            overrides["safe_state_restored"] = safe_state_restored
        if suggested_actions is not None:
            overrides["suggested_actions"] = suggested_actions
        return BridgeResponse(
            request_id=request_id,
            status=status,
            error=BridgeError(code=code, message=message, **overrides),
        )

    @staticmethod
    def _safe_state_after_failure(
        risk: ToolRisk,
        expected_action_id: UUID | None = None,
    ) -> bool | None:
        if risk is ToolRisk.READ:
            return True
        if expected_action_id is None:
            return None
        trace = last_transaction_trace()
        if (
            trace is None
            or trace.action_id != expected_action_id
            or trace.outcome is CadTransactionOutcome.UNKNOWN
        ):
            return None
        if trace.outcome in {
            CadTransactionOutcome.ABORTED,
            CadTransactionOutcome.UNDONE,
        }:
            return True

        return False

    @classmethod
    def _failure_diagnostic(
        cls,
        prefix: str,
        error: Exception,
    ) -> _FailureDiagnostic:
        message = cls._failure_message(prefix, error)
        if isinstance(error, KeyError):
            return _FailureDiagnostic(
                message=message,
                category=ToolErrorCategory.MISSING_OBJECT,
                retryable=True,
                suggested_actions=(
                    ToolRecoveryAction(
                        action=ToolRecoveryActionType.REFRESH_CONTEXT,
                        description=(
                            "Refresh the document context, resolve the current object "
                            "name, then submit a new request ID."
                        ),
                    ),
                ),
            )
        if isinstance(error, ValueError):
            return _FailureDiagnostic(
                message=message,
                category=ToolErrorCategory.INVALID_ARGUMENT,
                retryable=True,
                suggested_actions=(
                    ToolRecoveryAction(
                        action=ToolRecoveryActionType.CHANGE_ARGUMENT,
                        description=(
                            "Correct the geometric or numeric arguments, then submit "
                            "a new request ID."
                        ),
                    ),
                ),
            )
        if isinstance(error, RuntimeError):
            return _FailureDiagnostic(
                message=message,
                category=ToolErrorCategory.GEOMETRY,
                retryable=True,
                suggested_actions=(
                    ToolRecoveryAction(
                        action=ToolRecoveryActionType.INSPECT_GEOMETRY,
                        description=(
                            "Inspect the current geometry and validation state before "
                            "submitting a corrected request."
                        ),
                    ),
                ),
            )
        return _FailureDiagnostic(
            message=message,
            category=ToolErrorCategory.INTERNAL,
            retryable=False,
            suggested_actions=(
                ToolRecoveryAction(
                    action=ToolRecoveryActionType.STOP_AND_REPORT,
                    description=(
                        "Stop automatic recovery and report the failure without "
                        "exposing implementation details."
                    ),
                ),
            ),
        )

    @staticmethod
    def _failure_message(prefix: str, error: Exception) -> str:
        """Append the adapter's own reason so MCP clients can self-correct.

        Only the types the adapter raises deliberately carry domain messages
        ("The corner radius does not fit the adjacent path segments.",
        "Unknown CAD object: Sun2"); anything else is an implementation
        detail and stays suppressed. Without the reason a caller cannot tell
        a bad argument from a GUI failure, and the GUI already shows it to
        the human via the TALOS panel.
        """

        if not isinstance(error, _DOMAIN_ERRORS):
            return prefix
        # KeyError's str() wraps its message in quotes; args[0] is the message.
        raw = error.args[0] if isinstance(error, KeyError) and error.args else error
        reason, _ = redact_text(str(raw).strip(), max_chars=400)
        if not reason:
            return prefix
        return f"{prefix} {reason}"

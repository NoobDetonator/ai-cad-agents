from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping
import json
from threading import Lock, get_ident
from typing import Any
from uuid import UUID

from aicad.bridge.protocol import (
    BridgeError,
    BridgeErrorCode,
    BridgePlanCancelRequest,
    BridgePlanRequest,
    BridgePlanStatusRequest,
    BridgePlanSubmitRequest,
    BridgeResponse,
    BridgeResponseStatus,
    validate_plan_request_payload,
)
from aicad.core.tool_registry import ToolRegistry
from aicad.orchestration.plan_service import (
    CompositeApprovalGrant,
    CompositePlanExecutor,
    CompositePlanStatus,
    CompositeValidatedPlan,
    PlanService,
    PlanStatusSnapshot,
)


DEFAULT_MAX_TRACKED_PLAN_REQUESTS = 512


class PlanBridgeDispatcher:
    """Project the GUI-owned PlanService through the authenticated bridge."""

    def __init__(
        self,
        registry: ToolRegistry,
        plan_service: PlanService,
        *,
        on_confirmation_requested: Callable[[CompositeValidatedPlan], None],
        context_reader: Callable[[], Mapping[str, Any]],
        max_tracked_requests: int = DEFAULT_MAX_TRACKED_PLAN_REQUESTS,
    ) -> None:
        if max_tracked_requests < 1:
            raise ValueError("The plan request limit must be positive.")
        self._registry = registry
        self._plan_service = plan_service
        self._on_confirmation_requested = on_confirmation_requested
        self._context_reader = context_reader
        self._max_tracked_requests = max_tracked_requests
        self._owner_thread_id = get_ident()
        self._lock = Lock()
        self._plans: dict[UUID, CompositeValidatedPlan] = {}
        self._queue: deque[UUID] = deque()
        self._queued: set[UUID] = set()
        self._active_confirmation: UUID | None = None
        self._responses: dict[UUID, tuple[str, BridgeResponse]] = {}
        self._closed = False

    @property
    def plan_service(self) -> PlanService:
        return self._plan_service

    def submit(self, payload: Mapping[str, Any]) -> BridgeResponse:
        request = validate_plan_request_payload(payload, self._registry)
        fingerprint = self._fingerprint(request)
        with self._lock:
            existing = self._responses.get(request.request_id)
            if existing is not None:
                if existing[0] != fingerprint:
                    return self._error(
                        request.request_id,
                        BridgeErrorCode.INVALID_REQUEST,
                        "The request ID is already associated with different content.",
                    )
                if isinstance(request, BridgePlanStatusRequest):
                    try:
                        snapshot = self._plan_service.get_status(request.plan_id)
                        refreshed = BridgeResponse(
                            request_id=request.request_id,
                            status=BridgeResponseStatus.COMPLETED,
                            result=snapshot.model_dump(mode="json"),
                        )
                    except KeyError as exc:
                        refreshed = self._error(
                            request.request_id,
                            BridgeErrorCode.INVALID_REQUEST,
                            str(exc),
                        )
                    self._responses[request.request_id] = (fingerprint, refreshed)
                    return refreshed
                return existing[1]
            if self._closed:
                return self._remember(
                    request,
                    self._error(
                        request.request_id,
                        BridgeErrorCode.GUI_UNAVAILABLE,
                        "The GUI plan dispatcher is closed.",
                        status=BridgeResponseStatus.FAILED,
                    ),
                )

            try:
                snapshot = self._handle_locked(request)
                response = BridgeResponse(
                    request_id=request.request_id,
                    status=BridgeResponseStatus.COMPLETED,
                    result=snapshot.model_dump(mode="json"),
                )
            except (KeyError, ValueError) as exc:
                response = self._error(
                    request.request_id,
                    BridgeErrorCode.INVALID_REQUEST,
                    str(exc),
                )
            return self._remember(request, response)

    def process_next(self) -> bool:
        """Present one queued plan confirmation from the owning GUI thread."""

        self._ensure_owner_thread()
        with self._lock:
            if self._active_confirmation is not None:
                return False
            while self._queue:
                plan_id = self._queue.popleft()
                self._queued.discard(plan_id)
                plan = self._plans.get(plan_id)
                if plan is None:
                    continue
                status = self._plan_service.get_status(plan_id)
                if status.status is not CompositePlanStatus.AWAITING_APPROVAL:
                    continue
                self._active_confirmation = plan_id
                break
            else:
                return False
        try:
            self._on_confirmation_requested(plan)
        except Exception:
            self._plan_service.cancel(
                plan.plan_id,
                audit_source="system",
                error_code="confirmation_unavailable",
            )
            with self._lock:
                self._active_confirmation = None
        return True

    def is_remote_plan(self, plan_id: UUID) -> bool:
        with self._lock:
            return plan_id in self._plans

    def resolve_confirmation(
        self,
        plan_id: UUID,
        *,
        approved: bool,
        on_progress: Callable[[PlanStatusSnapshot], None] | None = None,
        automatic: bool = False,
    ) -> PlanStatusSnapshot:
        """Approve or deny one remote plan and execute it on the GUI thread."""

        self._ensure_owner_thread()
        with self._lock:
            plan = self._plans.get(plan_id)
            active = self._active_confirmation
        if plan is None:
            raise KeyError("Unknown remote composite plan.")
        current = self._plan_service.get_status(plan_id)
        if current.status is not CompositePlanStatus.AWAITING_APPROVAL:
            with self._lock:
                if active == plan_id:
                    self._active_confirmation = None
            return current
        if active != plan_id:
            raise ValueError("The remote plan is not awaiting visual confirmation.")
        if not approved:
            snapshot = self._plan_service.cancel(
                plan_id,
                audit_source="ui",
                denied=True,
            )
            with self._lock:
                self._active_confirmation = None
            return snapshot

        try:
            self._plan_service.execute(
                plan_id,
                CompositeApprovalGrant.issue(plan, source="mcp"),
                CompositePlanExecutor(self._registry, self._context_reader),
                on_progress=on_progress,
                approval_automatic=automatic,
                approval_source="quick_test" if automatic else "ui",
            )
        except Exception:
            pass
        finally:
            with self._lock:
                self._active_confirmation = None
        return self._plan_service.get_status(plan_id)

    def close(self) -> None:
        self._ensure_owner_thread()
        with self._lock:
            self._closed = True
            pending_ids = tuple(self._queued)
            if self._active_confirmation is not None:
                pending_ids += (self._active_confirmation,)
            self._queue.clear()
            self._queued.clear()
            self._active_confirmation = None
        for plan_id in pending_ids:
            self._plan_service.cancel(plan_id, audit_source="system")

    def _handle_locked(self, request: BridgePlanRequest) -> PlanStatusSnapshot:
        if isinstance(request, BridgePlanSubmitRequest):
            plan = request.plan
            snapshot = self._plan_service.submit(
                plan,
                audit_source="mcp",
                original_request="MCP composite plan submission.",
            )
            self._plans.setdefault(plan.plan_id, plan)
            if (
                snapshot.status is CompositePlanStatus.AWAITING_APPROVAL
                and plan.plan_id not in self._queued
                and self._active_confirmation != plan.plan_id
            ):
                self._queue.append(plan.plan_id)
                self._queued.add(plan.plan_id)
            return snapshot
        if isinstance(request, BridgePlanStatusRequest):
            return self._plan_service.get_status(request.plan_id)
        if isinstance(request, BridgePlanCancelRequest):
            return self._plan_service.cancel(
                request.plan_id,
                audit_source="mcp",
            )
        raise ValueError("Unsupported bridge plan operation.")

    def _remember(
        self,
        request: BridgePlanRequest,
        response: BridgeResponse,
    ) -> BridgeResponse:
        if len(self._responses) >= self._max_tracked_requests:
            oldest = next(iter(self._responses))
            del self._responses[oldest]
        self._responses[request.request_id] = (self._fingerprint(request), response)
        return response

    def _ensure_owner_thread(self) -> None:
        if get_ident() != self._owner_thread_id:
            raise RuntimeError("The plan dispatcher must run on its owner GUI thread.")

    @staticmethod
    def _fingerprint(request: BridgePlanRequest) -> str:
        return json.dumps(
            request.model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _error(
        request_id: UUID,
        code: BridgeErrorCode,
        message: str,
        *,
        status: BridgeResponseStatus = BridgeResponseStatus.REJECTED,
    ) -> BridgeResponse:
        return BridgeResponse(
            request_id=request_id,
            status=status,
            error=BridgeError(code=code, message=message),
        )

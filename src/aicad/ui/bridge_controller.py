from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID

from aicad.audit.service import AuditService
from aicad.bridge.dispatcher import GUI_REQUEST_TIMEOUT_SECONDS, BridgeDispatcher
from aicad.bridge.plan_dispatcher import PlanBridgeDispatcher
from aicad.bridge.protocol import BridgeRequest, BridgeResponse
from aicad.bridge.session import (
    BridgeSessionRecord,
    BridgeSessionStore,
    default_session_store,
)
from aicad.bridge.transport import LocalTcpBridgeServer
from aicad.core.tool_registry import ToolRegistry
from aicad.orchestration.plan_service import (
    CompositeValidatedPlan,
    PlanService,
    PlanStatusSnapshot,
)
from aicad.runtime import get_audit_service, get_plan_service, get_tool_registry


GUI_DISPATCH_INTERVAL_MS = 50


class GuiBridgeController:
    """Own the local bridge lifecycle from the FreeCAD GUI thread."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        plan_service: PlanService | None = None,
        session_store: BridgeSessionStore | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        self._audit_service = audit_service or get_audit_service()
        self._confirmation_listener: Callable[[BridgeRequest], None] | None = None
        self._plan_confirmation_listener: (
            Callable[[CompositeValidatedPlan], None] | None
        ) = None
        self._dispatcher = BridgeDispatcher(
            registry,
            audit_service=self._audit_service,
            on_confirmation_requested=self._request_confirmation,
            request_timeout=GUI_REQUEST_TIMEOUT_SECONDS,
        )
        self._plan_dispatcher = PlanBridgeDispatcher(
            registry,
            plan_service or get_plan_service(),
            on_confirmation_requested=self._request_plan_confirmation,
            context_reader=lambda: registry.execute(
                "cad.get_context_snapshot",
                {"detail_level": "work", "max_objects": 25, "cursor": 0},
            ),
        )
        self._server = LocalTcpBridgeServer(self._submit)
        self._session_store = session_store or default_session_store()
        self._session_record: BridgeSessionRecord | None = None
        self._timer: object | None = None
        self._tick_running = False

    @property
    def is_running(self) -> bool:
        return self._server.is_running and self._session_record is not None

    @property
    def session_record(self) -> BridgeSessionRecord:
        if self._session_record is None:
            raise RuntimeError("The GUI bridge has not been started.")
        return self._session_record

    def set_confirmation_listener(
        self,
        listener: Callable[[BridgeRequest], None],
    ) -> None:
        self._confirmation_listener = listener

    def set_plan_confirmation_listener(
        self,
        listener: Callable[[CompositeValidatedPlan], None],
    ) -> None:
        self._plan_confirmation_listener = listener

    @property
    def plan_service(self) -> PlanService:
        return self._plan_dispatcher.plan_service

    def start(self) -> BridgeSessionRecord:
        if self.is_running:
            return self.session_record

        from PySide import QtCore, QtWidgets

        application = QtWidgets.QApplication.instance()
        if application is None:
            raise RuntimeError("The GUI bridge requires a running Qt application.")
        endpoint = self._server.start()
        try:
            record = self._session_store.publish(
                endpoint,
                session_id=self._audit_service.session_id,
            )
        except Exception:
            self._server.stop()
            raise

        timer = QtCore.QTimer(application)
        timer.setInterval(GUI_DISPATCH_INTERVAL_MS)
        timer.timeout.connect(self._tick)
        timer.start()
        application.aboutToQuit.connect(stop_gui_bridge)

        self._session_record = record
        self._timer = timer
        return record

    def resolve_confirmation(
        self,
        request_id: UUID,
        *,
        approved: bool,
        automatic: bool = False,
    ) -> BridgeResponse:
        return self._dispatcher.resolve_confirmation(
            request_id,
            approved=approved,
            automatic=automatic,
        )

    def is_remote_plan(self, plan_id: UUID) -> bool:
        return self._plan_dispatcher.is_remote_plan(plan_id)

    def resolve_plan_confirmation(
        self,
        plan_id: UUID,
        *,
        approved: bool,
        on_progress: Callable[[PlanStatusSnapshot], None] | None = None,
        automatic: bool = False,
    ) -> PlanStatusSnapshot:
        return self._plan_dispatcher.resolve_confirmation(
            plan_id,
            approved=approved,
            on_progress=on_progress,
            automatic=automatic,
        )

    def stop(self) -> None:
        timer = self._timer
        if timer is not None:
            timer.stop()
        self._timer = None

        self._dispatcher.close()
        self._plan_dispatcher.close()
        self._server.stop()
        record = self._session_record
        self._session_record = None
        if record is not None:
            self._session_store.clear(record.session_id)

    def _tick(self) -> None:
        if self._tick_running:
            return
        self._tick_running = True
        try:
            self._dispatcher.expire_requests()
            self._dispatcher.process_next()
            self._plan_dispatcher.process_next()
        finally:
            self._tick_running = False

    def _submit(self, payload: Mapping[str, Any]) -> BridgeResponse:
        if "operation" in payload:
            return self._plan_dispatcher.submit(payload)
        return self._dispatcher.submit(payload)

    def _request_confirmation(self, request: BridgeRequest) -> None:
        listener = self._confirmation_listener
        if listener is None:
            raise RuntimeError("No GUI confirmation listener is available.")
        listener(request)

    def _request_plan_confirmation(self, plan: CompositeValidatedPlan) -> None:
        listener = self._plan_confirmation_listener
        if listener is None:
            raise RuntimeError("No GUI plan confirmation listener is available.")
        listener(plan)


_controller: GuiBridgeController | None = None


def get_or_start_gui_bridge(
    confirmation_listener: Callable[[BridgeRequest], None],
    plan_confirmation_listener: Callable[[CompositeValidatedPlan], None] | None = None,
) -> GuiBridgeController:
    global _controller

    if _controller is None:
        _controller = GuiBridgeController(
            get_tool_registry(),
            audit_service=get_audit_service(),
        )
    _controller.set_confirmation_listener(confirmation_listener)
    if plan_confirmation_listener is not None:
        _controller.set_plan_confirmation_listener(plan_confirmation_listener)
    if not _controller.is_running:
        _controller.start()
    return _controller


def get_gui_bridge() -> GuiBridgeController | None:
    return _controller


def stop_gui_bridge() -> None:
    global _controller

    controller = _controller
    _controller = None
    if controller is not None and controller.is_running:
        controller.stop()

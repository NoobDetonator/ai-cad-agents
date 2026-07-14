from concurrent.futures import ThreadPoolExecutor
from threading import Event, get_ident
import time
from typing import Any
from uuid import uuid4

import pytest

from aicad.application import build_cad_tool_registry
from aicad.audit import (
    AuditActionStatus,
    AuditApprovalDecision,
    AuditService,
    AuditSource,
    AuditStore,
)
from aicad.bridge.dispatcher import BridgeDispatcher
from aicad.bridge.protocol import (
    BridgeErrorCode,
    BridgeRequest,
    BridgeResponseStatus,
)


class RecordingAdapter:
    def __init__(self) -> None:
        self.read_thread_ids: list[int] = []
        self.create_thread_ids: list[int] = []
        self.created_names: list[str] = []

    def get_document_summary(self) -> dict[str, Any]:
        self.read_thread_ids.append(get_ident())
        return {"active": False, "objects": []}

    def get_selection(self) -> dict[str, Any]:
        return {"selection": []}

    def get_context_snapshot(
        self,
        detail_level: str = "work",
        max_objects: int = 25,
        cursor: int = 0,
    ) -> dict[str, Any]:
        self.read_thread_ids.append(get_ident())
        return {
            "detail_level": detail_level,
            "max_objects": max_objects,
            "cursor": cursor,
        }

    def create_box(
        self,
        length: float,
        width: float,
        height: float,
        name: str = "AIBox",
    ) -> dict[str, Any]:
        self.create_thread_ids.append(get_ident())
        self.created_names.append(name)
        return {
            "name": name,
            "dimensions_mm": [length, width, height],
            "valid": True,
        }

    def create_cylinder(
        self,
        diameter: float,
        height: float,
        name: str = "AICylinder",
    ) -> dict[str, Any]:
        self.create_thread_ids.append(get_ident())
        self.created_names.append(name)
        return {
            "name": name,
            "diameter_mm": diameter,
            "height_mm": height,
            "valid": True,
        }

    def validate_document(self) -> dict[str, Any]:
        return {"valid": True, "errors": []}

    def undo(self) -> dict[str, bool]:
        return {"undone": True}


def request_payload(
    tool_name: str = "cad.get_document_summary",
    *,
    arguments: dict[str, object] | None = None,
    request_id: object | None = None,
) -> dict[str, object]:
    request = BridgeRequest(
        request_id=request_id or uuid4(),
        tool_name=tool_name,
        arguments=arguments or {},
        source="mcp",
    )
    return request.model_dump(mode="json")


def wait_until_queued(dispatcher: BridgeDispatcher) -> None:
    deadline = time.monotonic() + 1
    while dispatcher.queued_count == 0 and time.monotonic() < deadline:
        Event().wait(0.001)
    assert dispatcher.queued_count > 0


def test_read_executes_only_when_owner_thread_processes_queue() -> None:
    adapter = RecordingAdapter()
    dispatcher = BridgeDispatcher(build_cad_tool_registry(adapter))
    owner_thread = get_ident()

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(dispatcher.submit, request_payload())
        wait_until_queued(dispatcher)
        assert dispatcher.process_next() is True
        response = future.result(timeout=1)

    assert response.status is BridgeResponseStatus.COMPLETED
    assert response.result == {"active": False, "objects": []}
    assert adapter.read_thread_ids == [owner_thread]


def test_mutation_requires_confirmation_and_is_idempotent() -> None:
    adapter = RecordingAdapter()
    confirmations: list[BridgeRequest] = []
    dispatcher = BridgeDispatcher(
        build_cad_tool_registry(adapter),
        on_confirmation_requested=confirmations.append,
    )
    payload = request_payload(
        "cad.create_box",
        arguments={
            "length": 10,
            "width": 20,
            "height": 30,
            "name": "BridgeBox",
        },
    )

    pending = dispatcher.submit(payload)
    assert pending.status is BridgeResponseStatus.PENDING_CONFIRMATION
    assert adapter.created_names == []
    assert dispatcher.process_next() is True
    assert confirmations[0].request_id == pending.request_id

    completed = dispatcher.resolve_confirmation(pending.request_id, approved=True)
    assert completed.status is BridgeResponseStatus.COMPLETED
    assert adapter.created_names == ["BridgeBox"]
    assert adapter.create_thread_ids == [get_ident()]

    polled = dispatcher.submit(payload)
    assert polled == completed
    assert adapter.created_names == ["BridgeBox"]

    mismatched = request_payload(
        "cad.create_box",
        request_id=str(pending.request_id),
        arguments={"length": 1, "width": 2, "height": 3},
    )
    rejected = dispatcher.submit(mismatched)
    assert rejected.status is BridgeResponseStatus.REJECTED
    assert rejected.error is not None
    assert rejected.error.code is BridgeErrorCode.INVALID_REQUEST


def test_mutations_are_presented_one_at_a_time() -> None:
    adapter = RecordingAdapter()
    confirmations: list[BridgeRequest] = []
    dispatcher = BridgeDispatcher(
        build_cad_tool_registry(adapter),
        on_confirmation_requested=confirmations.append,
    )
    first = dispatcher.submit(
        request_payload(
            "cad.create_box",
            arguments={"length": 1, "width": 2, "height": 3, "name": "First"},
        )
    )
    second = dispatcher.submit(
        request_payload(
            "cad.create_box",
            arguments={"length": 4, "width": 5, "height": 6, "name": "Second"},
        )
    )

    assert dispatcher.process_next() is True
    assert dispatcher.process_next() is False
    assert [request.arguments["name"] for request in confirmations] == ["First"]

    cancelled = dispatcher.resolve_confirmation(first.request_id, approved=False)
    assert cancelled.status is BridgeResponseStatus.CANCELLED
    assert dispatcher.process_next() is True
    assert [request.arguments["name"] for request in confirmations] == [
        "First",
        "Second",
    ]
    dispatcher.resolve_confirmation(second.request_id, approved=False)
    assert adapter.created_names == []


def test_expired_mutation_cannot_execute_late() -> None:
    adapter = RecordingAdapter()
    now = [100.0]
    dispatcher = BridgeDispatcher(
        build_cad_tool_registry(adapter),
        request_timeout=5,
        clock=lambda: now[0],
    )
    pending = dispatcher.submit(
        request_payload(
            "cad.create_box",
            arguments={"length": 1, "width": 2, "height": 3},
        )
    )
    assert dispatcher.process_next() is True

    now[0] = 106.0
    assert dispatcher.expire_requests() == 1
    expired = dispatcher.resolve_confirmation(pending.request_id, approved=True)

    assert expired.status is BridgeResponseStatus.EXPIRED
    assert expired.error is not None
    assert expired.error.code is BridgeErrorCode.TIMEOUT
    assert adapter.created_names == []


def test_expired_read_is_never_executed_later() -> None:
    adapter = RecordingAdapter()
    dispatcher = BridgeDispatcher(
        build_cad_tool_registry(adapter),
        request_timeout=0.01,
    )

    response = dispatcher.submit(request_payload())

    assert response.status is BridgeResponseStatus.EXPIRED
    assert dispatcher.process_next() is False
    assert adapter.read_thread_ids == []


def test_close_wakes_waiters_and_rejects_new_work() -> None:
    adapter = RecordingAdapter()
    dispatcher = BridgeDispatcher(build_cad_tool_registry(adapter))
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(dispatcher.submit, request_payload())
        wait_until_queued(dispatcher)
        dispatcher.close()
        cancelled = future.result(timeout=1)

    assert cancelled.status is BridgeResponseStatus.CANCELLED
    after_close = dispatcher.submit(request_payload())
    assert after_close.status is BridgeResponseStatus.FAILED
    assert after_close.error is not None
    assert after_close.error.code is BridgeErrorCode.GUI_UNAVAILABLE


def test_dispatcher_owner_operations_reject_worker_threads() -> None:
    dispatcher = BridgeDispatcher(build_cad_tool_registry(RecordingAdapter()))

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(dispatcher.process_next)
        with pytest.raises(RuntimeError, match="owner thread"):
            future.result(timeout=1)


def test_nonterminal_request_limit_is_enforced() -> None:
    dispatcher = BridgeDispatcher(
        build_cad_tool_registry(RecordingAdapter()),
        max_tracked_requests=1,
    )
    dispatcher.submit(
        request_payload(
            "cad.create_box",
            arguments={"length": 1, "width": 2, "height": 3},
        )
    )
    rejected = dispatcher.submit(
        request_payload(
            "cad.create_box",
            arguments={"length": 4, "width": 5, "height": 6},
        )
    )

    assert rejected.status is BridgeResponseStatus.REJECTED
    assert rejected.error is not None
    assert rejected.error.code is BridgeErrorCode.QUEUE_FULL


def test_mcp_dispatcher_audits_automatic_approval_and_result(tmp_path) -> None:
    adapter = RecordingAdapter()
    registry = build_cad_tool_registry(adapter)
    audit = AuditService(AuditStore(tmp_path / "audit"))
    dispatcher = BridgeDispatcher(
        registry,
        audit_service=audit,
        on_confirmation_requested=lambda _: None,
    )
    payload = request_payload(
        "cad.create_box",
        arguments={"length": 1, "width": 2, "height": 3, "name": "Audited"},
    )

    pending = dispatcher.submit(payload)
    assert dispatcher.process_next() is True
    completed = dispatcher.resolve_confirmation(
        pending.request_id,
        approved=True,
        automatic=True,
    )

    assert completed.status is BridgeResponseStatus.COMPLETED
    record = audit.store.load(audit.session_id, pending.request_id)
    assert record.source is AuditSource.MCP
    assert record.status is AuditActionStatus.COMPLETED
    assert record.approval.decision is AuditApprovalDecision.APPROVED_AUTOMATIC
    assert record.result["name"] == "Audited"

    denied_payload = request_payload(
        "cad.create_box",
        arguments={"length": 2, "width": 2, "height": 2, "name": "Denied"},
    )
    denied_pending = dispatcher.submit(denied_payload)
    assert dispatcher.process_next() is True
    denied = dispatcher.resolve_confirmation(
        denied_pending.request_id,
        approved=False,
    )
    assert denied.status is BridgeResponseStatus.CANCELLED
    denied_record = audit.store.load(audit.session_id, denied_pending.request_id)
    assert denied_record.status is AuditActionStatus.CANCELLED
    assert denied_record.approval.decision is AuditApprovalDecision.DENIED
    assert "Denied" not in adapter.created_names

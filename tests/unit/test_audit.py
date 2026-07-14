from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from uuid import UUID, uuid4

import pytest

from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.audit import (
    REDACTION_MARKER,
    AuditActionKind,
    AuditActionRecord,
    AuditActionStatus,
    AuditApprovalDecision,
    AuditApprovalRecord,
    AuditPlanRecord,
    AuditRecorder,
    AuditRedactionError,
    AuditRetentionPolicy,
    AuditSource,
    AuditService,
    AuditStore,
    AuditStoreError,
    AuditToolCallRecord,
    AuditTransactionOutcome,
    AuditTransactionRecord,
    AuditValidationRecord,
    AuditValidationStatus,
    default_audit_store,
    redact_json,
)
from aicad.core.tool_registry import (
    ToolRegistry,
    ToolRisk,
    ToolSpec,
    build_default_registry,
)
from aicad.core.transactions import (
    CadTransactionOutcome,
    mark_transaction,
    transaction_trace,
    transaction_title,
)


NOW = datetime(2026, 7, 14, 15, 0, tzinfo=timezone.utc)
SESSION = UUID("12345678-1234-5678-1234-567812345678")


def tool_call(*, secret: str | None = None) -> AuditToolCallRecord:
    arguments: dict[str, object] = {
        "length": 10.0,
        "width": 20.0,
        "height": 30.0,
    }
    if secret is not None:
        arguments["api_key"] = secret
    return AuditToolCallRecord(
        call_id="box-1",
        tool_name="cad.create_box",
        arguments=arguments,
        risk=ToolRisk.MODIFY,
        expected_validations=("registry.arguments", "document.valid"),
    )


def pending_record(
    *,
    session_id: UUID = SESSION,
    action_id: UUID | None = None,
    started_at: datetime = NOW,
) -> AuditActionRecord:
    return AuditActionRecord(
        session_id=session_id,
        action_id=action_id or uuid4(),
        source=AuditSource.LOCAL_CHAT,
        kind=AuditActionKind.TOOL,
        started_at=started_at,
        original_request="Crie uma caixa.",
        intention="Criar uma caixa validada.",
        tool_calls=(tool_call(),),
        approval=AuditApprovalRecord(decision=AuditApprovalDecision.PENDING),
    )


def test_recursive_redaction_removes_keys_assignments_tokens_and_user_paths() -> None:
    secret = "sk-live-very-secret-value"
    payload = {
        "api_key": secret,
        "nested": {"session-token": "bridge-secret"},
        "message": (
            "Authorization: abcdefghijklmnop; "
            "Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature; "
            r"arquivo C:\Users\Alice\Documents\part.FCStd"
        ),
        "known": f"prefix {secret} suffix",
        "safe": "cad.create_box",
        "state_token": {"revision": 7},
    }

    result = redact_json(payload, sensitive_values=(secret,))

    assert result.value["api_key"] == REDACTION_MARKER
    assert result.value["nested"]["session-token"] == REDACTION_MARKER
    assert "abcdefghijklmnop" not in result.value["message"]
    assert "eyJhbGci" not in result.value["message"]
    assert "Alice" not in result.value["message"]
    assert secret not in result.value["known"]
    assert result.value["safe"] == "cad.create_box"
    assert result.value["state_token"] == {"revision": 7}
    assert result.redaction_count >= 5
    assert payload["api_key"] == secret


def test_redaction_rejects_unbounded_or_non_json_data() -> None:
    with pytest.raises(AuditRedactionError, match="non-finite"):
        redact_json({"value": float("inf")})
    with pytest.raises(AuditRedactionError, match="nesting"):
        redact_json({"a": {"b": {"c": 1}}}, max_depth=1)
    with pytest.raises(AuditRedactionError, match="unsupported"):
        redact_json({"value": object()})


def test_action_contract_requires_plan_calls_and_terminal_metadata() -> None:
    plan = AuditPlanRecord(
        contract_version="1.0",
        plan_id=uuid4(),
        plan_hash="a" * 64,
        base_state_token={
            "document_id": "Doc",
            "document_fingerprint": "a" * 64,
            "selection_fingerprint": "b" * 64,
            "revision": 1,
        },
        steps=("Criar caixa.", "Criar cilindro."),
    )
    second_call = tool_call().model_copy(
        update={"call_id": "cylinder-1", "tool_name": "cad.create_cylinder"}
    )
    record = AuditActionRecord(
        session_id=SESSION,
        action_id=uuid4(),
        source=AuditSource.AI_CHAT,
        kind=AuditActionKind.PLAN,
        started_at=NOW,
        intention="Criar dois sólidos.",
        plan=plan,
        tool_calls=(tool_call(), second_call),
        approval=AuditApprovalRecord(decision=AuditApprovalDecision.PENDING),
    )

    assert record.schema_version == "1.0"
    with pytest.raises(ValueError, match="duration"):
        AuditActionRecord.model_validate(
            {
                **record.model_dump(mode="json"),
                "status": "completed",
                "finished_at": NOW.isoformat(),
            }
        )
    with pytest.raises(ValueError, match="plan metadata"):
        AuditActionRecord(
            session_id=SESSION,
            action_id=uuid4(),
            source=AuditSource.AI_CHAT,
            kind=AuditActionKind.PLAN,
            started_at=NOW,
            tool_calls=(tool_call(),),
            approval=AuditApprovalRecord(decision=AuditApprovalDecision.PENDING),
        )
    with pytest.raises(ValueError, match="explicit approval"):
        AuditActionRecord.model_validate(
            {
                **pending_record().model_dump(mode="json"),
                "status": "completed",
                "finished_at": NOW.isoformat(),
                "duration_ms": 1,
            }
        )
    with pytest.raises(ValueError, match="approval decision"):
        AuditActionRecord.model_validate(
            {
                **pending_record().model_copy(
                    update={
                        "tool_calls": (
                            tool_call().model_copy(update={"risk": ToolRisk.READ}),
                        )
                    }
                ).model_dump(mode="json"),
                "status": "completed",
                "finished_at": NOW.isoformat(),
                "duration_ms": 1,
            }
        )


def test_recorder_persists_redacted_lifecycle_and_exports_without_overwrite(
    tmp_path,
) -> None:
    secret = "sk-live-never-write-this"
    ticks = iter((10.0, 10.25))
    store = AuditStore(tmp_path / "audit", now=lambda: NOW)
    recorder = AuditRecorder(
        store,
        session_id=SESSION,
        now=lambda: NOW,
        monotonic=lambda: next(ticks),
    )

    started = recorder.start_action(
        source=AuditSource.AI_CHAT,
        kind=AuditActionKind.TOOL,
        original_request=f"Crie uma caixa; api_key={secret}",
        intention="Criar uma caixa validada.",
        tool_calls=(tool_call(secret=secret),),
        sensitive_values=(secret,),
    )
    approved = recorder.record_approval(
        started,
        decision=AuditApprovalDecision.APPROVED_MANUAL,
        source="ui",
    )
    finished = recorder.finish_action(
        approved,
        status=AuditActionStatus.COMPLETED,
        result={"name": "Box", "session_token": secret},
        validations=(
            AuditValidationRecord(
                name="document.valid",
                status=AuditValidationStatus.PASSED,
                details={"valid": True},
            ),
        ),
        transactions=(
            AuditTransactionRecord(
                transaction_id="tx-box-1",
                call_id="box-1",
                sequence=1,
                label="AI CAD: create Box",
                outcome=AuditTransactionOutcome.COMMITTED,
            ),
        ),
        sensitive_values=(secret,),
    )

    assert finished.revision == 3
    assert finished.duration_ms == 250
    assert finished.status is AuditActionStatus.COMPLETED
    assert finished.redaction_count >= 3
    loaded = store.load(SESSION, finished.action_id)
    assert loaded == finished
    record_path = (
        tmp_path / "audit" / "v1" / SESSION.hex / f"{finished.action_id.hex}.json"
    )
    assert secret.encode() not in record_path.read_bytes()

    destination = tmp_path / "audit-export.json"
    assert store.export_session(SESSION, destination) == destination
    exported = json.loads(destination.read_text(encoding="utf-8"))
    assert exported["schema_version"] == "1.0"
    assert exported["session_id"] == str(SESSION)
    assert exported["records"][0]["action_id"] == str(finished.action_id)
    assert secret not in destination.read_text(encoding="utf-8")
    with pytest.raises(AuditStoreError, match="already exists"):
        store.export_session(SESSION, destination)


def test_store_enforces_revision_sequence_and_idempotent_save(tmp_path) -> None:
    store = AuditStore(tmp_path / "audit", now=lambda: NOW)
    record = pending_record()

    first = store.save(record)
    assert store.save(first) == first
    with pytest.raises(AuditStoreError, match="exactly one revision"):
        store.save(first.model_copy(update={"revision": 3, "intention": "changed"}))

    second = first.model_copy(update={"revision": 2, "intention": "changed"})
    assert store.save(second).revision == 2


def test_store_applies_age_action_and_session_retention(tmp_path) -> None:
    policy = AuditRetentionPolicy(
        max_age_days=30,
        max_sessions=1,
        max_actions_per_session=2,
    )
    store = AuditStore(tmp_path / "audit", retention=policy, now=lambda: NOW)
    first_session = uuid4()
    action_ids = [uuid4(), uuid4(), uuid4()]
    for offset, action_id in enumerate(action_ids):
        store.save(
            pending_record(
                session_id=first_session,
                action_id=action_id,
                started_at=NOW + timedelta(seconds=offset),
            )
        )
    assert [item.action_id for item in store.list_records(first_session)] == action_ids[1:]

    second_session = uuid4()
    newest = pending_record(
        session_id=second_session,
        started_at=NOW + timedelta(minutes=1),
    )
    store.save(newest)
    assert store.list_records(second_session) == (newest,)
    with pytest.raises(AuditStoreError, match="unavailable"):
        store.list_records(first_session)

    old_session = uuid4()
    old = pending_record(
        session_id=old_session,
        started_at=NOW - timedelta(days=31),
    )
    store.save(old)
    with pytest.raises(AuditStoreError):
        store.load(old_session, old.action_id)


def test_default_store_honors_explicit_local_directory(monkeypatch, tmp_path) -> None:
    destination = tmp_path / "private-audit"
    monkeypatch.setenv("AICAD_AUDIT_DIR", str(destination))

    store = default_audit_store()

    assert store.root_directory == destination.absolute()
    assert not destination.exists()


def test_audit_service_links_approval_result_and_transaction(tmp_path) -> None:
    store = AuditStore(tmp_path / "audit")
    service = AuditService(store, session_id=SESSION)
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="cad.test_mutation",
            description="Test an audited mutation.",
            risk=ToolRisk.MODIFY,
            input_schema={"type": "object", "additionalProperties": False},
        ),
        lambda: _audited_mutation(),
    )

    action_id = service.begin_tool(
        registry,
        "cad.test_mutation",
        {},
        source=AuditSource.LOCAL_CHAT,
        original_request="Faça a alteração.",
    )
    service.approve(action_id, automatic=False, source="ui")
    assert service.execute_tool(action_id, registry) == {"valid": True}

    record = store.load(SESSION, action_id)
    assert record.status is AuditActionStatus.COMPLETED
    assert record.approval.decision is AuditApprovalDecision.APPROVED_MANUAL
    assert record.result == {"valid": True}
    assert [item.status for item in record.validations] == [
        AuditValidationStatus.PASSED,
        AuditValidationStatus.PASSED,
        AuditValidationStatus.PASSED,
    ]
    assert len(record.transactions) == 1
    assert record.transactions[0].outcome is AuditTransactionOutcome.COMMITTED
    assert record.transactions[0].transaction_id in record.transactions[0].label


def _audited_mutation() -> dict[str, bool]:
    transaction_title("test mutation")
    mark_transaction(CadTransactionOutcome.COMMITTED)
    return {"valid": True}


def test_audit_export_uses_raw_path_in_memory_and_persists_redacted_path(
    tmp_path,
) -> None:
    store = AuditStore(tmp_path / "audit")
    service = AuditService(store, session_id=SESSION)
    registry = build_default_registry()
    registry.bind("cad.get_audit_history", service.get_history)
    registry.bind("cad.export_audit_history", service.export_history)
    destination = (tmp_path / "session-audit.json").absolute()

    action_id = service.begin_tool(
        registry,
        "cad.export_audit_history",
        {"destination": str(destination), "overwrite": False},
        source=AuditSource.LOCAL_CHAT,
        original_request=f"Exporte para {destination}",
    )
    service.approve(action_id, automatic=False, source="ui")
    result = service.execute_tool(action_id, registry)

    assert destination.is_file()
    assert result["destination"] == str(destination)
    record = store.load(SESSION, action_id)
    serialized = record.model_dump_json()
    assert record.status is AuditActionStatus.COMPLETED
    assert str(destination) not in serialized
    bundle = json.loads(destination.read_text(encoding="utf-8"))
    exported_record = next(
        item for item in bundle["records"] if item["action_id"] == str(action_id)
    )
    assert exported_record["status"] == "completed"
    assert str(destination) not in destination.read_text(encoding="utf-8")


def test_ai_turn_groups_child_reads_and_records_understanding(tmp_path) -> None:
    service = AuditService(AuditStore(tmp_path / "audit"), session_id=SESSION)
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="cad.test_read",
            description="Test an audited read.",
            risk=ToolRisk.READ,
            input_schema={"type": "object", "additionalProperties": False},
        ),
        lambda: {"value": 42},
    )

    turn_id = service.begin_turn(
        source=AuditSource.AI_CHAT,
        original_request="Entenda a peça antes de responder.",
    )
    assert service.run_tool(
        registry,
        "cad.test_read",
        {},
        source=AuditSource.AI_CHAT,
        original_request="Entenda a peça antes de responder.",
        parent_action_id=turn_id,
    ) == {"value": 42}
    service.finish_turn(
        turn_id,
        status=AuditActionStatus.COMPLETED,
        intention="Ler o estado e explicar a peça.",
        assumptions=("O documento ativo é a referência.",),
        result={"status": "answered"},
    )

    turn = service.store.load(SESSION, turn_id)
    child = next(
        record
        for record in service.store.list_records(SESSION)
        if record.parent_action_id == turn_id
    )
    assert turn.kind is AuditActionKind.TURN
    assert turn.status is AuditActionStatus.COMPLETED
    assert turn.intention == "Ler o estado e explicar a peça."
    assert turn.assumptions == ("O documento ativo é a referência.",)
    assert child.kind is AuditActionKind.TOOL
    assert child.result == {"value": 42}


def test_undo_does_not_misattribute_an_intervening_freecad_transaction(
    monkeypatch,
) -> None:
    class Document:
        UndoCount = 2

        def undo(self) -> None:
            self.UndoCount -= 1

        def recompute(self) -> None:
            pass

    class App:
        ActiveDocument = Document()

    adapter = FreeCadAdapter()
    adapter._audited_transactions.append(("tx-original", "AI CAD original", 1))
    monkeypatch.setattr(adapter, "_modules", lambda: (App, object()))

    with transaction_trace(uuid4(), "undo-intervening") as intervening:
        assert adapter.undo() == {"undone": True}
    assert intervening.outcome is CadTransactionOutcome.UNDONE
    assert intervening.transaction_id != "tx-original"
    assert adapter._audited_transactions == [
        ("tx-original", "AI CAD original", 1)
    ]

    with transaction_trace(uuid4(), "undo-original") as original:
        assert adapter.undo() == {"undone": True}
    assert original.outcome is CadTransactionOutcome.UNDONE
    assert original.transaction_id == "tx-original"
    assert adapter._audited_transactions == []

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import os
import sys
import time
import traceback
from uuid import uuid4


project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(project_root / "src"))

from aicad.bridge.protocol import (
    BridgePlanStatusRequest,
    BridgePlanSubmitRequest,
    BridgeRequest,
    BridgeResponseStatus,
    BridgeTransportRequest,
)
from aicad.bridge.session import default_session_store
from aicad.bridge.transport import TcpBridgeClient
from aicad.core.context import DocumentStateToken
from aicad.orchestration import OrchestrationPlan, PlannedToolCall
from aicad.orchestration.plan_service import (
    CompositePlanStatus,
    CompositeValidatedPlan,
)
from aicad.runtime import get_audit_service, get_tool_registry


import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets


result_path = Path(os.environ["AICAD_GUI_RESULT"])
screenshot_path = Path(os.environ["AICAD_GUI_SCREENSHOT"])


def wait_for_ui(predicate, timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QtWidgets.QApplication.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    assert predicate(), "A interface nao atingiu o estado esperado dentro do prazo."


def run_bridge_request(client: TcpBridgeClient, request: BridgeTransportRequest):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(client.request, request)
        wait_for_ui(future.done)
        return future.result(timeout=1)


def poll_completed(client: TcpBridgeClient, request: BridgeRequest):
    response = run_bridge_request(client, request)
    assert response.status is BridgeResponseStatus.COMPLETED
    return response


def inspect() -> None:
    try:
        for document_name in list(App.listDocuments()):
            App.closeDocument(document_name)

        assert "AICadWorkbench" in Gui.listWorkbenches()
        Gui.activateWorkbench("AICadWorkbench")
        QtWidgets.QApplication.processEvents()

        main_window = Gui.getMainWindow()
        dock = main_window.findChild(QtWidgets.QDockWidget, "TalosMcpDock")
        assert dock is not None and dock.isVisible()

        bridge_status = dock.findChild(QtWidgets.QLabel, "TalosBridgeStatus")
        session_details = dock.findChild(QtWidgets.QLabel, "TalosSessionDetails")
        catalog_summary = dock.findChild(QtWidgets.QLabel, "TalosCatalogSummary")
        document_status = dock.findChild(QtWidgets.QLabel, "TalosDocumentStatus")
        validate_button = dock.findChild(
            QtWidgets.QPushButton, "TalosValidateDocument"
        )
        automatic = dock.findChild(QtWidgets.QCheckBox, "TalosAutomaticApproval")
        confirmation = dock.findChild(QtWidgets.QGroupBox, "TalosConfirmation")
        confirmation_text = dock.findChild(QtWidgets.QLabel, "TalosConfirmationText")
        approve_button = dock.findChild(QtWidgets.QPushButton, "TalosApprove")
        reject_button = dock.findChild(QtWidgets.QPushButton, "TalosReject")
        copy_config = dock.findChild(QtWidgets.QPushButton, "TalosCopyMcpConfig")
        event_log = dock.findChild(QtWidgets.QTextBrowser, "TalosEventLog")
        assert all(
            widget is not None
            for widget in (
                bridge_status,
                session_details,
                catalog_summary,
                document_status,
                validate_button,
                automatic,
                confirmation,
                confirmation_text,
                approve_button,
                reject_button,
                copy_config,
                event_log,
            )
        )

        for removed_name in (
            "AICadPrompt",
            "AICadSend",
            "AICadConfigureApiKey",
            "AICadRemoveApiKey",
            "AICadUseDeepSeek",
            "AICadQuickTestMode",
        ):
            assert dock.findChild(QtCore.QObject, removed_name) is None

        assert automatic.isChecked() is False
        assert "115" in catalog_summary.text()
        wait_for_ui(lambda: "ativa" in bridge_status.text().lower())

        session = default_session_store().load()
        assert session.session_id == get_audit_service().session_id
        assert str(session.session_id) not in session_details.text()
        client = TcpBridgeClient(session.endpoint)

        summary = run_bridge_request(
            client,
            BridgeRequest(
                request_id=uuid4(),
                tool_name="cad.get_document_summary",
                arguments={},
                source="mcp",
            ),
        )
        assert summary.status is BridgeResponseStatus.COMPLETED
        assert summary.result["active"] is False

        new_document = BridgeRequest(
            request_id=uuid4(),
            tool_name="cad.new_document",
            arguments={"name": "TalosPanelSmoke"},
            source="mcp",
        )
        pending_document = run_bridge_request(client, new_document)
        assert pending_document.status is BridgeResponseStatus.PENDING_CONFIRMATION
        wait_for_ui(
            lambda: confirmation.isVisible()
            and "cad.new_document" in confirmation_text.text()
        )
        approve_button.click()
        wait_for_ui(lambda: App.ActiveDocument is not None)
        poll_completed(client, new_document)
        assert App.ActiveDocument.Name == "TalosPanelSmoke"

        create_box = BridgeRequest(
            request_id=uuid4(),
            tool_name="cad.create_box",
            arguments={
                "length": 12,
                "width": 10,
                "height": 4,
                "name": "PanelBase",
            },
            source="mcp",
        )
        pending_box = run_bridge_request(client, create_box)
        assert pending_box.status is BridgeResponseStatus.PENDING_CONFIRMATION
        wait_for_ui(
            lambda: confirmation.isVisible()
            and "cad.create_box" in confirmation_text.text()
        )
        approve_button.click()
        wait_for_ui(lambda: len(App.ActiveDocument.Objects) == 1)
        poll_completed(client, create_box)

        automatic.setChecked(True)
        create_cylinder = BridgeRequest(
            request_id=uuid4(),
            tool_name="cad.create_cylinder",
            arguments={
                "diameter": 4,
                "height": 8,
                "name": "AutoPin",
            },
            source="mcp",
        )
        pending_cylinder = run_bridge_request(client, create_cylinder)
        assert pending_cylinder.status is BridgeResponseStatus.PENDING_CONFIRMATION
        wait_for_ui(lambda: len(App.ActiveDocument.Objects) == 2)
        poll_completed(client, create_cylinder)
        automatic.setChecked(False)

        validate_button.click()
        wait_for_ui(lambda: "Valida" in event_log.toPlainText())
        copy_config.click()
        copied = json.loads(QtWidgets.QApplication.clipboard().text())
        assert copied["mcpServers"]["talos"]["command"].endswith(
            ("talos-freecad-mcp.exe", "aicad-mcp.exe")
        )
        assert "token" not in json.dumps(copied).lower()

        context = run_bridge_request(
            client,
            BridgeRequest(
                request_id=uuid4(),
                tool_name="cad.get_context_snapshot",
                arguments={"detail_level": "work", "max_objects": 25, "cursor": 0},
                source="mcp",
            ),
        )
        base_state = DocumentStateToken.model_validate(context.result["state_token"])
        proposal = OrchestrationPlan(
            intention="Criar duas pecas pelo painel MCP.",
            assumptions=(),
            steps=("Criar a placa.", "Criar o eixo."),
            message="Plano MCP do smoke grafico.",
            tool_calls=(
                PlannedToolCall(
                    call_id="panel-plan-plate",
                    name="cad.create_box",
                    arguments={
                        "length": 20,
                        "width": 8,
                        "height": 2,
                        "name": "PlanPlate",
                    },
                    risk="modify",
                    requires_confirmation=True,
                ),
                PlannedToolCall(
                    call_id="panel-plan-shaft",
                    name="cad.create_cylinder",
                    arguments={
                        "diameter": 3,
                        "height": 12,
                        "name": "PlanShaft",
                    },
                    risk="modify",
                    requires_confirmation=True,
                ),
            ),
        )
        composite = CompositeValidatedPlan.build(
            proposal, base_state, get_tool_registry()
        )
        submitted = run_bridge_request(
            client,
            BridgePlanSubmitRequest(
                request_id=uuid4(), plan=composite, source="mcp"
            ),
        )
        assert submitted.result["status"] == CompositePlanStatus.AWAITING_APPROVAL
        wait_for_ui(
            lambda: confirmation.isVisible()
            and "Plano com 2 etapas" in confirmation_text.text()
        )
        approve_button.click()
        wait_for_ui(lambda: len(App.ActiveDocument.Objects) == 4)
        status = run_bridge_request(
            client,
            BridgePlanStatusRequest(
                request_id=uuid4(), plan_id=composite.plan_id, source="mcp"
            ),
        )
        assert status.result["status"] == CompositePlanStatus.COMPLETED
        assert status.result["completed_calls"] == 2

        labels = {item.Label for item in App.ActiveDocument.Objects}
        assert labels == {"PanelBase", "AutoPin", "PlanPlate", "PlanShaft"}
        assert main_window.grab().save(str(screenshot_path), "PNG")
        assert screenshot_path.stat().st_size > 0
        assert "DeepSeek" not in dock.windowTitle()

        App.closeDocument(App.ActiveDocument.Name)
        result_path.write_text("FREECAD_GUI_SMOKE_OK", encoding="utf-8")
        QtWidgets.QApplication.exit(0)
    except Exception:
        result_path.write_text(
            "FREECAD_GUI_SMOKE_FAILED\n" + traceback.format_exc(),
            encoding="utf-8",
        )
        traceback.print_exc()
        QtWidgets.QApplication.exit(1)


QtCore.QTimer.singleShot(1500, inspect)

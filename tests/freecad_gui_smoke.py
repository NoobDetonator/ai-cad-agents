from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import sys
import traceback
import time
from uuid import uuid4


project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(project_root / "src"))

from aicad.bridge.protocol import (
    BridgePlanCancelRequest,
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
from aicad.runtime import get_tool_registry


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


def inspect() -> None:
    try:
        for document_name in list(App.listDocuments()):
            App.closeDocument(document_name)

        assert "AICadWorkbench" in Gui.listWorkbenches()
        Gui.activateWorkbench("AICadWorkbench")
        QtWidgets.QApplication.processEvents()

        main_window = Gui.getMainWindow()
        dock = main_window.findChild(QtWidgets.QDockWidget, "AICadChatDock")
        assert dock is not None and dock.isVisible()
        prompt = dock.findChild(QtWidgets.QPlainTextEdit, "AICadPrompt")
        send = dock.findChild(QtWidgets.QPushButton, "AICadSend")
        apply_button = dock.findChild(QtWidgets.QPushButton, "AICadApply")
        history = dock.findChild(QtWidgets.QTextBrowser, "AICadHistory")
        configure_key = dock.findChild(
            QtWidgets.QPushButton,
            "AICadConfigureApiKey",
        )
        remove_key = dock.findChild(QtWidgets.QPushButton, "AICadRemoveApiKey")
        cancel_ai = dock.findChild(QtWidgets.QPushButton, "AICadCancelAi")
        use_deepseek = dock.findChild(QtWidgets.QCheckBox, "AICadUseDeepSeek")
        assert all(
            widget is not None
            for widget in (
                prompt,
                send,
                apply_button,
                history,
                configure_key,
                remove_key,
                cancel_ai,
                use_deepseek,
            )
        )
        assert use_deepseek.isChecked() is False
        assert cancel_ai.isVisible() is False
        session = default_session_store().load()
        bridge_client = TcpBridgeClient(session.endpoint)
        summary_request = BridgeRequest(
            request_id=uuid4(),
            tool_name="cad.get_document_summary",
            arguments={},
            source="mcp",
        )
        summary_response = run_bridge_request(bridge_client, summary_request)
        assert summary_response.status is BridgeResponseStatus.COMPLETED
        assert summary_response.result["active"] is False
        context_request = BridgeRequest(
            request_id=uuid4(),
            tool_name="cad.get_context_snapshot",
            arguments={
                "detail_level": "work",
                "max_objects": 25,
                "cursor": 0,
            },
            source="mcp",
        )
        context_response = run_bridge_request(bridge_client, context_request)
        assert context_response.status is BridgeResponseStatus.COMPLETED
        assert context_response.result["active"] is False

        prompt.setPlainText("resumo")
        send.click()
        QtWidgets.QApplication.processEvents()
        assert "Nenhum documento CAD está ativo" in history.toPlainText()

        prompt.setPlainText("caixa 10 x 20 x 30 nome GuiSmokeBox")
        send.click()
        QtWidgets.QApplication.processEvents()
        assert App.ActiveDocument is None
        assert apply_button.isVisible()
        apply_button.click()
        QtWidgets.QApplication.processEvents()
        assert App.ActiveDocument is not None
        assert len(App.ActiveDocument.Objects) == 1
        assert App.ActiveDocument.UndoCount == 1
        assert "criada e validada" in history.toPlainText()
        assert main_window.grab().save(str(screenshot_path), "PNG")

        Gui.Selection.addSelection(App.ActiveDocument.Objects[0])
        prompt.setPlainText("seleção")
        send.click()
        QtWidgets.QApplication.processEvents()
        assert "Seleção atual (1): GuiSmokeBox" in history.toPlainText()
        prompt.setPlainText("contexto")
        send.click()
        QtWidgets.QApplication.processEvents()
        assert "1 selecionados" in history.toPlainText()
        assert "recentes: GuiSmokeBox" in history.toPlainText()
        Gui.Selection.clearSelection()

        prompt.setPlainText("validar")
        send.click()
        QtWidgets.QApplication.processEvents()
        assert "validado sem erros" in history.toPlainText()

        prompt.setPlainText("desfazer")
        send.click()
        QtWidgets.QApplication.processEvents()
        assert len(App.ActiveDocument.Objects) == 1
        apply_button.click()
        QtWidgets.QApplication.processEvents()
        assert len(App.ActiveDocument.Objects) == 0
        assert "foi desfeita" in history.toPlainText()

        prompt.setPlainText("cilindro 30 x 60 nome GuiSmokeCylinder")
        send.click()
        QtWidgets.QApplication.processEvents()
        assert len(App.ActiveDocument.Objects) == 0
        assert apply_button.isVisible()
        apply_button.click()
        wait_for_ui(lambda: len(App.ActiveDocument.Objects) == 1)
        cylinder = App.ActiveDocument.Objects[0]
        assert cylinder.TypeId == "Part::Cylinder"
        assert cylinder.Label == "GuiSmokeCylinder"
        assert cylinder.Radius.Value == 15
        assert cylinder.Height.Value == 60
        assert "Cilindro GuiSmokeCylinder criado" in history.toPlainText()

        prompt.setPlainText("desfazer")
        send.click()
        QtWidgets.QApplication.processEvents()
        assert apply_button.isVisible()
        apply_button.click()
        wait_for_ui(lambda: len(App.ActiveDocument.Objects) == 0)
        assert "foi desfeita" in history.toPlainText()

        mcp_box_request = BridgeRequest(
            request_id=uuid4(),
            tool_name="cad.create_box",
            arguments={
                "length": 7,
                "width": 8,
                "height": 9,
                "name": "McpSmokeBox",
            },
            source="mcp",
        )
        pending_response = run_bridge_request(bridge_client, mcp_box_request)
        assert pending_response.status is BridgeResponseStatus.PENDING_CONFIRMATION
        assert len(App.ActiveDocument.Objects) == 0
        wait_for_ui(
            lambda: apply_button.isVisible()
            and "cad.create_box" in history.toPlainText()
        )
        apply_button.click()
        wait_for_ui(lambda: len(App.ActiveDocument.Objects) == 1)
        assert App.ActiveDocument.Objects[0].Label == "McpSmokeBox"

        completed_response = run_bridge_request(bridge_client, mcp_box_request)
        assert completed_response.status is BridgeResponseStatus.COMPLETED
        assert completed_response.result["label"] == "McpSmokeBox"
        assert len(App.ActiveDocument.Objects) == 1
        assert main_window.grab().save(str(screenshot_path), "PNG")

        prompt.setPlainText("desfazer")
        send.click()
        QtWidgets.QApplication.processEvents()
        assert apply_button.isVisible()
        apply_button.click()
        wait_for_ui(lambda: len(App.ActiveDocument.Objects) == 0)

        plan_context_request = BridgeRequest(
            request_id=uuid4(),
            tool_name="cad.get_context_snapshot",
            arguments={
                "detail_level": "work",
                "max_objects": 25,
                "cursor": 0,
            },
            source="mcp",
        )
        plan_context = run_bridge_request(bridge_client, plan_context_request)
        base_state = DocumentStateToken.model_validate(
            plan_context.result["state_token"]
        )
        proposal = OrchestrationPlan(
            intention="Criar base e pino pelo MCP.",
            assumptions=(),
            steps=("Criar a base.", "Criar o pino."),
            message="Plano gráfico MCP.",
            tool_calls=(
                PlannedToolCall(
                    call_id="gui-mcp-box",
                    name="cad.create_box",
                    arguments={
                        "length": 12,
                        "width": 10,
                        "height": 4,
                        "name": "McpPlanBase",
                    },
                    risk="modify",
                    requires_confirmation=True,
                ),
                PlannedToolCall(
                    call_id="gui-mcp-pin",
                    name="cad.create_cylinder",
                    arguments={
                        "diameter": 4,
                        "height": 8,
                        "name": "McpPlanPin",
                    },
                    risk="modify",
                    requires_confirmation=True,
                ),
            ),
        )
        composite = CompositeValidatedPlan.build(
            proposal,
            base_state,
            get_tool_registry(),
        )
        submit_plan = BridgePlanSubmitRequest(
            request_id=uuid4(),
            plan=composite,
            source="mcp",
        )
        submitted = run_bridge_request(bridge_client, submit_plan)
        assert submitted.status is BridgeResponseStatus.COMPLETED
        assert submitted.result["status"] == CompositePlanStatus.AWAITING_APPROVAL
        assert len(App.ActiveDocument.Objects) == 0
        wait_for_ui(
            lambda: apply_button.isVisible()
            and "Plano composto recebido pelo MCP" in history.toPlainText()
        )
        apply_button.click()
        wait_for_ui(lambda: len(App.ActiveDocument.Objects) == 2)
        assert {obj.Label for obj in App.ActiveDocument.Objects} == {
            "McpPlanBase",
            "McpPlanPin",
        }
        plan_status = run_bridge_request(
            bridge_client,
            BridgePlanStatusRequest(
                request_id=uuid4(),
                plan_id=composite.plan_id,
                source="mcp",
            ),
        )
        assert plan_status.result["status"] == CompositePlanStatus.COMPLETED
        assert plan_status.result["completed_calls"] == 2
        assert main_window.grab().save(str(screenshot_path), "PNG")

        for _ in range(2):
            prompt.setPlainText("desfazer")
            send.click()
            QtWidgets.QApplication.processEvents()
            assert apply_button.isVisible()
            apply_button.click()
            QtWidgets.QApplication.processEvents()
        wait_for_ui(lambda: len(App.ActiveDocument.Objects) == 0)

        cancelled_plan = CompositeValidatedPlan.build(
            proposal,
            DocumentStateToken.model_validate(
                run_bridge_request(
                    bridge_client,
                    plan_context_request.model_copy(update={"request_id": uuid4()}),
                ).result["state_token"]
            ),
            get_tool_registry(),
        )
        cancelled_submit = BridgePlanSubmitRequest(
            request_id=uuid4(),
            plan=cancelled_plan,
            source="mcp",
        )
        run_bridge_request(bridge_client, cancelled_submit)
        wait_for_ui(lambda: apply_button.isVisible())
        cancelled = run_bridge_request(
            bridge_client,
            BridgePlanCancelRequest(
                request_id=uuid4(),
                plan_id=cancelled_plan.plan_id,
                source="mcp",
            ),
        )
        assert cancelled.result["status"] == CompositePlanStatus.CANCELLED
        apply_button.click()
        QtWidgets.QApplication.processEvents()
        assert len(App.ActiveDocument.Objects) == 0
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

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

from aicad.bridge.protocol import BridgeRequest, BridgeResponseStatus

from aicad.bridge.session import default_session_store
from aicad.bridge.transport import TcpBridgeClient


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


def run_bridge_request(client: TcpBridgeClient, request: BridgeRequest):
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
                use_deepseek,
            )
        )
        assert use_deepseek.isChecked() is False
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

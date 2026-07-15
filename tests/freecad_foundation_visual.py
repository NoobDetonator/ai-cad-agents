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

from aicad.bridge.protocol import BridgeRequest, BridgeResponseStatus
from aicad.bridge.session import default_session_store
from aicad.bridge.transport import TcpBridgeClient

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets


result_path = Path(os.environ["AICAD_FOUNDATION_VISUAL_RESULT"])
screenshot_path = Path(os.environ["AICAD_FOUNDATION_VISUAL_SCREENSHOT"])


def wait_for_ui(predicate, timeout: float = 12.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QtWidgets.QApplication.processEvents()
        if predicate():
            return
        time.sleep(0.02)
    assert predicate(), "The FreeCAD UI did not reach the expected state."


def send(client: TcpBridgeClient, request: BridgeRequest):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(client.request, request)
        wait_for_ui(future.done)
        return future.result(timeout=1)


def execute(
    client: TcpBridgeClient,
    name: str,
    arguments: dict[str, object],
):
    request = BridgeRequest(
        request_id=uuid4(),
        tool_name=name,
        arguments=arguments,
        source="mcp",
    )
    response = send(client, request)
    if response.status is BridgeResponseStatus.PENDING_CONFIRMATION:
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            QtWidgets.QApplication.processEvents()
            time.sleep(0.03)
            response = send(client, request)
            if response.status is not BridgeResponseStatus.PENDING_CONFIRMATION:
                break
    assert response.status is BridgeResponseStatus.COMPLETED, response
    return response.result


def inspect() -> None:
    try:
        for document_name in list(App.listDocuments()):
            App.closeDocument(document_name)

        Gui.activateWorkbench("AICadWorkbench")
        QtWidgets.QApplication.processEvents()
        main_window = Gui.getMainWindow()
        dock = main_window.findChild(QtWidgets.QDockWidget, "AICadChatDock")
        assert dock is not None and dock.isVisible()
        automatic = dock.findChild(QtWidgets.QCheckBox, "AICadQuickTestMode")
        history = dock.findChild(QtWidgets.QTextBrowser, "AICadHistory")
        assert automatic is not None and automatic.isChecked()
        assert history is not None

        client = TcpBridgeClient(default_session_store().load().endpoint)
        outputs: dict[str, object] = {}
        outputs["document"] = execute(
            client,
            "cad.new_document",
            {"name": "FoundationVisualReview"},
        )
        outputs["cone"] = execute(
            client,
            "cad.create_cone",
            {
                "bottom_diameter": 32,
                "top_diameter": 10,
                "height": 42,
                "name": "VisualCone",
            },
        )
        outputs["sphere"] = execute(
            client,
            "cad.create_sphere",
            {"diameter": 24, "name": "VisualSphere"},
        )
        outputs["sphere_translate"] = execute(
            client,
            "cad.translate_object",
            {"object": "VisualSphere", "dx": 52, "dz": 12},
        )
        outputs["torus"] = execute(
            client,
            "cad.create_torus",
            {
                "major_diameter": 44,
                "tube_diameter": 9,
                "name": "VisualTorus",
            },
        )
        outputs["torus_translate"] = execute(
            client,
            "cad.translate_object",
            {"object": "VisualTorus", "dx": 105, "dz": 6},
        )
        outputs["base"] = execute(
            client,
            "cad.create_box",
            {"length": 20, "width": 10, "height": 6, "name": "VisualBase"},
        )
        outputs["base_translate"] = execute(
            client,
            "cad.translate_object",
            {"object": "VisualBase", "dx": 20, "dy": 52},
        )
        outputs["copy"] = execute(
            client,
            "cad.duplicate_object",
            {
                "object": "VisualBase",
                "name": "VisualCopy",
                "offset_x": 45,
            },
        )
        outputs["copy_rotate"] = execute(
            client,
            "cad.rotate_object",
            {
                "object": "VisualCopy",
                "axis": "z",
                "angle": 90,
                "pivot": "object_center",
            },
        )
        outputs["distance"] = execute(
            client,
            "cad.measure_distance",
            {"left": "VisualBase", "right": "VisualCopy"},
        )

        execute(
            client,
            "cad.duplicate_object",
            {"object": "VisualCopy", "name": "DeleteProbe", "offset_x": 30},
        )
        outputs["delete"] = execute(
            client,
            "cad.delete_object",
            {"object": "DeleteProbe"},
        )
        assert App.ActiveDocument.getObject("DeleteProbe") is None
        outputs["delete_undo"] = execute(client, "cad.undo", {})
        assert App.ActiveDocument.getObject("DeleteProbe") is not None
        execute(client, "cad.delete_object", {"object": "DeleteProbe"})

        validation = execute(client, "cad.validate_document", {})
        assert validation["valid"] is True
        expected_labels = {
            "VisualCone",
            "VisualSphere",
            "VisualTorus",
            "VisualBase",
            "VisualCopy",
        }
        assert {item.Label for item in App.ActiveDocument.Objects} == expected_labels

        colors = {
            "VisualCone": (0.95, 0.55, 0.15),
            "VisualSphere": (0.25, 0.65, 0.95),
            "VisualTorus": (0.35, 0.85, 0.45),
            "VisualBase": (0.85, 0.35, 0.35),
            "VisualCopy": (0.75, 0.45, 0.90),
        }
        for name, color in colors.items():
            App.ActiveDocument.getObject(name).ViewObject.ShapeColor = color

        view = Gui.activeDocument().activeView()
        view.viewAxonometric()
        view.fitAll()
        QtWidgets.QApplication.processEvents()
        wait_for_ui(lambda: "aprovada automaticamente" in history.toPlainText())
        assert main_window.grab().save(str(screenshot_path), "PNG")

        distance = outputs["distance"]
        report = {
            "status": "FREECAD_FOUNDATION_VISUAL_OK",
            "automatic_approval_checked": automatic.isChecked(),
            "objects": sorted(expected_labels),
            "minimum_distance_mm": distance["minimum_distance_mm"],
            "center_distance_mm": distance["center_distance_mm"],
            "document_valid": validation["valid"],
            "deleted_and_undone": outputs["delete"]["deleted"]
            and outputs["delete_undo"]["undone"],
            "screenshot": str(screenshot_path),
            "outputs": outputs,
        }
        result_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        main_window.raise_()
        main_window.activateWindow()
    except Exception:
        result_path.write_text(
            json.dumps(
                {
                    "status": "FREECAD_FOUNDATION_VISUAL_FAILED",
                    "error": traceback.format_exc(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        traceback.print_exc()


QtCore.QTimer.singleShot(1800, inspect)

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


result_path = Path(os.environ["AICAD_SKETCH_VISUAL_RESULT"])
screenshot_path = Path(os.environ["AICAD_SKETCH_VISUAL_SCREENSHOT"])


def wait_for_ui(predicate, timeout: float = 15.0) -> None:
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


def execute(client: TcpBridgeClient, name: str, arguments: dict[str, object]):
    request = BridgeRequest(
        request_id=uuid4(), tool_name=name, arguments=arguments, source="mcp"
    )
    response = send(client, request)
    if response.status is BridgeResponseStatus.PENDING_CONFIRMATION:
        deadline = time.monotonic() + 15
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
        execute(client, "cad.new_document", {"name": "SketchEnvironmentReview"})

        execute(client, "cad.create_empty_sketch", {"name": "FoundationProfile"})
        execute(
            client,
            "cad.add_sketch_slot",
            {
                "sketch": "FoundationProfile",
                "start_x": -45,
                "start_y": 0,
                "end_x": 45,
                "end_y": 0,
                "width": 44,
            },
        )
        pad = execute(
            client,
            "cad.pad_sketch",
            {"sketch": "FoundationProfile", "length": 8, "name": "SketchFoundation"},
        )

        execute(
            client,
            "cad.create_empty_sketch",
            {"plane": "xy", "offset": 10, "name": "GeometryGallery"},
        )
        execute(
            client,
            "cad.add_sketch_line",
            {
                "sketch": "GeometryGallery",
                "x1": -88,
                "y1": 0,
                "x2": 88,
                "y2": 0,
                "construction": True,
            },
        )
        execute(
            client,
            "cad.add_sketch_rectangle",
            {
                "sketch": "GeometryGallery",
                "x": -78,
                "y": -24,
                "width": 28,
                "height": 19,
                "rotation": 8,
            },
        )
        execute(
            client,
            "cad.add_sketch_circle",
            {
                "sketch": "GeometryGallery",
                "center_x": -30,
                "center_y": -14,
                "radius": 10,
            },
        )
        execute(
            client,
            "cad.add_sketch_dimensional_constraint",
            {
                "sketch": "GeometryGallery",
                "constraint_type": "diameter",
                "geometry": 5,
                "value": 20,
            },
        )
        execute(
            client,
            "cad.add_sketch_ellipse",
            {
                "sketch": "GeometryGallery",
                "center_x": 5,
                "center_y": -14,
                "major_radius": 15,
                "minor_radius": 7,
                "rotation": 25,
            },
        )
        execute(
            client,
            "cad.add_sketch_regular_polygon",
            {
                "sketch": "GeometryGallery",
                "center_x": 48,
                "center_y": -14,
                "radius": 13,
                "sides": 6,
                "rotation": 30,
            },
        )
        execute(
            client,
            "cad.add_sketch_arc",
            {
                "sketch": "GeometryGallery",
                "center_x": -52,
                "center_y": 23,
                "radius": 13,
                "start_angle": 10,
                "end_angle": 275,
            },
        )
        execute(
            client,
            "cad.add_sketch_polyline",
            {
                "sketch": "GeometryGallery",
                "points": ["-5,14", "7,29", "20,14", "7,20"],
                "closed": True,
            },
        )
        execute(
            client,
            "cad.add_sketch_slot",
            {
                "sketch": "GeometryGallery",
                "start_x": 42,
                "start_y": 22,
                "end_x": 70,
                "end_y": 22,
                "width": 12,
            },
        )

        execute(
            client,
            "cad.create_empty_sketch",
            {"plane": "xy", "offset": 30, "name": "EditGallery"},
        )
        first = execute(
            client,
            "cad.add_sketch_rectangle",
            {
                "sketch": "EditGallery",
                "x": 12,
                "y": -14,
                "width": 30,
                "height": 28,
            },
        )
        execute(
            client,
            "cad.mirror_sketch_geometry",
            {
                "sketch": "EditGallery",
                "geometry_indices": first["added_geometry"],
                "axis": "vertical",
            },
        )
        execute(
            client,
            "cad.fillet_sketch_corner",
            {
                "sketch": "EditGallery",
                "first_geometry": 0,
                "second_geometry": 1,
                "first_x": 41,
                "first_y": -14,
                "second_x": 42,
                "second_y": -13,
                "radius": 5,
            },
        )
        execute(
            client,
            "cad.copy_sketch_geometry",
            {
                "sketch": "EditGallery",
                "geometry_indices": [0, 1, 2, 3, 8],
                "dx": 0,
                "dy": 43,
            },
        )

        gallery_info = execute(client, "cad.get_sketch_info", {"sketch": "GeometryGallery"})
        edit_info = execute(client, "cad.get_sketch_info", {"sketch": "EditGallery"})
        validation = execute(client, "cad.validate_document", {})
        assert validation["valid"] is True
        assert gallery_info["geometry_count"] >= 20
        assert edit_info["geometry_count"] >= 14
        assert edit_info["closed_wire_count"] == 3
        assert edit_info["open_wire_count"] == 0

        document = App.ActiveDocument
        document.getObject("SketchFoundation").ViewObject.ShapeColor = (0.18, 0.48, 0.88)
        document.getObject("FoundationProfile").ViewObject.Visibility = False
        document.getObject("GeometryGallery").ViewObject.LineColor = (1.0, 0.72, 0.12)
        document.getObject("GeometryGallery").ViewObject.PointColor = (1.0, 0.25, 0.15)
        document.getObject("GeometryGallery").ViewObject.LineWidth = 4.0
        document.getObject("EditGallery").ViewObject.LineColor = (0.35, 1.0, 0.48)
        document.getObject("EditGallery").ViewObject.PointColor = (0.9, 0.2, 1.0)
        document.getObject("EditGallery").ViewObject.LineWidth = 4.0

        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(document.getObject("GeometryGallery"))
        view = Gui.activeDocument().activeView()
        view.viewAxonometric()
        view.fitAll()
        QtWidgets.QApplication.processEvents()
        wait_for_ui(lambda: "aprovada automaticamente" in history.toPlainText())
        assert main_window.grab().save(str(screenshot_path), "PNG")

        result_path.write_text(
            json.dumps(
                {
                    "status": "FREECAD_SKETCH_VISUAL_OK",
                    "automatic_approval_checked": automatic.isChecked(),
                    "document_valid": validation["valid"],
                    "pad_volume_mm3": pad["volume_mm3"],
                    "gallery_geometry_count": gallery_info["geometry_count"],
                    "gallery_constraint_count": gallery_info["constraint_count"],
                    "edit_geometry_count": edit_info["geometry_count"],
                    "edit_closed_wire_count": edit_info["closed_wire_count"],
                    "edit_open_wire_count": edit_info["open_wire_count"],
                    "screenshot": str(screenshot_path),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        main_window.raise_()
        main_window.activateWindow()
    except Exception:
        result_path.write_text(
            json.dumps(
                {
                    "status": "FREECAD_SKETCH_VISUAL_FAILED",
                    "error": traceback.format_exc(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        traceback.print_exc()


QtCore.QTimer.singleShot(1800, inspect)

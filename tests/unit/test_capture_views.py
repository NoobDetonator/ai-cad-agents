from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from aicad.adapters.freecad.context import ContextReadsMixin
from aicad.core.tool_registry import ToolInputError, build_default_registry


class FakeActiveView:
    def __init__(self, *, fail_after: int | None = None) -> None:
        self.camera = "original-camera"
        self.saved_cameras: list[str] = []
        self.fail_after = fail_after
        self.animation_enabled = True

    def getCamera(self) -> str:
        return self.camera

    def setCamera(self, camera: str) -> None:
        self.camera = camera

    def isAnimationEnabled(self) -> bool:
        return self.animation_enabled

    def setAnimationEnabled(self, enabled: bool) -> None:
        self.animation_enabled = enabled

    def _orient(self, name: str) -> None:
        self.camera = name

    def viewAxonometric(self) -> None:
        self._orient("isometric")

    def viewTop(self) -> None:
        self._orient("top")

    def viewBottom(self) -> None:
        self._orient("bottom")

    def viewFront(self) -> None:
        self._orient("front")

    def viewRear(self) -> None:
        self._orient("rear")

    def viewLeft(self) -> None:
        self._orient("left")

    def viewRight(self) -> None:
        self._orient("right")

    def fitAll(self) -> None:
        self.camera += ":fit"

    def redraw(self) -> None:
        pass

    def saveImage(self, path: str, width: int, height: int, mode: str) -> None:
        del width, height, mode
        if self.fail_after is not None and len(self.saved_cameras) >= self.fail_after:
            raise RuntimeError("Synthetic capture failure.")
        self.saved_cameras.append(self.camera)
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + self.camera.encode("utf-8"))


def install_fake_gui(monkeypatch: pytest.MonkeyPatch, view: FakeActiveView) -> None:
    gui_document = SimpleNamespace(activeView=lambda: view)
    monkeypatch.setitem(
        sys.modules,
        "FreeCADGui",
        SimpleNamespace(activeDocument=lambda: gui_document, updateGui=lambda: None),
    )


def test_capture_views_are_independent_and_restore_camera(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AICAD_VISUAL_CACHE", str(tmp_path))
    view = FakeActiveView()
    install_fake_gui(monkeypatch, view)

    result = ContextReadsMixin().capture_views(
        ["isometric", "top", "current"],
        width=640,
        height=480,
        fit=True,
    )

    assert result["views"] == ["isometric", "top", "current"]
    assert result["count"] == 3
    assert result["camera_restored"] is True
    assert view.saved_cameras == [
        "isometric:fit",
        "top:fit",
        "original-camera:fit",
    ]
    assert view.camera == "original-camera"
    assert view.animation_enabled is True
    assert len(list(tmp_path.glob("*.png"))) == 3


def test_single_capture_now_restores_camera(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AICAD_VISUAL_CACHE", str(tmp_path))
    view = FakeActiveView()
    install_fake_gui(monkeypatch, view)

    result = ContextReadsMixin().capture_view(view="right", fit=True)

    assert result["camera_restored"] is True
    assert view.saved_cameras == ["right:fit"]
    assert view.camera == "original-camera"
    assert view.animation_enabled is True


def test_capture_batch_failure_removes_partial_images_and_restores_camera(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AICAD_VISUAL_CACHE", str(tmp_path))
    view = FakeActiveView(fail_after=1)
    install_fake_gui(monkeypatch, view)

    with pytest.raises(RuntimeError, match="Synthetic capture failure"):
        ContextReadsMixin().capture_views(["front", "top"])

    assert view.camera == "original-camera"
    assert view.animation_enabled is True
    assert list(tmp_path.glob("*.png")) == []


def test_capture_views_schema_rejects_duplicate_or_unknown_views() -> None:
    registry = build_default_registry()

    with pytest.raises(ToolInputError, match="unique"):
        registry.validate_arguments(
            "cad.capture_views",
            {"views": ["top", "top"]},
        )
    with pytest.raises(ToolInputError, match="allowed values"):
        registry.validate_arguments(
            "cad.capture_views",
            {"views": ["perspective"]},
        )


def test_capture_overlays_are_hidden_and_restored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeViewer:
        navi_cube_enabled = True

        def isEnabledNaviCube(self) -> bool:
            return self.navi_cube_enabled

        def setEnabledNaviCube(self, enabled: bool) -> None:
            self.navi_cube_enabled = enabled

    class FakeOverlayView:
        axis_cross_enabled = True
        corner_cross_enabled = True
        viewer = FakeViewer()

        def getViewer(self) -> FakeViewer:
            return self.viewer

        def hasAxisCross(self) -> bool:
            return self.axis_cross_enabled

        def setAxisCross(self, enabled: bool) -> None:
            self.axis_cross_enabled = enabled

        def isCornerCrossVisible(self) -> bool:
            return self.corner_cross_enabled

        def setCornerCrossVisible(self, enabled: bool) -> None:
            self.corner_cross_enabled = enabled

        def redraw(self) -> None:
            pass

    monkeypatch.setitem(
        sys.modules,
        "FreeCADGui",
        SimpleNamespace(updateGui=lambda: None),
    )
    view = FakeOverlayView()

    state = ContextReadsMixin._hide_capture_overlays(view)

    assert view.viewer.navi_cube_enabled is False
    assert view.axis_cross_enabled is False
    assert view.corner_cross_enabled is False
    ContextReadsMixin._restore_capture_overlays(view, state)
    assert view.viewer.navi_cube_enabled is True
    assert view.axis_cross_enabled is True
    assert view.corner_cross_enabled is True


def test_capture_overlay_failure_restores_already_changed_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeViewer:
        enabled = True

        def isEnabledNaviCube(self) -> bool:
            return self.enabled

        def setEnabledNaviCube(self, enabled: bool) -> None:
            self.enabled = enabled

    class FailingOverlayView:
        viewer = FakeViewer()

        def getViewer(self) -> FakeViewer:
            return self.viewer

        def hasAxisCross(self) -> bool:
            return True

        def setAxisCross(self, enabled: bool) -> None:
            if not enabled:
                raise RuntimeError("Synthetic overlay failure.")

        def redraw(self) -> None:
            pass

    monkeypatch.setitem(
        sys.modules,
        "FreeCADGui",
        SimpleNamespace(updateGui=lambda: None),
    )
    view = FailingOverlayView()

    with pytest.raises(RuntimeError, match="Synthetic overlay failure"):
        ContextReadsMixin._hide_capture_overlays(view)

    assert view.viewer.enabled is True

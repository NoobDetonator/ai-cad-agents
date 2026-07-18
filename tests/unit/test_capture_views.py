from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from talos.adapters.freecad.context import ContextReadsMixin
from talos.core.tool_registry import ToolInputError, build_default_registry


class FakeActiveView:
    def __init__(self, *, fail_after: int | None = None) -> None:
        self.camera = "original-camera"
        self.saved_cameras: list[str] = []
        self.fail_after = fail_after
        self.animation_enabled = True
        self.clipping_plane = False
        self.clipping_calls: list[tuple[object, ...]] = []

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

    def hasClippingPlane(self) -> bool:
        return self.clipping_plane

    def toggleClippingPlane(self, *arguments: object) -> None:
        self.clipping_calls.append(arguments)
        self.clipping_plane = bool(arguments[0])

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
    monkeypatch.setenv("TALOS_VISUAL_CACHE", str(tmp_path))
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
    monkeypatch.setenv("TALOS_VISUAL_CACHE", str(tmp_path))
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
    monkeypatch.setenv("TALOS_VISUAL_CACHE", str(tmp_path))
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


def test_framebuffer_capture_waits_for_two_equal_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeImage:
        def __init__(self, content: str) -> None:
            self.content = content

        def isNull(self) -> bool:
            return False

        def width(self) -> int:
            return 640

        def height(self) -> int:
            return 480

        def __eq__(self, other: object) -> bool:
            return isinstance(other, FakeImage) and self.content == other.content

    class FakeViewer:
        def __init__(self) -> None:
            self.frames = iter(
                [
                    FakeImage("stale"),
                    FakeImage("rendering"),
                    FakeImage("stable"),
                    FakeImage("stable"),
                ]
            )
            self.repaint_count = 0
            self.grab_count = 0

        def repaint(self) -> None:
            self.repaint_count += 1

        def grabFramebuffer(self) -> FakeImage:
            self.grab_count += 1
            return next(self.frames)

    class FakeView:
        def __init__(self) -> None:
            self.redraw_count = 0

        def redraw(self) -> None:
            self.redraw_count += 1

    monkeypatch.setitem(
        sys.modules,
        "FreeCADGui",
        SimpleNamespace(updateGui=lambda: None),
    )
    viewer = FakeViewer()
    view = FakeView()

    result = ContextReadsMixin._grab_stable_framebuffer(view, viewer)

    assert result.content == "stable"
    assert viewer.grab_count == 4
    assert viewer.repaint_count == 4
    assert view.redraw_count == 4


def test_framebuffer_capture_rejects_unstable_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeImage:
        def __init__(self, content: int) -> None:
            self.content = content

        def isNull(self) -> bool:
            return False

        def width(self) -> int:
            return 640

        def height(self) -> int:
            return 480

        def __eq__(self, other: object) -> bool:
            return isinstance(other, FakeImage) and self.content == other.content

    class FakeViewer:
        def __init__(self) -> None:
            self.index = 0

        def grabFramebuffer(self) -> FakeImage:
            self.index += 1
            return FakeImage(self.index)

    class FakeView:
        def redraw(self) -> None:
            pass

    monkeypatch.setitem(
        sys.modules,
        "FreeCADGui",
        SimpleNamespace(updateGui=lambda: None),
    )

    with pytest.raises(RuntimeError, match="did not stabilize"):
        ContextReadsMixin._grab_stable_framebuffer(FakeView(), FakeViewer())


class FakeVector(tuple):
    def __new__(cls, x: float, y: float, z: float):
        return super().__new__(cls, (float(x), float(y), float(z)))


class FakeMatrix(tuple):
    def __new__(cls, *values: float):
        return super().__new__(cls, tuple(float(value) for value in values))


class FakeRotation:
    def __init__(self, source=None, target=None) -> None:
        if target is None and isinstance(source, FakeMatrix):
            self.matrix = tuple(source)
            self.source = None
            self.target = None
        else:
            self.matrix = None
            self.source = source
            self.target = target


class FakePlacement:
    def __init__(self, point: FakeVector, rotation: FakeRotation) -> None:
        self.point = point
        self.rotation = rotation


FAKE_APP = SimpleNamespace(
    Vector=FakeVector,
    Rotation=FakeRotation,
    Matrix=FakeMatrix,
    Placement=FakePlacement,
)


def test_section_capture_applies_plane_and_restores_clipping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TALOS_VISUAL_CACHE", str(tmp_path))
    view = FakeActiveView()
    install_fake_gui(monkeypatch, view)
    context = ContextReadsMixin()
    monkeypatch.setattr(context, "_modules", lambda: (FAKE_APP, None), raising=False)

    result = context.capture_section_view(
        plane="xz",
        offset=12,
        flip=True,
        view="right",
        fit=True,
    )

    placement = view.clipping_calls[0][3]
    assert isinstance(placement, FakePlacement)
    assert placement.point == (0.0, 12.0, 0.0)
    assert placement.rotation.source == (0.0, 0.0, 1.0)
    assert placement.rotation.target == (0.0, -1.0, 0.0)
    assert view.clipping_calls[-1] == (0,)
    assert view.clipping_plane is False
    assert view.camera == "original-camera"
    assert result["plane"] == "xz"
    assert result["normal"] == [0.0, -1.0, 0.0]
    assert result["kept_side"] == "positive_normal"
    assert result["capped"] is False
    assert result["clipping_restored"] is True


def test_section_capture_camera_faces_the_cut(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TALOS_VISUAL_CACHE", str(tmp_path))

    class DirectionalView(FakeActiveView):
        def __init__(self) -> None:
            super().__init__()
            self.camera_matrices: list[tuple[float, ...]] = []

        def setCameraOrientation(self, rotation) -> None:
            self.camera_matrices.append(rotation.matrix)
            self.camera = "cut-facing"

    view = DirectionalView()
    install_fake_gui(monkeypatch, view)
    context = ContextReadsMixin()
    monkeypatch.setattr(context, "_modules", lambda: (FAKE_APP, None), raising=False)

    result = context.capture_section_view(plane="xz", offset=0)

    # Sem flip o corte descarta o lado +Y: a coluna Z da matriz (eixo da
    # camera apontando do modelo para ela) deve ter componente Y positivo.
    matrix = view.camera_matrices[0]
    assert matrix[6] > 0, matrix
    assert result["camera_faces_cut"] is True
    assert result["view"] == "isometric"
    assert view.camera == "original-camera"
    assert view.animation_enabled is True

    flipped = context.capture_section_view(plane="xz", offset=0, flip=True)
    assert view.camera_matrices[1][6] < 0, view.camera_matrices
    assert flipped["camera_faces_cut"] is True


def test_section_capture_failure_removes_temporary_clipping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TALOS_VISUAL_CACHE", str(tmp_path))
    view = FakeActiveView(fail_after=0)
    install_fake_gui(monkeypatch, view)
    context = ContextReadsMixin()
    monkeypatch.setattr(context, "_modules", lambda: (FAKE_APP, None), raising=False)

    with pytest.raises(RuntimeError, match="Synthetic capture failure"):
        context.capture_section_view()

    assert view.clipping_plane is False
    assert view.clipping_calls[-1] == (0,)
    assert list(tmp_path.glob("*.png")) == []


def test_section_capture_restore_failure_discards_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingRestoreView(FakeActiveView):
        def toggleClippingPlane(self, *arguments: object) -> None:
            if arguments[0] == 0:
                raise RuntimeError("Synthetic clipping restore failure.")
            super().toggleClippingPlane(*arguments)

    monkeypatch.setenv("TALOS_VISUAL_CACHE", str(tmp_path))
    view = FailingRestoreView()
    install_fake_gui(monkeypatch, view)
    context = ContextReadsMixin()
    monkeypatch.setattr(context, "_modules", lambda: (FAKE_APP, None), raising=False)

    with pytest.raises(RuntimeError, match="clipping state could not be restored"):
        context.capture_section_view()

    assert list(tmp_path.glob("*.png")) == []


def test_section_capture_refuses_existing_clipping_plane(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TALOS_VISUAL_CACHE", str(tmp_path))
    view = FakeActiveView()
    view.clipping_plane = True
    install_fake_gui(monkeypatch, view)
    context = ContextReadsMixin()

    with pytest.raises(RuntimeError, match="already active"):
        context.capture_section_view()

    assert view.clipping_calls == []
    assert view.clipping_plane is True


def test_section_capture_schema_rejects_invalid_plane_or_offset() -> None:
    registry = build_default_registry()

    with pytest.raises(ToolInputError, match="allowed values"):
        registry.validate_arguments(
            "cad.capture_section_view",
            {"plane": "diagonal"},
        )
    with pytest.raises(ToolInputError, match="offset must be a number"):
        registry.validate_arguments(
            "cad.capture_section_view",
            {"offset": True},
        )

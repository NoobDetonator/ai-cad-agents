from importlib import import_module
from pathlib import Path
import runpy
from types import SimpleNamespace


def test_freecad_facing_modules_import_without_freecad_installed() -> None:
    import_module("aicad.adapters.freecad_adapter")
    import_module("aicad.runtime")
    import_module("aicad.ui.talos_panel")
    import_module("aicad.orchestration")
    import_module("aicad.orchestration.plans")
    import_module("aicad.orchestration.plan_service")
    import_module("aicad.orchestration.recipes")
    import_module("aicad.core.tool_results")
    import_module("aicad.core.context")
    import_module("aicad.core.mechanical_tools")
    import_module("aicad.core.tool_selector")
    import_module("aicad.core.visual_cache")
    import_module("aicad.evaluation.benchmark")


def test_freecad_workbench_registration_is_idempotent(monkeypatch) -> None:
    workbenches = {}

    def add_workbench(workbench) -> None:
        name = type(workbench).__name__
        if name in workbenches:
            raise KeyError(f"{name!r} already exists")
        workbenches[name] = workbench

    freecad_gui = SimpleNamespace(
        addWorkbench=add_workbench,
        listWorkbenches=lambda: dict(workbenches),
    )
    monkeypatch.setitem(__import__("sys").modules, "FreeCADGui", freecad_gui)
    init_gui = Path(__file__).resolve().parents[2] / "src" / "freecad" / "AiCad" / "InitGui.py"

    for _ in range(2):
        runpy.run_path(str(init_gui), init_globals={"Workbench": object})

    assert list(workbenches) == ["AICadWorkbench"]

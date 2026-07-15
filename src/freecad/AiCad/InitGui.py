from __future__ import annotations

import os
import sys
from pathlib import Path

import FreeCADGui as Gui


def _project_root(
    path_type=Path,
    environment=os.environ,
    module_search_paths=tuple(sys.path),
):
    configured = environment.get("AICAD_PROJECT_ROOT")
    if configured:
        candidate = path_type(configured).expanduser().resolve()
        if (candidate / "src" / "aicad").is_dir():
            return candidate

    # O carregador do FreeCAD não define __file__ para InitGui.py, mas inclui o
    # diretório do Workbench em sys.path. O junction recomendado resolve desse
    # diretório versionado de usuário para o checkout do projeto.
    for search_path in module_search_paths:
        module_path = path_type(search_path or ".").resolve()
        if not (module_path / "InitGui.py").is_file():
            continue
        for candidate in module_path.parents:
            if (candidate / "pyproject.toml").is_file() and (
                candidate / "src" / "aicad"
            ).is_dir():
                return candidate
    return None


root_path = _project_root()
if root_path is not None:
    dependency_path = str(root_path / ".venv" / "Lib" / "site-packages")
    source_path = str(root_path / "src")
    for import_path in (source_path, dependency_path):
        if Path(import_path).is_dir() and import_path not in sys.path:
            sys.path.insert(0, import_path)


class AICadWorkbench(Workbench):
    MenuText = "AI CAD"
    ToolTip = "Modelagem CAD paramétrica assistida por IA"

    def Initialize(self) -> None:
        from aicad.freecad_commands import register_commands

        register_commands()
        self.appendToolbar("AI CAD", ["AICad_ShowChat"])
        self.appendMenu("AI CAD", ["AICad_ShowChat"])

    def Activated(self) -> None:
        from aicad.ui.chat_panel import show_chat_panel

        show_chat_panel()

    def GetClassName(self) -> str:
        return "Gui::PythonWorkbench"


if "AICadWorkbench" not in Gui.listWorkbenches():
    Gui.addWorkbench(AICadWorkbench())

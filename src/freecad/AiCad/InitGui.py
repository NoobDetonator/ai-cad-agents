from __future__ import annotations

import os
import sys
from pathlib import Path

import FreeCADGui as Gui


project_root = os.environ.get("AICAD_PROJECT_ROOT")
if project_root:
    source_path = str(Path(project_root) / "src")
    if source_path not in sys.path:
        sys.path.insert(0, source_path)


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


Gui.addWorkbench(AICadWorkbench())

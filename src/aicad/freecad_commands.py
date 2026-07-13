from __future__ import annotations


def register_commands() -> None:
    import FreeCADGui as Gui

    class ShowChatCommand:
        def GetResources(self) -> dict[str, str]:
            return {
                "MenuText": "Abrir AI CAD",
                "ToolTip": "Abre o painel de modelagem assistida por IA",
            }

        def Activated(self) -> None:
            from aicad.ui.chat_panel import show_chat_panel

            show_chat_panel()

        def IsActive(self) -> bool:
            return True

    Gui.addCommand("AICad_ShowChat", ShowChatCommand())

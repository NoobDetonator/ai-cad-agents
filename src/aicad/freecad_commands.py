from __future__ import annotations


def register_commands() -> None:
    import FreeCADGui as Gui

    class ShowMcpPanelCommand:
        def GetResources(self) -> dict[str, str]:
            return {
                "MenuText": "Abrir TALOS MCP",
                "ToolTip": "Abre o painel de operação e diagnóstico do servidor MCP",
            }

        def Activated(self) -> None:
            from aicad.ui.talos_panel import show_mcp_panel

            show_mcp_panel()

        def IsActive(self) -> bool:
            return True

    Gui.addCommand("Talos_ShowMcpPanel", ShowMcpPanelCommand())

from __future__ import annotations

from collections import Counter
from html import escape
import json
import os
from pathlib import Path

from aicad.bridge.protocol import BridgeRequest
from aicad.core.tool_registry import ToolRisk
from aicad.orchestration.plan_service import CompositeValidatedPlan
from aicad.runtime import get_tool_registry
from aicad.ui.bridge_controller import GuiBridgeController, get_or_start_gui_bridge


def automatic_approval_default(
    environment: dict[str, str] | os._Environ[str] = os.environ,
) -> bool:
    """Auto-approval starts OFF unless TALOS_AUTO_APPROVE=1 asks for it.

    The visible-confirmation default is the product's core safety promise;
    development sessions opt in explicitly (scripts/iniciar_rapido.ps1).
    """

    return environment.get("TALOS_AUTO_APPROVE", "0").strip() == "1"


def mcp_configuration() -> dict[str, object]:
    project_root = Path(__file__).resolve().parents[3]
    scripts = project_root / ".venv" / "Scripts"
    preferred = scripts / "talos-freecad-mcp.exe"
    legacy = scripts / "aicad-mcp.exe"
    executable = preferred if preferred.is_file() else legacy
    return {
        "mcpServers": {
            "talos": {"command": str(executable), "args": []},
        }
    }


def show_mcp_panel() -> None:
    """Show the MCP operations panel and ensure the local bridge is running."""

    import FreeCADGui as Gui
    from PySide import QtCore, QtWidgets

    main_window = Gui.getMainWindow()
    existing = main_window.findChild(QtWidgets.QDockWidget, "TalosMcpDock")
    if existing is not None:
        existing.show()
        existing.raise_()
        return

    registry = get_tool_registry()
    specs = registry.list_specs()
    risks = Counter(spec.risk for spec in specs)
    family_count = len({spec.family for spec in specs})

    dock = QtWidgets.QDockWidget("TALOS MCP", main_window)
    dock.setObjectName("TalosMcpDock")
    dock.setMinimumWidth(390)
    container = QtWidgets.QWidget(dock)
    layout = QtWidgets.QVBoxLayout(container)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(10)

    title = QtWidgets.QLabel(
        "<h2 style='margin:0'>TALOS MCP</h2>"
        "<p style='margin:2px 0 0 0'>FreeCAD seguro para agentes externos</p>",
        container,
    )
    title.setObjectName("TalosPanelTitle")

    bridge_group = QtWidgets.QGroupBox("Ponte local", container)
    bridge_layout = QtWidgets.QVBoxLayout(bridge_group)
    bridge_status = QtWidgets.QLabel("Iniciando ponte MCP...", bridge_group)
    bridge_status.setObjectName("TalosBridgeStatus")
    bridge_status.setWordWrap(True)
    session_details = QtWidgets.QLabel("Sessão ainda não publicada.", bridge_group)
    session_details.setObjectName("TalosSessionDetails")
    session_details.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
    session_details.setWordWrap(True)
    bridge_actions = QtWidgets.QWidget(bridge_group)
    bridge_actions_layout = QtWidgets.QHBoxLayout(bridge_actions)
    bridge_actions_layout.setContentsMargins(0, 0, 0, 0)
    refresh_button = QtWidgets.QPushButton("Atualizar", bridge_actions)
    refresh_button.setObjectName("TalosRefreshStatus")
    copy_config_button = QtWidgets.QPushButton("Copiar configuração MCP", bridge_actions)
    copy_config_button.setObjectName("TalosCopyMcpConfig")
    bridge_actions_layout.addWidget(refresh_button)
    bridge_actions_layout.addWidget(copy_config_button, 1)
    bridge_layout.addWidget(bridge_status)
    bridge_layout.addWidget(session_details)
    bridge_layout.addWidget(bridge_actions)

    catalog_group = QtWidgets.QGroupBox("Capacidades publicadas", container)
    catalog_layout = QtWidgets.QVBoxLayout(catalog_group)
    catalog_summary = QtWidgets.QLabel(
        f"<b>{len(specs)}</b> ferramentas em <b>{family_count}</b> famílias<br>"
        f"{risks[ToolRisk.READ]} leitura · {risks[ToolRisk.MODIFY]} modificação · "
        f"{risks[ToolRisk.EXPORT]} exportação",
        catalog_group,
    )
    catalog_summary.setObjectName("TalosCatalogSummary")
    catalog_layout.addWidget(catalog_summary)

    document_group = QtWidgets.QGroupBox("Documento ativo", container)
    document_layout = QtWidgets.QVBoxLayout(document_group)
    document_status = QtWidgets.QLabel("Consultando o FreeCAD...", document_group)
    document_status.setObjectName("TalosDocumentStatus")
    document_status.setWordWrap(True)
    validate_button = QtWidgets.QPushButton("Recalcular e validar documento", document_group)
    validate_button.setObjectName("TalosValidateDocument")
    document_layout.addWidget(document_status)
    document_layout.addWidget(validate_button)

    approval_group = QtWidgets.QGroupBox("Política de aprovação", container)
    approval_layout = QtWidgets.QVBoxLayout(approval_group)
    automatic_approval = QtWidgets.QCheckBox(
        "Aprovar automaticamente mutações reversíveis", approval_group
    )
    automatic_approval.setObjectName("TalosAutomaticApproval")
    automatic_approval.setChecked(automatic_approval_default())
    automatic_approval.setToolTip(
        "Somente ferramentas compensáveis podem ser aprovadas automaticamente. "
        "Exportações sempre exigem confirmação manual."
    )
    approval_note = QtWidgets.QLabel(
        "Exportações e operações sem compensação continuam manuais. Cada chamada "
        "é validada e auditada.",
        approval_group,
    )
    approval_note.setWordWrap(True)
    approval_layout.addWidget(automatic_approval)
    approval_layout.addWidget(approval_note)

    confirmation_group = QtWidgets.QGroupBox("Confirmação pendente", container)
    confirmation_group.setObjectName("TalosConfirmation")
    confirmation_layout = QtWidgets.QVBoxLayout(confirmation_group)
    confirmation_text = QtWidgets.QLabel("", confirmation_group)
    confirmation_text.setObjectName("TalosConfirmationText")
    confirmation_text.setWordWrap(True)
    confirmation_actions = QtWidgets.QWidget(confirmation_group)
    confirmation_actions_layout = QtWidgets.QHBoxLayout(confirmation_actions)
    confirmation_actions_layout.setContentsMargins(0, 0, 0, 0)
    approve_button = QtWidgets.QPushButton("Aprovar e executar", confirmation_actions)
    approve_button.setObjectName("TalosApprove")
    reject_button = QtWidgets.QPushButton("Rejeitar", confirmation_actions)
    reject_button.setObjectName("TalosReject")
    confirmation_actions_layout.addWidget(approve_button, 1)
    confirmation_actions_layout.addWidget(reject_button)
    confirmation_layout.addWidget(confirmation_text)
    confirmation_layout.addWidget(confirmation_actions)
    confirmation_group.hide()

    events_group = QtWidgets.QGroupBox("Atividade MCP", container)
    events_layout = QtWidgets.QVBoxLayout(events_group)
    event_log = QtWidgets.QTextBrowser(events_group)
    event_log.setObjectName("TalosEventLog")
    event_log.setOpenExternalLinks(False)
    event_log.setMinimumHeight(170)
    clear_events_button = QtWidgets.QPushButton("Limpar visualização", events_group)
    clear_events_button.setObjectName("TalosClearEvents")
    events_layout.addWidget(event_log, 1)
    events_layout.addWidget(clear_events_button)

    layout.addWidget(title)
    layout.addWidget(bridge_group)
    layout.addWidget(catalog_group)
    layout.addWidget(document_group)
    layout.addWidget(approval_group)
    layout.addWidget(confirmation_group)
    layout.addWidget(events_group, 1)
    dock.setWidget(container)
    main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)

    controllers: list[GuiBridgeController] = []
    pending: list[BridgeRequest | CompositeValidatedPlan] = []
    active: list[BridgeRequest | CompositeValidatedPlan | None] = [None]

    def append_event(title_text: str, detail: str) -> None:
        event_log.append(
            f"<p style='margin:3px 0'><b>{escape(title_text)}</b><br>"
            f"{escape(detail)}</p>"
        )

    def controller() -> GuiBridgeController | None:
        return controllers[0] if controllers else None

    def operation_is_automatic(
        operation: BridgeRequest | CompositeValidatedPlan,
    ) -> bool:
        if not automatic_approval.isChecked():
            return False
        if isinstance(operation, CompositeValidatedPlan):
            return all(
                registry.get_spec(call.name).compensatable for call in operation.calls
            )
        spec = registry.get_spec(operation.tool_name)
        return spec.risk is ToolRisk.MODIFY and spec.compensatable

    def operation_description(
        operation: BridgeRequest | CompositeValidatedPlan,
    ) -> str:
        if isinstance(operation, CompositeValidatedPlan):
            steps = " · ".join(operation.steps)
            return (
                f"Plano com {len(operation.calls)} etapas: {operation.intention}. "
                f"{steps}"
            )
        spec = registry.get_spec(operation.tool_name)
        arguments = json.dumps(
            operation.arguments, ensure_ascii=False, sort_keys=True
        )
        return f"{operation.tool_name} [{spec.risk.value}] — {arguments}"

    def show_next_confirmation() -> None:
        if active[0] is not None or not pending:
            return
        operation = pending.pop(0)
        active[0] = operation
        confirmation_text.setText(escape(operation_description(operation)))
        confirmation_group.show()

    def finish_active() -> None:
        active[0] = None
        confirmation_group.hide()
        confirmation_text.clear()
        show_next_confirmation()

    def resolve_operation(
        operation: BridgeRequest | CompositeValidatedPlan,
        *,
        approved: bool,
        automatic: bool,
    ) -> None:
        current_controller = controller()
        if current_controller is None:
            append_event("Ponte indisponível", "A operação não pôde ser resolvida.")
            return
        if isinstance(operation, CompositeValidatedPlan):
            snapshot = current_controller.resolve_plan_confirmation(
                operation.plan_id,
                approved=approved,
                automatic=automatic,
            )
            append_event(
                "Plano MCP atualizado",
                f"{operation.plan_id} — {snapshot.status.value} "
                f"({snapshot.completed_calls}/{snapshot.total_calls}).",
            )
            return
        response = current_controller.resolve_confirmation(
            operation.request_id,
            approved=approved,
            automatic=automatic,
        )
        detail = response.status.value
        if response.error is not None:
            detail += f" — {response.error.message}"
        append_event(f"Ferramenta MCP: {operation.tool_name}", detail)

    def queue_operation(operation: BridgeRequest | CompositeValidatedPlan) -> None:
        append_event("Solicitação recebida", operation_description(operation))
        if operation_is_automatic(operation):
            resolve_operation(operation, approved=True, automatic=True)
            return
        pending.append(operation)
        show_next_confirmation()

    def approve_active() -> None:
        operation = active[0]
        if operation is None:
            return
        resolve_operation(operation, approved=True, automatic=False)
        finish_active()

    def reject_active() -> None:
        operation = active[0]
        if operation is None:
            return
        resolve_operation(operation, approved=False, automatic=False)
        finish_active()

    def refresh_status() -> None:
        current_controller = controller()
        if current_controller is None or not current_controller.is_running:
            bridge_status.setText("Ponte MCP indisponível")
            session_details.setText("Ative novamente o Workbench TALOS MCP.")
        else:
            record = current_controller.session_record
            bridge_status.setText("Ponte MCP ativa e autenticada")
            session_details.setText(
                f"127.0.0.1:{record.port} · sessão {str(record.session_id)[:8]}… · "
                f"PID {record.process_id} · protocolo {record.protocol_version}"
            )
        try:
            summary = registry.execute("cad.get_document_summary")
            if summary.get("active"):
                document_status.setText(
                    f"<b>{escape(str(summary.get('label') or summary.get('name')))}</b> · "
                    f"{len(summary.get('objects', ()))} objetos"
                )
            else:
                document_status.setText("Nenhum documento ativo.")
        except Exception as exc:
            document_status.setText(f"Contexto indisponível: {escape(str(exc))}")

    def validate_document() -> None:
        try:
            result = registry.execute("cad.validate_document")
            if result.get("valid"):
                append_event("Validação concluída", "Documento e formas válidos.")
            else:
                errors = "; ".join(str(item) for item in result.get("errors", ()))
                append_event("Validação encontrou erros", errors or "Erro não detalhado.")
        except Exception as exc:
            append_event("Validação indisponível", str(exc))
        refresh_status()

    def copy_configuration() -> None:
        payload = json.dumps(mcp_configuration(), ensure_ascii=False, indent=2)
        QtWidgets.QApplication.clipboard().setText(payload)
        append_event(
            "Configuração copiada",
            "Cole o JSON no cliente MCP. Nenhum token de sessão foi copiado.",
        )

    def automatic_policy_changed(enabled: bool) -> None:
        append_event(
            "Política de aprovação",
            (
                "Mutações compensáveis serão aprovadas automaticamente nesta sessão."
                if enabled
                else "Confirmação visual restaurada para todas as mutações."
            ),
        )
        operation = active[0]
        if enabled and operation is not None and operation_is_automatic(operation):
            resolve_operation(operation, approved=True, automatic=True)
            finish_active()

    approve_button.clicked.connect(approve_active)
    reject_button.clicked.connect(reject_active)
    refresh_button.clicked.connect(refresh_status)
    validate_button.clicked.connect(validate_document)
    copy_config_button.clicked.connect(copy_configuration)
    clear_events_button.clicked.connect(event_log.clear)
    automatic_approval.toggled.connect(automatic_policy_changed)

    try:
        bridge = get_or_start_gui_bridge(queue_operation, queue_operation)
        controllers.append(bridge)
        append_event(
            "Ponte MCP pronta",
            "Aguardando agentes externos. Exportações sempre exigem aprovação manual.",
        )
    except Exception as exc:
        append_event("Falha ao iniciar a ponte MCP", str(exc))

    refresh_timer = QtCore.QTimer(dock)
    refresh_timer.setInterval(1500)
    refresh_timer.timeout.connect(refresh_status)
    refresh_timer.start()
    dock.destroyed.connect(refresh_timer.stop)

    refresh_status()
    dock.show()


__all__ = [
    "automatic_approval_default",
    "mcp_configuration",
    "show_mcp_panel",
]

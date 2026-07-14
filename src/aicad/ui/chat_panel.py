from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from queue import Empty, Queue
from threading import Event, Thread
from typing import Any

from aicad.bridge.protocol import (
    BridgeRequest,
    BridgeResponse,
    BridgeResponseStatus,
)
from aicad.core.chat_commands import ChatCommand, format_tool_result, parse_chat_command
from aicad.core.context import DocumentStateToken
from aicad.core.tool_registry import ToolRisk
from aicad.orchestration import (
    AgentSessionMemory,
    AgentStage,
    AgentTurnCancellation,
    AgentTurnCancelledError,
    AgentTurnController,
    AgentTurnResult,
    AgentTurnStatus,
    ApprovalGrant,
    CompositeApprovalGrant,
    CompositePlanError,
    CompositePlanExecutor,
    CompositeValidatedPlan,
    AiOrchestrator,
    DeepSeekProvider,
    OrchestrationLimits,
    OrchestrationPlan,
    PlanApprovalError,
    PlanExecutionError,
    PlanService,
    SingleMutationPlanExecutor,
    ValidatedPlan,
)
from aicad.orchestration.credentials import (
    CredentialStore,
    CredentialStoreError,
)
from aicad.runtime import get_tool_registry
from aicad.ui.bridge_controller import GuiBridgeController, get_or_start_gui_bridge


DOCK_NAME = "AICadChatDock"


@dataclass(slots=True)
class _GuiReadRequest:
    name: str
    arguments: dict[str, Any]
    cancellation: AgentTurnCancellation
    completed: Event = field(default_factory=Event)
    result: Any = None
    error: Exception | None = None


def show_chat_panel() -> None:
    import FreeCADGui as Gui
    from PySide import QtCore, QtWidgets

    main_window = Gui.getMainWindow()
    existing = main_window.findChild(QtWidgets.QDockWidget, DOCK_NAME)
    if existing is not None:
        existing.show()
        existing.raise_()
        return

    dock = QtWidgets.QDockWidget("AI CAD", main_window)
    dock.setObjectName(DOCK_NAME)
    dock.setAllowedAreas(
        QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea
    )

    container = QtWidgets.QWidget(dock)
    layout = QtWidgets.QVBoxLayout(container)

    status = QtWidgets.QLabel("Modo local seguro", container)
    status.setObjectName("AICadStatus")
    status.setWordWrap(True)

    credential_actions = QtWidgets.QWidget(container)
    credential_actions_layout = QtWidgets.QHBoxLayout(credential_actions)
    credential_actions_layout.setContentsMargins(0, 0, 0, 0)
    configure_api_key = QtWidgets.QPushButton("Configurar chave DeepSeek", container)
    configure_api_key.setObjectName("AICadConfigureApiKey")
    remove_api_key = QtWidgets.QPushButton("Remover chave", container)
    remove_api_key.setObjectName("AICadRemoveApiKey")
    credential_actions_layout.addWidget(configure_api_key, 1)
    credential_actions_layout.addWidget(remove_api_key)

    use_deepseek = QtWidgets.QCheckBox("Usar IA DeepSeek", container)
    use_deepseek.setObjectName("AICadUseDeepSeek")
    use_deepseek.setChecked(False)

    history = QtWidgets.QTextBrowser(container)
    history.setObjectName("AICadHistory")
    history.setHtml(
        "<b>AI CAD pronto.</b><br>"
        "O chat local já pode ler o documento e preparar operações CAD seguras. "
        "Digite <code>ajuda</code> para ver os comandos."
    )

    prompt = QtWidgets.QPlainTextEdit(container)
    prompt.setObjectName("AICadPrompt")
    prompt.setPlaceholderText("Descreva a peça ou alteração desejada...")
    prompt.setMaximumHeight(100)

    send = QtWidgets.QPushButton("Enviar", container)
    send.setObjectName("AICadSend")

    cancel_ai_button = QtWidgets.QPushButton("Cancelar consulta da IA", container)
    cancel_ai_button.setObjectName("AICadCancelAi")
    cancel_ai_button.hide()

    confirmation = QtWidgets.QWidget(container)
    confirmation.setObjectName("AICadConfirmation")
    confirmation_layout = QtWidgets.QHBoxLayout(confirmation)
    confirmation_layout.setContentsMargins(0, 0, 0, 0)
    apply_button = QtWidgets.QPushButton("Confirmar operação", confirmation)
    apply_button.setObjectName("AICadApply")
    cancel_button = QtWidgets.QPushButton("Cancelar", confirmation)
    cancel_button.setObjectName("AICadCancel")
    confirmation_layout.addWidget(apply_button, 1)
    confirmation_layout.addWidget(cancel_button)
    confirmation.hide()

    registry = get_tool_registry()
    pending: list[
        ChatCommand | BridgeRequest | ValidatedPlan | CompositeValidatedPlan
    ] = []
    remote_confirmation_queue: list[BridgeRequest] = []
    bridge_controller: list[GuiBridgeController] = []
    credential_store = CredentialStore()
    bridge_active = [False]
    credential_configured: list[bool | None] = [None]
    credential_vault_available = [True]
    ai_busy = [False]
    ai_results: Queue[tuple[str, object]] = Queue()
    ai_progress: Queue[AgentStage] = Queue()
    ai_read_requests: Queue[_GuiReadRequest] = Queue()
    active_ai_cancellation: list[AgentTurnCancellation] = []
    ai_stage: list[AgentStage | None] = [None]
    session_memory = AgentSessionMemory()
    plan_service = PlanService()
    ai_timer = QtCore.QTimer(container)

    def append_assistant(message: str) -> None:
        history.append(f"<p><b>AI CAD:</b> {message}</p>")

    def refresh_security_status() -> None:
        parts = [
            "Modo local seguro",
            (
                "ponte MCP local ativa"
                if bridge_active[0]
                else "ponte MCP indisponível"
            ),
        ]
        if not credential_vault_available[0]:
            parts.append("cofre de credenciais indisponível")
        elif credential_configured[0] is True:
            parts.append("chave DeepSeek no cofre")
        elif credential_configured[0] is False:
            parts.append("sem chave DeepSeek")
        else:
            parts.append("chave DeepSeek gerenciada sob demanda")
        if ai_busy[0]:
            stage_labels = {
                AgentStage.PREPARE_CONTEXT: "preparando contexto",
                AgentStage.SELECT_TOOLS: "selecionando ferramentas",
                AgentStage.ASK_MODEL: "consultando DeepSeek",
                AgentStage.VALIDATE_PLAN: "validando plano",
                AgentStage.EXECUTE_READS: "lendo o documento",
            }
            parts.append(stage_labels.get(ai_stage[0], "consultando DeepSeek"))
        elif use_deepseek.isChecked():
            parts.append("DeepSeek habilitada")
        status.setText(" • ".join(parts))
        remove_api_key.setEnabled(credential_vault_available[0])


    def configure_deepseek_api_key() -> None:
        api_key, accepted = QtWidgets.QInputDialog.getText(
            dock,
            "Configurar chave DeepSeek",
            (
                "Cole sua chave de API. Ela será salva somente no cofre "
                "de credenciais do Windows:"
            ),
            QtWidgets.QLineEdit.Password,
        )
        if not accepted:
            return
        try:
            credential_store.set_api_key("deepseek", api_key)
        except (CredentialStoreError, ValueError) as exc:
            append_assistant(
                "A chave DeepSeek não foi salva: " + escape(str(exc))
            )
            return
        credential_configured[0] = True
        credential_vault_available[0] = True
        append_assistant(
            "Chave DeepSeek salva no cofre do Windows. "
            "Nenhuma chamada externa foi ativada ainda."
        )
        refresh_security_status()

    def remove_deepseek_api_key() -> None:
        try:
            has_api_key = credential_store.has_api_key("deepseek")
        except CredentialStoreError as exc:
            credential_vault_available[0] = False
            append_assistant(
                "O cofre de credenciais não pôde ser consultado: "
                + escape(str(exc))
            )
            refresh_security_status()
            return
        credential_vault_available[0] = True
        credential_configured[0] = has_api_key
        if not has_api_key:
            append_assistant("Nenhuma chave DeepSeek está salva no cofre do Windows.")
            refresh_security_status()
            return
        decision = QtWidgets.QMessageBox.question(
            dock,
            "Remover chave DeepSeek",
            "Remover a chave DeepSeek do cofre de credenciais do Windows?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if decision != QtWidgets.QMessageBox.Yes:
            return
        try:
            credential_store.delete_api_key("deepseek")
        except CredentialStoreError as exc:
            append_assistant(
                "A chave DeepSeek não foi removida: " + escape(str(exc))
            )
            return
        credential_configured[0] = False
        credential_vault_available[0] = True
        append_assistant("Chave DeepSeek removida do cofre do Windows.")
        refresh_security_status()


    def set_pending(
        command: (
            ChatCommand
            | BridgeRequest
            | ValidatedPlan
            | CompositeValidatedPlan
            | None
        ),
    ) -> None:
        pending.clear()
        if command is not None:
            pending.append(command)
        waiting = command is not None
        confirmation.setVisible(waiting)
        inputs_enabled = not waiting and not ai_busy[0]
        prompt.setEnabled(inputs_enabled)
        send.setEnabled(inputs_enabled)
        use_deepseek.setEnabled(inputs_enabled)

    def set_ai_busy(busy: bool) -> None:
        ai_busy[0] = busy
        if not busy:
            ai_stage[0] = None
        inputs_enabled = not busy and not pending
        prompt.setEnabled(inputs_enabled)
        send.setEnabled(inputs_enabled)
        use_deepseek.setEnabled(inputs_enabled)
        cancel_ai_button.setVisible(busy)
        cancel_ai_button.setEnabled(busy)
        refresh_security_status()

    def refresh_view(tool_name: str) -> None:
        if tool_name not in {
            "cad.create_box",
            "cad.create_cylinder",
            "cad.undo",
        }:
            return
        active_gui_document = Gui.activeDocument()
        if active_gui_document is not None:
            active_gui_document.activeView().viewAxonometric()
            active_gui_document.activeView().fitAll()

    def describe_bridge_request(request: BridgeRequest) -> str:
        arguments = ", ".join(
            f"<code>{escape(str(name))}={escape(str(value))}</code>"
            for name, value in request.arguments.items()
        )
        if not arguments:
            arguments = "sem argumentos"
        return (
            "<b>Solicitação MCP recebida.</b><br>"
            f"Ferramenta: <code>{escape(request.tool_name)}</code><br>"
            f"Argumentos: {arguments}<br>"
            "A operação só será executada após sua confirmação."
        )

    def show_next_remote_confirmation() -> None:
        if pending or ai_busy[0] or not remote_confirmation_queue:
            return
        request = remote_confirmation_queue.pop(0)
        append_assistant(describe_bridge_request(request))
        set_pending(request)

    def queue_bridge_confirmation(request: BridgeRequest) -> None:
        remote_confirmation_queue.append(request)
        show_next_remote_confirmation()

    def show_bridge_response(
        request: BridgeRequest,
        response: BridgeResponse,
    ) -> None:
        if response.status is BridgeResponseStatus.COMPLETED:
            append_assistant(format_tool_result(request.tool_name, response.result))
            refresh_view(request.tool_name)
            return
        message = (
            response.error.message
            if response.error is not None
            else f"Estado da solicitação MCP: {response.status}."
        )
        append_assistant(f"Solicitação MCP não executada: {escape(message)}")

    def execute(command: ChatCommand, confirmed: bool = False) -> None:
        try:
            result = registry.execute(
                command.tool_name,
                command.arguments,
                confirmed=confirmed,
            )
            append_assistant(format_tool_result(command.tool_name, result))
            refresh_view(command.tool_name)
        except (KeyError, PermissionError, RuntimeError, ValueError) as exc:
            append_assistant(f"Operação não executada: {escape(str(exc))}")

    def describe_ai_plan(plan: OrchestrationPlan) -> str:
        sections = [
            f"<b>Intenção:</b> {escape(plan.intention)}",
            "<b>Plano:</b><ol>"
            + "".join(f"<li>{escape(step)}</li>" for step in plan.steps)
            + "</ol>",
        ]
        if plan.assumptions:
            assumptions = "; ".join(escape(item) for item in plan.assumptions)
            sections.insert(1, f"<b>Suposições:</b> {assumptions}")
        if plan.message:
            sections.append(escape(plan.message))
        for call in plan.tool_calls:
            arguments = ", ".join(
                f"<code>{escape(str(name))}={escape(str(value))}</code>"
                for name, value in call.arguments.items()
            )
            sections.append(
                f"<b>Ferramenta proposta:</b> <code>{escape(call.name)}</code>"
                + (f"<br>Argumentos: {arguments}" if arguments else "")
            )
        return "<br>".join(sections)

    def read_work_context() -> dict[str, Any]:
        return registry.execute(
            "cad.get_context_snapshot",
            {"detail_level": "work", "max_objects": 25, "cursor": 0},
        )

    def describe_validated_plan(plan: ValidatedPlan) -> str:
        return (
            "<b>Plano imutável aguardando aprovação.</b><br>"
            f"ID: <code>{escape(str(plan.plan_id))}</code><br>"
            f"Hash: <code>{escape(plan.plan_hash[:16])}…</code><br>"
            f"Estado-base: revisão {plan.base_state_token.revision}.<br>"
            "Somente a chamada exibida e este estado exato serão aceitos."
        )

    def describe_composite_plan(plan: CompositeValidatedPlan) -> str:
        calls = "".join(
            f"<li><code>{escape(call.name)}</code> — "
            f"<code>{escape(call.call_id)}</code></li>"
            for call in plan.calls
        )
        return (
            "<b>Plano composto aguardando uma única aprovação.</b><br>"
            f"ID: <code>{escape(str(plan.plan_id))}</code><br>"
            f"Hash: <code>{escape(plan.plan_hash[:16])}…</code><br>"
            f"Estado-base: revisão {plan.base_state_token.revision}."
            f"<ol>{calls}</ol>"
            "Falha em qualquer etapa desfaz somente as transações deste plano."
        )

    def request_deepseek_plan(text: str) -> None:
        try:
            document_context = read_work_context()
        except (KeyError, PermissionError, RuntimeError, ValueError):
            append_assistant(
                "Não foi possível preparar o contexto do documento para a DeepSeek."
            )
            return
        cancellation = AgentTurnCancellation()
        active_ai_cancellation.clear()
        active_ai_cancellation.append(cancellation)
        set_ai_busy(True)
        ai_timer.start()

        def worker() -> None:
            try:
                api_key = credential_store.get_api_key("deepseek")
            except CredentialStoreError:
                ai_results.put(("vault_error", None))
                return
            if api_key is None:
                ai_results.put(("missing_key", None))
                return
            provider = None
            try:
                provider = DeepSeekProvider(api_key)
                orchestrator = AiOrchestrator(
                    registry,
                    provider,
                    limits=OrchestrationLimits(max_tool_calls=2),
                )
                controller = AgentTurnController(
                    registry,
                    orchestrator,
                    read_executor=execute_ai_read_on_gui,
                    memory=session_memory,
                )
                turn = controller.run(
                    text,
                    context={"snapshot": document_context},
                    cancellation=cancellation,
                    progress=ai_progress.put,
                )
            except Exception:
                ai_results.put(("provider_error", None))
                return
            finally:
                if provider is not None:
                    provider.close()
            ai_results.put(("turn", (turn, document_context)))

        Thread(
            target=worker,
            name="aicad-deepseek",
            daemon=True,
        ).start()

    def execute_ai_read_on_gui(
        name: str,
        arguments: dict[str, Any],
    ) -> Any:
        if not active_ai_cancellation:
            raise AgentTurnCancelledError("The AI turn is no longer active.")
        cancellation = active_ai_cancellation[0]
        request = _GuiReadRequest(name, dict(arguments), cancellation)
        ai_read_requests.put(request)
        while not request.completed.wait(0.05):
            cancellation.raise_if_cancelled()
        cancellation.raise_if_cancelled()
        if request.error is not None:
            raise RuntimeError("The GUI read failed safely.") from request.error
        return request.result

    def process_ai_read_requests() -> None:
        while True:
            try:
                request = ai_read_requests.get_nowait()
            except Empty:
                return
            try:
                request.cancellation.raise_if_cancelled()
                request.result = registry.execute(request.name, request.arguments)
            except Exception as exc:
                request.error = exc
            finally:
                request.completed.set()

    def cancel_ai_turn() -> None:
        if not ai_busy[0] or not active_ai_cancellation:
            return
        active_ai_cancellation[0].cancel()
        cancel_ai_button.setEnabled(False)
        append_assistant(
            "Cancelamento solicitado; a operação será interrompida no próximo "
            "ponto seguro."
        )

    def process_ai_result() -> None:
        process_ai_read_requests()
        try:
            while True:
                ai_stage[0] = ai_progress.get_nowait()
        except Empty:
            pass
        if ai_busy[0]:
            refresh_security_status()
        try:
            result_kind, payload = ai_results.get_nowait()
        except Empty:
            return
        ai_timer.stop()
        active_ai_cancellation.clear()
        set_ai_busy(False)
        if result_kind == "missing_key":
            credential_configured[0] = False
            append_assistant("Configure a chave DeepSeek antes de usar o modo de IA.")
            refresh_security_status()
            show_next_remote_confirmation()
            return
        if result_kind == "vault_error":
            credential_vault_available[0] = False
            append_assistant("O cofre de credenciais não pôde ser consultado.")
            refresh_security_status()
            show_next_remote_confirmation()
            return
        if (
            result_kind != "turn"
            or not isinstance(payload, tuple)
            or len(payload) != 2
            or not isinstance(payload[0], AgentTurnResult)
            or not isinstance(payload[1], dict)
        ):
            credential_configured[0] = True
            append_assistant(
                "A DeepSeek não respondeu com um plano válido. "
                "Tente novamente em alguns instantes."
            )
            refresh_security_status()
            show_next_remote_confirmation()
            return
        turn_result, base_context = payload
        credential_configured[0] = True
        credential_vault_available[0] = True
        refresh_security_status()
        if turn_result.status is AgentTurnStatus.CANCELLED:
            append_assistant("Consulta cancelada sem alterar o documento.")
            show_next_remote_confirmation()
            return
        plan = turn_result.final_plan
        if plan is None:
            append_assistant("A consulta terminou sem um plano utilizável.")
            show_next_remote_confirmation()
            return
        append_assistant(describe_ai_plan(plan))
        if not plan.tool_calls:
            show_next_remote_confirmation()
            return
        call = plan.tool_calls[0]
        if call.risk is not ToolRisk.READ:
            try:
                base_state = DocumentStateToken.model_validate(
                    base_context["state_token"]
                )
                if len(plan.tool_calls) == 1:
                    validated_plan = ValidatedPlan.build(plan, base_state, registry)
                else:
                    validated_plan = CompositeValidatedPlan.build(
                        plan,
                        base_state,
                        registry,
                    )
            except (KeyError, RuntimeError, ValueError):
                append_assistant(
                    "A mutação proposta não pôde ser congelada com segurança."
                )
                show_next_remote_confirmation()
                return
            if isinstance(validated_plan, CompositeValidatedPlan):
                plan_service.submit(validated_plan)
                append_assistant(describe_composite_plan(validated_plan))
            else:
                append_assistant(describe_validated_plan(validated_plan))
            set_pending(validated_plan)
            return
        command = ChatCommand(
            message="Operação proposta pela DeepSeek.",
            tool_name=call.name,
            arguments=dict(call.arguments),
        )
        execute(command)
        show_next_remote_confirmation()

    def submit() -> None:
        text = prompt.toPlainText().strip()
        if not text:
            return
        history.append(f"<p><b>Você:</b> {escape(text)}</p>")
        prompt.clear()
        if use_deepseek.isChecked():
            request_deepseek_plan(text)
            return
        command = parse_chat_command(text)
        append_assistant(command.message)
        if command.tool_name is None:
            return
        spec = registry.get_spec(command.tool_name)
        if spec.risk is ToolRisk.READ:
            execute(command)
            return
        set_pending(command)

    def confirm_pending() -> None:
        if not pending:
            return
        operation = pending[0]
        set_pending(None)
        if isinstance(operation, ChatCommand):
            execute(operation, confirmed=True)
        elif isinstance(operation, ValidatedPlan):
            try:
                grant = ApprovalGrant.issue(operation)
                result = SingleMutationPlanExecutor(
                    registry,
                    read_work_context,
                ).execute(operation, grant)
                append_assistant(
                    format_tool_result(operation.call.name, result.tool_result)
                )
                append_assistant(
                    "Plano imutável executado e pós-condição validada; "
                    f"novo estado na revisão {result.state_after.revision}."
                )
                refresh_view(operation.call.name)
            except (PlanApprovalError, PlanExecutionError, RuntimeError, ValueError) as exc:
                append_assistant(
                    "Plano não executado: " + escape(str(exc))
                )
        elif isinstance(operation, CompositeValidatedPlan):
            try:
                grant = CompositeApprovalGrant.issue(operation)
                append_assistant(
                    f"Executando plano composto de {len(operation.calls)} etapas."
                )

                def show_composite_progress(snapshot) -> None:
                    append_assistant(
                        "Plano composto: "
                        f"{snapshot.completed_calls}/{snapshot.total_calls} "
                        "etapas validadas."
                    )

                result = plan_service.execute(
                    operation.plan_id,
                    grant,
                    CompositePlanExecutor(registry, read_work_context),
                    on_progress=show_composite_progress,
                )
                for call, tool_result in zip(
                    operation.calls,
                    result.results,
                    strict=True,
                ):
                    append_assistant(format_tool_result(call.name, tool_result))
                    refresh_view(call.name)
                append_assistant(
                    "Plano composto concluído; todas as pós-condições passaram."
                )
            except (CompositePlanError, PlanApprovalError, RuntimeError, ValueError) as exc:
                append_assistant(
                    "Plano composto não concluído: " + escape(str(exc))
                )
        elif bridge_controller:
            response = bridge_controller[0].resolve_confirmation(
                operation.request_id,
                approved=True,
            )
            show_bridge_response(operation, response)
        else:
            append_assistant("A ponte MCP não está disponível para confirmar.")
        show_next_remote_confirmation()

    def cancel_pending() -> None:
        if not pending:
            return
        operation = pending[0]
        set_pending(None)
        if isinstance(operation, ChatCommand):
            append_assistant("Operação cancelada; o documento não foi alterado.")
        elif isinstance(operation, ValidatedPlan):
            append_assistant(
                "Plano imutável cancelado; nenhuma autorização foi emitida e o "
                "documento não foi alterado."
            )
        elif isinstance(operation, CompositeValidatedPlan):
            plan_service.cancel(operation.plan_id)
            append_assistant(
                "Plano composto cancelado; nenhuma etapa foi executada."
            )
        elif bridge_controller:
            response = bridge_controller[0].resolve_confirmation(
                operation.request_id,
                approved=False,
            )
            show_bridge_response(operation, response)
        else:
            append_assistant("Solicitação MCP cancelada sem alterar o documento.")
        show_next_remote_confirmation()

    refresh_security_status()
    try:
        controller = get_or_start_gui_bridge(queue_bridge_confirmation)
        bridge_controller.append(controller)
        bridge_active[0] = True
        refresh_security_status()
    except (OSError, RuntimeError, ValueError) as exc:
        append_assistant(
            "Ponte MCP indisponível; o chat local continua ativo: "
            + escape(str(exc))
        )

    ai_timer.setInterval(50)
    ai_timer.timeout.connect(process_ai_result)
    send.clicked.connect(submit)
    cancel_ai_button.clicked.connect(cancel_ai_turn)
    apply_button.clicked.connect(confirm_pending)
    cancel_button.clicked.connect(cancel_pending)
    configure_api_key.clicked.connect(configure_deepseek_api_key)
    remove_api_key.clicked.connect(remove_deepseek_api_key)
    use_deepseek.toggled.connect(refresh_security_status)
    layout.addWidget(status)
    layout.addWidget(credential_actions)
    layout.addWidget(use_deepseek)
    layout.addWidget(history, 1)
    layout.addWidget(prompt)
    layout.addWidget(send)
    layout.addWidget(cancel_ai_button)
    layout.addWidget(confirmation)
    dock.setWidget(container)
    main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
    dock.show()

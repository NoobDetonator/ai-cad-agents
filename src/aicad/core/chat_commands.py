from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
import re
import unicodedata
from typing import Any


HELP_TEXT = (
    "Comandos locais disponíveis:<br>"
    "• <code>resumo</code> — lê o documento ativo<br>"
    "• <code>seleção</code> — lê a seleção atual<br>"
    "• <code>contexto</code> — lê o contexto versionado do trabalho atual<br>"
    "• <code>detalhes Base</code>, <code>medir Base</code> ou "
    "<code>parâmetros Base</code> — inspeciona um objeto<br>"
    "• <code>validar</code> — recalcula e verifica o documento<br>"
    "• <code>caixa 10 x 20 x 30 nome MinhaCaixa</code> — prepara uma caixa em mm<br>"
    "• <code>cilindro 30 x 60 nome Eixo</code> — prepara um cilindro por "
    "diâmetro × altura em mm<br>"
    "• <code>placa 100 x 60 x 8 nome Base</code> — prepara uma placa em mm<br>"
    "• <code>desfazer</code> — prepara a reversão da última transação"
)


@dataclass(frozen=True, slots=True)
class ChatCommand:
    message: str
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)


_NUMBER = r"(\d+(?:[\.,]\d+)?)"
_BOX_PATTERN = re.compile(
    rf"^\s*(?:(?:criar|crie|fazer|faça|faca)\s+)?(?:uma\s+)?caixa\s+"
    rf"{_NUMBER}\s*[x×]\s*{_NUMBER}\s*[x×]\s*{_NUMBER}"
    rf"(?:\s+(?:nome|chamada)\s+([A-Za-z][A-Za-z0-9_-]*))?\s*$",
    re.IGNORECASE,
)

_CYLINDER_PATTERN = re.compile(
    rf"^\s*(?:(?:criar|crie|fazer|faça|faca)\s+)?(?:um\s+)?cilindro\s+"
    rf"{_NUMBER}\s*[x×]\s*{_NUMBER}"
    rf"(?:\s+(?:nome|chamado)\s+([A-Za-z][A-Za-z0-9_-]*))?\s*$",
    re.IGNORECASE,
)

_PLATE_PATTERN = re.compile(
    rf"^\s*(?:(?:criar|crie|fazer|faça|faca)\s+)?(?:uma\s+)?(?:placa|chapa)\s+"
    rf"{_NUMBER}\s*[x×]\s*{_NUMBER}\s*[x×]\s*{_NUMBER}"
    rf"(?:\s+(?:nome|chamada)\s+([A-Za-z][A-Za-z0-9_-]*))?\s*$",
    re.IGNORECASE,
)

_OBJECT_READ_PATTERN = re.compile(
    r"^\s*(detalhes|medir|medidas|depend[eê]ncias|par[aâ]metros)\s+(.+?)\s*$",
    re.IGNORECASE,
)


def _normalized(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(
        character for character in normalized if not unicodedata.combining(character)
    )


def parse_chat_command(text: str) -> ChatCommand:
    cleaned = text.strip()
    if not cleaned:
        return ChatCommand("Digite um comando para continuar.")

    command = _normalized(cleaned)
    if command in {"ajuda", "comandos", "help"}:
        return ChatCommand(HELP_TEXT)
    if command in {"resumo", "documento", "resumo do documento"}:
        return ChatCommand(
            "Vou ler o documento ativo sem modificá-lo.",
            "cad.get_document_summary",
        )
    if command in {"selecao", "ler selecao", "selecao atual"}:
        return ChatCommand("Vou ler a seleção atual.", "cad.get_selection")
    if command in {"contexto", "contexto atual", "estado atual"}:
        return ChatCommand(
            "Vou ler o contexto versionado do documento sem modificá-lo.",
            "cad.get_context_snapshot",
            {"detail_level": "work", "max_objects": 25, "cursor": 0},
        )
    if command in {"validar", "validar documento", "verificar documento"}:
        return ChatCommand(
            "Vou recalcular e validar o documento sem alterar sua geometria.",
            "cad.validate_document",
        )
    if command in {"desfazer", "undo", "reverter"}:
        return ChatCommand(
            "Plano: desfazer a última transação CAD confirmada.",
            "cad.undo",
        )

    object_read = _OBJECT_READ_PATTERN.fullmatch(cleaned)
    if object_read:
        action = _normalized(object_read.group(1))
        reference = object_read.group(2).strip()
        tools = {
            "detalhes": "cad.get_object_details",
            "medir": "cad.measure_object",
            "medidas": "cad.measure_object",
            "dependencias": "cad.get_dependencies",
            "parametros": "cad.get_editable_parameters",
        }
        return ChatCommand(
            f"Vou inspecionar {escape(reference)} sem modificar o documento.",
            tools[action],
            {"object": reference},
        )

    box_match = _BOX_PATTERN.fullmatch(cleaned)
    if box_match:
        length, width, height = (
            float(value.replace(",", ".")) for value in box_match.groups()[:3]
        )
        name = box_match.group(4) or "AIBox"
        return ChatCommand(
            f"Plano: criar a caixa {name} com {length:g} × {width:g} × {height:g} mm, "
            "recalcular e validar antes de confirmar a transação.",
            "cad.create_box",
            {
                "length": length,
                "width": width,
                "height": height,
                "name": name,
            },
        )

    cylinder_match = _CYLINDER_PATTERN.fullmatch(cleaned)
    if cylinder_match:
        diameter, height = (
            float(value.replace(",", ".")) for value in cylinder_match.groups()[:2]
        )
        name = cylinder_match.group(3) or "AICylinder"
        return ChatCommand(
            (
                f"Plano: criar o cilindro {name} com diâmetro {diameter:g} mm "
                f"e altura {height:g} mm no eixo Z, recalcular e validar antes "
                "de confirmar a transação."
            ),
            "cad.create_cylinder",
            {
                "diameter": diameter,
                "height": height,
                "name": name,
            },
        )

    plate_match = _PLATE_PATTERN.fullmatch(cleaned)
    if plate_match:
        length, width, thickness = (
            float(value.replace(",", ".")) for value in plate_match.groups()[:3]
        )
        name = plate_match.group(4) or "AIPlate"
        return ChatCommand(
            (
                f"Plano: criar a placa {name} com {length:g} × {width:g} × "
                f"{thickness:g} mm, recalcular e validar antes de confirmar."
            ),
            "cad.create_plate",
            {
                "length": length,
                "width": width,
                "thickness": thickness,
                "name": name,
            },
        )

    return ChatCommand(
        "Não reconheci esse pedido no modo local seguro.<br>" + HELP_TEXT
    )


def format_tool_result(tool_name: str, result: Any) -> str:
    if tool_name == "cad.get_document_summary":
        if not result["active"]:
            return "Nenhum documento CAD está ativo. Crie uma peça para iniciar."
        objects = result["objects"]
        object_word = "objeto" if len(objects) == 1 else "objetos"
        document_label = escape(str(result["label"]))
        return (
            f"Documento <b>{document_label}</b>: {len(objects)} {object_word}, "
            f"{sum(item['has_error'] for item in objects)} com erro."
        )
    if tool_name == "cad.get_selection":
        selection = result["selection"]
        if not selection:
            return "Nenhum objeto, face ou aresta está selecionado."
        names = ", ".join(escape(str(item["label"])) for item in selection)
        return f"Seleção atual ({len(selection)}): {names}."
    if tool_name == "cad.get_context_snapshot":
        if not result["active"]:
            return "Nenhum documento CAD está ativo para formar o contexto."
        summary = result["summary"]
        label = escape(str(result["document_label"]))
        recent = result["recent_objects"]
        recent_text = (
            "; recentes: " + ", ".join(escape(str(name)) for name in recent)
            if recent
            else ""
        )
        return (
            f"Contexto <b>{label}</b>, revisão "
            f"{result['state_token']['revision']}: "
            f"{summary['object_count']} objetos, "
            f"{summary['selected_count']} selecionados, "
            f"{summary['error_count']} com erro{recent_text}."
        )
    if tool_name == "cad.resolve_object":
        if result["status"] == "awaiting_selection":
            return "Selecione exatamente um objeto no FreeCAD para continuar."
        if result["status"] == "not_found":
            return "Não encontrei um objeto correspondente à referência informada."
        item = result["object"]
        return (
            f"Objeto resolvido: <b>{escape(str(item['label']))}</b> "
            f"(<code>{escape(str(item['name']))}</code>)."
        )
    if tool_name == "cad.measure_object":
        return (
            f"<b>{escape(str(result['label']))}</b>: "
            f"{result['length_mm']:g} × {result['width_mm']:g} × "
            f"{result['height_mm']:g} mm; volume {result['volume_mm3']:g} mm³."
        )
    if tool_name == "cad.get_object_details":
        item = result["object"]
        return (
            f"Detalhes de <b>{escape(str(item['label']))}</b>: "
            f"{len(result['editable_parameters'])} parâmetros editáveis e "
            f"{len(result['edge_references'])} referências geométricas de aresta."
        )
    if tool_name == "cad.get_dependencies":
        return (
            f"Relações de <code>{escape(str(result['name']))}</code>: "
            f"depende de {len(result['depends_on'])} e é usado por "
            f"{len(result['used_by'])} objetos."
        )
    if tool_name == "cad.get_editable_parameters":
        names = ", ".join(
            escape(str(item["name"])) for item in result["parameters"]
        ) or "nenhum"
        return f"Parâmetros editáveis de <b>{escape(str(result['label']))}</b>: {names}."
    if tool_name == "cad.capture_view":
        return (
            "Vista 3D capturada no cache local seguro: "
            f"<code>{escape(str(result['capture_id']))}</code>."
        )
    if tool_name == "cad.create_box":
        dimensions = " × ".join(f"{value:g}" for value in result["dimensions_mm"])
        label = escape(str(result["label"]))
        return (
            f"Caixa <b>{label}</b> criada e validada "
            f"({dimensions} mm; volume {result['volume_mm3']:g} mm³). "
            "A operação pode ser desfeita."
        )
    if tool_name == "cad.create_cylinder":
        label = escape(str(result["label"]))
        return (
            f"Cilindro <b>{label}</b> criado e validado "
            f"(diâmetro {result['diameter_mm']:g} mm × "
            f"altura {result['height_mm']:g} mm; "
            f"volume {result['volume_mm3']:g} mm³; eixo Z). "
            "A operação pode ser desfeita."
        )
    mechanical_actions = {
        "cad.rename_object": "Objeto renomeado",
        "cad.set_parameter": "Parâmetro alterado",
        "cad.transform_object": "Objeto transformado",
        "cad.create_plate": "Placa criada",
        "cad.create_through_hole": "Furo passante criado",
        "cad.create_rectangular_hole_pattern": "Padrão retangular criado",
        "cad.create_circular_hole_pattern": "Padrão circular criado",
        "cad.create_rectangular_sketch": "Sketch retangular criado",
        "cad.pad_sketch": "Pad criado",
        "cad.boolean_operation": "Operação booleana concluída",
        "cad.fillet_edges": "Filete criado",
        "cad.chamfer_edges": "Chanfro criado",
    }
    if tool_name in mechanical_actions:
        label = escape(str(result.get("label", result.get("name", "objeto"))))
        return (
            f"{mechanical_actions[tool_name]} em <b>{label}</b>, "
            "validado e reversível por undo."
        )
    if tool_name == "cad.validate_document":
        if result["valid"]:
            return "Documento recalculado e validado sem erros."
        errors = "; ".join(escape(str(error)) for error in result["errors"])
        return "Falha de validação: " + errors
    if tool_name == "cad.undo":
        if result["undone"]:
            return "A última transação CAD foi desfeita e o documento foi recalculado."
        return "Não há uma transação CAD disponível para desfazer."
    return "Ferramenta concluída."

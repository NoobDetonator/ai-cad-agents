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
    "• <code>validar</code> — recalcula e verifica o documento<br>"
    "• <code>caixa 10 x 20 x 30 nome MinhaCaixa</code> — prepara uma caixa em mm<br>"
    "• <code>cilindro 30 x 60 nome Eixo</code> — prepara um cilindro por "
    "diâmetro × altura em mm<br>"
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

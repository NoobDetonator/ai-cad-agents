from __future__ import annotations

from aicad.core.tool_catalog.schemas import (
    DELETION_RESULT,
    NAME,
    NUMBER,
    OBJECT_RESULT,
    REFERENCE,
    _object_schema,
    _spec,
)
from aicad.core.tool_registry import ToolRisk, ToolSpec


def object_tool_specs() -> tuple[ToolSpec, ...]:
    """Return safe object lifecycle tool specifications."""

    return (
        _spec(
            "cad.duplicate_object",
            "Create an independent shape copy with a new name. Optional x/y/z "
            "offsets are relative global millimeter deltas; the duplicate keeps "
            "the source orientation and has no parametric link to the source.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "object": REFERENCE,
                    "name": NAME,
                    "offset_x": NUMBER,
                    "offset_y": NUMBER,
                    "offset_z": NUMBER,
                },
                ("object", "name"),
            ),
            family="object",
            aliases=(
                "duplicar objeto",
                "duplique",
                "copiar peça",
                "faça uma cópia",
                "duplicate object",
                "copy part",
            ),
            tags=("cópia", "independente", "duplicar", "copy", "independent"),
            examples=("Duplique a Base como BaseDireita e desloque 40 mm em X.",),
            order=142,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.delete_object",
            "Delete one object transactionally. Refuse deletion when another "
            "document object depends on it; there is no force or cascade mode.",
            ToolRisk.MODIFY,
            _object_schema({"object": REFERENCE}, ("object",)),
            family="object",
            aliases=(
                "apagar objeto",
                "apague",
                "excluir peça",
                "exclua",
                "delete object",
                "remove part",
            ),
            tags=("apagar", "excluir", "dependência", "delete", "remove", "dependency"),
            examples=("Apague o objeto Rascunho se ele não estiver sendo usado.",),
            order=144,
            output_schema=DELETION_RESULT,
        ),
    )

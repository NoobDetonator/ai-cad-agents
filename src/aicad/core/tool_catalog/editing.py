from __future__ import annotations

from aicad.core.tool_catalog.schemas import (
    NAME,
    NUMBER,
    OBJECT_RESULT,
    PLACEMENT_RESULT,
    REFERENCE,
    _object_schema,
    _spec,
)
from aicad.core.tool_registry import ToolRisk, ToolSpec


def editing_tool_specs() -> tuple[ToolSpec, ...]:
    """Return the editing CAD tool specifications."""

    return (
        _spec(
            "cad.rename_object",
            "Rename one object. The new name must start with a letter and use "
            "only letters, digits, underscore or hyphen.",
            ToolRisk.MODIFY,
            _object_schema({"object": REFERENCE, "name": NAME}, ("object", "name")),
            family="edit",
            aliases=("renomear", "renomeie", "mudar nome", "rename object"),
            tags=("nome", "rótulo", "label", "rename", "edit"),
            examples=("Renomeie Box para Base.",),
            order=120,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.set_parameter",
            "Set one numeric parameter listed by cad.get_editable_parameters "
            "(millimeters or degrees) and validate the resulting shape.",
            ToolRisk.MODIFY,
            _object_schema(
                {"object": REFERENCE, "parameter": REFERENCE, "value": NUMBER},
                ("object", "parameter", "value"),
            ),
            family="edit",
            aliases=("alterar parâmetro", "mudar dimensão", "set parameter"),
            tags=(
                "parâmetro",
                "valor",
                "comprimento",
                "largura",
                "altura",
                "raio",
                "parameter",
                "dimension",
            ),
            examples=("Altere a altura da Base para 12 mm.",),
            order=130,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.transform_object",
            "Set an object's ABSOLUTE placement: x/y/z in millimeters replace "
            "the position (omitted axes keep their value); any of roll/pitch/"
            "yaw in degrees replaces the whole rotation. Values are not "
            "relative deltas; read the current placement first.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "object": REFERENCE,
                    "x": NUMBER,
                    "y": NUMBER,
                    "z": NUMBER,
                    "roll": NUMBER,
                    "pitch": NUMBER,
                    "yaw": NUMBER,
                },
                ("object",),
            ),
            family="edit",
            aliases=("mover", "rotacionar", "transformar", "move", "rotate"),
            tags=("posição", "rotação", "eixo", "placement", "transform"),
            examples=("Mova a Base 20 mm no eixo X.",),
            order=140,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.translate_object",
            "Move an object RELATIVELY along global axes by dx/dy/dz in "
            "millimeters. At least one delta must be non-zero.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "object": REFERENCE,
                    "dx": NUMBER,
                    "dy": NUMBER,
                    "dz": NUMBER,
                },
                ("object",),
            ),
            family="edit",
            aliases=(
                "deslocar objeto",
                "desloque",
                "mover relativamente",
                "translate object",
                "move by",
            ),
            tags=("deslocamento", "delta", "relativo", "translate", "relative"),
            examples=("Desloque a Tampa 20 mm em X e 5 mm em Z.",),
            order=146,
            output_schema=PLACEMENT_RESULT,
        ),
        _spec(
            "cad.rotate_object",
            "Rotate an object RELATIVELY around global X, Y or Z by a non-zero "
            "angle in degrees, using either the object's bounding-box center or "
            "the global origin as pivot.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "object": REFERENCE,
                    "axis": {"type": "string", "enum": ["x", "y", "z"]},
                    "angle": {"type": "number", "minimum": -360, "maximum": 360},
                    "pivot": {
                        "type": "string",
                        "enum": ["object_center", "global_origin"],
                    },
                },
                ("object", "axis", "angle"),
            ),
            family="edit",
            aliases=(
                "girar objeto",
                "gire",
                "rotacionar relativamente",
                "rotacione",
                "rotate object",
                "rotate by",
            ),
            tags=("rotação", "ângulo", "pivô", "relativo", "rotation", "pivot"),
            examples=("Gire a Tampa 90 graus em Z ao redor do próprio centro.",),
            order=148,
            output_schema=PLACEMENT_RESULT,
        ),
    )

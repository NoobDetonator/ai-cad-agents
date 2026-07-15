from __future__ import annotations

from aicad.core.tool_catalog.schemas import (
    NAME,
    NON_NEGATIVE,
    OBJECT_RESULT,
    POSITIVE,
    _object_schema,
    _spec,
)
from aicad.core.tool_registry import ToolRisk, ToolSpec


def primitive_tool_specs() -> tuple[ToolSpec, ...]:
    """Return the primitives CAD tool specifications."""

    return (
        ToolSpec(
            name="cad.create_box",
            description=(
                "Create a parametric box at the global origin: length along "
                "X, width along Y, height along Z, in millimeters."
            ),
            risk=ToolRisk.MODIFY,
            input_schema={
                "type": "object",
                "properties": {
                    "length": {"type": "number", "exclusiveMinimum": 0},
                    "width": {"type": "number", "exclusiveMinimum": 0},
                    "height": {"type": "number", "exclusiveMinimum": 0},
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 64,
                        "pattern": "[A-Za-z][A-Za-z0-9_-]*",
                    },
                },
                "required": ["length", "width", "height"],
                "additionalProperties": False,
            },
            family="primitive",
            aliases=(
                "caixa",
                "bloco retangular",
                "cubo",
                "box",
                "rectangular block",
                "cube",
            ),
            tags=(
                "comprimento",
                "largura",
                "altura",
                "length",
                "width",
                "height",
                "criar",
                "create",
            ),
            examples=(
                "Crie uma caixa 10 x 20 x 30.",
                "Create a box with length, width and height.",
            ),
            canonical_order=100,
        ),
        ToolSpec(
            name="cad.create_cylinder",
            description=(
                "Create a vertical parametric cylinder based at the global "
                "origin, aligned with the Z axis, from its diameter and "
                "height in millimeters."
            ),
            risk=ToolRisk.MODIFY,
            input_schema={
                "type": "object",
                "properties": {
                    "diameter": {"type": "number", "exclusiveMinimum": 0},
                    "height": {"type": "number", "exclusiveMinimum": 0},
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 64,
                        "pattern": "[A-Za-z][A-Za-z0-9_-]*",
                    },
                },
                "required": ["diameter", "height"],
                "additionalProperties": False,
            },
            family="primitive",
            aliases=(
                "cilindro",
                "eixo vertical",
                "pino",
                "cylinder",
                "vertical shaft",
                "pin",
            ),
            tags=(
                "diâmetro",
                "diametro",
                "raio",
                "altura",
                "diameter",
                "radius",
                "height",
                "criar",
                "create",
            ),
            examples=(
                "Modele um eixo vertical de 16 mm de diâmetro.",
                "Create a cylinder with diameter and height.",
            ),
            canonical_order=110,
        ),
        _spec(
            "cad.create_cone",
            "Create a parametric cone or truncated cone at the global origin, "
            "aligned with +Z. Diameters are in millimeters; at least one end "
            "diameter must be greater than zero.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "bottom_diameter": NON_NEGATIVE,
                    "top_diameter": NON_NEGATIVE,
                    "height": POSITIVE,
                    "name": NAME,
                },
                ("bottom_diameter", "top_diameter", "height"),
            ),
            family="primitive",
            aliases=("cone", "tronco de cone", "conical frustum", "create cone"),
            tags=("cone", "cônico", "afunilado", "frustum", "conical", "tapered"),
            examples=("Crie um cone de base 30 mm e altura 50 mm.",),
            order=112,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_sphere",
            "Create a complete parametric sphere centered at the global origin "
            "from its diameter in millimeters.",
            ToolRisk.MODIFY,
            _object_schema(
                {"diameter": POSITIVE, "name": NAME},
                ("diameter",),
            ),
            family="primitive",
            aliases=("esfera", "bola", "sphere", "ball"),
            tags=("esfera", "esférico", "bola", "sphere", "spherical", "ball"),
            examples=("Crie uma esfera de 24 mm de diâmetro.",),
            order=114,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_torus",
            "Create a complete parametric torus centered at the global origin and "
            "aligned with Z. The major diameter must exceed the tube diameter.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "major_diameter": POSITIVE,
                    "tube_diameter": POSITIVE,
                    "name": NAME,
                },
                ("major_diameter", "tube_diameter"),
            ),
            family="primitive",
            aliases=("toro", "rosquinha", "torus", "donut"),
            tags=("toro", "anel", "diâmetro maior", "torus", "ring", "tube"),
            examples=("Crie um toro de diâmetro principal 40 mm e tubo 8 mm.",),
            order=116,
            output_schema=OBJECT_RESULT,
        ),
    )

from __future__ import annotations

from aicad.core.tool_catalog.schemas import (
    INTEGER,
    NAME,
    NUMBER,
    OBJECT_RESULT,
    POSITIVE,
    REFERENCE,
    _object_schema,
    _spec,
)
from aicad.core.tool_registry import ToolRisk, ToolSpec


def pattern_tool_specs() -> tuple[ToolSpec, ...]:
    """Return the patterns CAD tool specifications."""

    return (
        _spec(
            "cad.create_rectangular_hole_pattern",
            "Cut a grid of vertical through holes: the first hole is at GLOBAL "
            "coordinates origin_x, origin_y and the grid extends by "
            "spacing_x along +X per column and spacing_y along +Y per row, "
            "all in millimeters. Maximum 64 holes.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "object": REFERENCE,
                    "diameter": POSITIVE,
                    "rows": INTEGER,
                    "columns": INTEGER,
                    "spacing_x": POSITIVE,
                    "spacing_y": POSITIVE,
                    "origin_x": NUMBER,
                    "origin_y": NUMBER,
                    "name": NAME,
                },
                (
                    "object",
                    "diameter",
                    "rows",
                    "columns",
                    "spacing_x",
                    "spacing_y",
                    "origin_x",
                    "origin_y",
                ),
            ),
            family="pattern",
            aliases=("padrão retangular de furos", "grade de furos", "rectangular pattern"),
            tags=("linhas", "colunas", "espaçamento", "rows", "columns", "holes"),
            examples=("Faça quatro furos em uma grade 2 por 2.",),
            order=170,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_circular_hole_pattern",
            "Cut vertical through holes equally spaced on a circle CENTERED ON "
            "THE OBJECT'S bounding-box center, with pitch_diameter in "
            "millimeters and start_angle in degrees from the +X axis. "
            "Maximum 64 holes.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "object": REFERENCE,
                    "diameter": POSITIVE,
                    "count": INTEGER,
                    "pitch_diameter": POSITIVE,
                    "start_angle": NUMBER,
                    "name": NAME,
                },
                ("object", "diameter", "count", "pitch_diameter"),
            ),
            family="pattern",
            aliases=("padrão circular de furos", "círculo de furos", "bolt circle"),
            tags=("flange", "circular", "parafusos", "bolt", "circle", "holes"),
            examples=("Faça seis furos em um círculo de passo de 80 mm.",),
            order=180,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.mirror_object",
            "Mirror one solid across a global plane through the origin (xy, yz "
            "or xz) into a new derived solid linked to the source. Good for "
            "left/right symmetric parts.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "object": REFERENCE,
                    "plane": {"type": "string", "enum": ["xy", "yz", "xz"]},
                    "name": NAME,
                },
                ("object",),
            ),
            family="pattern",
            aliases=("espelhar", "espelhamento", "mirror", "mirror object"),
            tags=(
                "espelho",
                "espelhe",
                "espelhado",
                "simetria",
                "espelhar",
                "mirror",
                "symmetry",
            ),
            examples=(
                "Espelhe o suporte no plano YZ.",
                "Mirror the bracket across the xz plane.",
            ),
            order=250,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.linear_pattern",
            "Copy one solid into a linear array of count instances spaced by "
            "spacing millimeters along a global axis (x, y or z), stored in "
            "one derived feature. Disconnected instances remain separate solids "
            "inside that feature. Maximum 64 instances.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "object": REFERENCE,
                    "count": {"type": "integer", "minimum": 2, "maximum": 64},
                    "spacing": POSITIVE,
                    "direction": {"type": "string", "enum": ["x", "y", "z"]},
                    "name": NAME,
                },
                ("object", "count", "spacing"),
            ),
            family="pattern",
            aliases=(
                "padrão linear",
                "repetição linear",
                "linear pattern",
                "linear array",
            ),
            tags=(
                "padrão",
                "repetir",
                "repita",
                "vezes",
                "linear",
                "array",
                "cópias",
                "pattern",
                "repeat",
            ),
            examples=(
                "Repita a nervura seis vezes a cada 20 mm no eixo X.",
                "Make a linear pattern of 4 copies spaced 15 mm.",
            ),
            order=252,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.polar_pattern",
            "Copy one solid into a polar array of count instances spread over "
            "angle degrees around a global axis (x, y or z) through the "
            "origin, stored in one derived feature. Disconnected instances remain "
            "separate solids inside that feature. A full 360 steps evenly; "
            "a smaller angle spreads the copies across the arc. Maximum 64 "
            "instances.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "object": REFERENCE,
                    "count": {"type": "integer", "minimum": 2, "maximum": 64},
                    "angle": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "maximum": 360,
                    },
                    "axis": {"type": "string", "enum": ["x", "y", "z"]},
                    "name": NAME,
                },
                ("object", "count"),
            ),
            family="pattern",
            aliases=(
                "padrão polar",
                "padrão circular",
                "repetição polar",
                "polar pattern",
                "circular pattern",
            ),
            tags=(
                "padrão",
                "polar",
                "circular",
                "revolução",
                "ao redor",
                "pattern",
                "polar",
                "around",
            ),
            examples=(
                "Distribua a pá em um padrão polar de 8 ao redor do eixo Z.",
                "Make a polar pattern of 6 copies over 360 degrees.",
            ),
            order=254,
            output_schema=OBJECT_RESULT,
        ),
    )

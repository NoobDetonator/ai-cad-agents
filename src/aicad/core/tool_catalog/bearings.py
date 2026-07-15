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


ELEMENT_COUNT = {"type": "integer", "minimum": 4, "maximum": 64}
GROOVE_CONFORMITY = {"type": "number", "minimum": 1.0, "maximum": 1.25}


def bearing_tool_specs() -> tuple[ToolSpec, ...]:
    """Return conventional and additive-manufacturing bearing tools."""

    return (
        _spec(
            "cad.create_deep_groove_ball_bearing",
            "Create an open single-row deep-groove radial ball bearing with "
            "toroidal raceway grooves, balls and an optional connected cage "
            "with two axial rails and posts between the balls. "
            "It supports explicit radial clearance and groove conformity.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "bore_diameter": POSITIVE,
                    "outer_diameter": POSITIVE,
                    "width": POSITIVE,
                    "ball_count": ELEMENT_COUNT,
                    "ball_diameter": POSITIVE,
                    "radial_clearance": NON_NEGATIVE,
                    "groove_conformity": GROOVE_CONFORMITY,
                    "cage": {"type": "boolean"},
                    "name": NAME,
                },
                (
                    "bore_diameter",
                    "outer_diameter",
                    "width",
                    "ball_count",
                    "ball_diameter",
                ),
            ),
            family="bearing",
            aliases=(
                "rolamento rigido de esferas",
                "rolamento de esferas com pistas profundas",
                "deep groove ball bearing",
                "radial ball bearing",
            ),
            tags=(
                "rolamento",
                "radial",
                "pista profunda",
                "gaiola",
                "bearing",
                "raceway",
                "cage",
            ),
            examples=(
                "Crie um rolamento rígido 12 x 32 x 10 com oito esferas e gaiola.",
            ),
            order=270,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_thrust_ball_bearing",
            "Create a separable single-direction thrust ball bearing along Z: "
            "two grooved washers, balls and an optional cage. It is intended "
            "for axial rather than radial load.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "bore_diameter": POSITIVE,
                    "outer_diameter": POSITIVE,
                    "height": POSITIVE,
                    "ball_count": ELEMENT_COUNT,
                    "ball_diameter": POSITIVE,
                    "axial_clearance": NON_NEGATIVE,
                    "groove_conformity": GROOVE_CONFORMITY,
                    "cage": {"type": "boolean"},
                    "name": NAME,
                },
                (
                    "bore_diameter",
                    "outer_diameter",
                    "height",
                    "ball_count",
                    "ball_diameter",
                ),
            ),
            family="bearing",
            aliases=(
                "rolamento axial de esferas",
                "rolamento de encosto",
                "thrust ball bearing",
                "axial bearing",
            ),
            tags=("rolamento", "axial", "arruela", "encosto", "thrust", "washer"),
            examples=(
                "Crie um rolamento axial 20 x 42 x 14 mm para carga no eixo Z.",
            ),
            order=272,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_cylindrical_roller_bearing",
            "Create a radial cylindrical-roller bearing with inner and outer "
            "races, explicit roller length, radial clearance and an optional "
            "connected two-rail cage.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "bore_diameter": POSITIVE,
                    "outer_diameter": POSITIVE,
                    "width": POSITIVE,
                    "roller_count": ELEMENT_COUNT,
                    "roller_diameter": POSITIVE,
                    "roller_length": POSITIVE,
                    "radial_clearance": NON_NEGATIVE,
                    "cage": {"type": "boolean"},
                    "name": NAME,
                },
                (
                    "bore_diameter",
                    "outer_diameter",
                    "width",
                    "roller_count",
                    "roller_diameter",
                    "roller_length",
                ),
            ),
            family="bearing",
            aliases=(
                "rolamento de rolos cilindricos",
                "rolamento de roletes",
                "cylindrical roller bearing",
                "roller bearing",
            ),
            tags=("rolamento", "rolo", "carga radial", "roller", "radial load", "cage"),
            examples=(
                "Crie um rolamento de rolos 20 x 47 x 14 com doze rolos de 6 x 11 mm.",
            ),
            order=274,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_print_in_place_roller_bearing",
            "Create a captured cylindrical-roller bearing for upright print-in-place "
            "additive manufacturing. Separate radial and axial print clearances "
            "and 45-degree retaining rims reduce fusion and unsupported overhangs. "
            "Clearance must be calibrated for the selected printer and material.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "bore_diameter": POSITIVE,
                    "outer_diameter": POSITIVE,
                    "width": POSITIVE,
                    "roller_count": ELEMENT_COUNT,
                    "roller_diameter": POSITIVE,
                    "print_clearance": POSITIVE,
                    "axial_clearance": POSITIVE,
                    "name": NAME,
                },
                (
                    "bore_diameter",
                    "outer_diameter",
                    "width",
                    "roller_count",
                    "roller_diameter",
                ),
            ),
            family="bearing",
            aliases=(
                "rolamento impresso no lugar",
                "rolamento para impressao 3d",
                "print in place bearing",
                "3d printed roller bearing",
            ),
            tags=(
                "impressao 3d",
                "fdm",
                "folga de impressao",
                "print-in-place",
                "additive",
                "clearance",
            ),
            examples=(
                "Crie um rolamento print-in-place com folga de impressão de 0,4 mm.",
            ),
            order=276,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_printed_plain_bushing",
            "Create an upright-printable polymer plain bushing with explicit "
            "shaft running clearance, axial lubrication or debris channels and "
            "a bottom elephant-foot bore relief.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "shaft_diameter": POSITIVE,
                    "outer_diameter": POSITIVE,
                    "length": POSITIVE,
                    "running_clearance": POSITIVE,
                    "channel_count": {"type": "integer", "minimum": 0, "maximum": 24},
                    "channel_width": POSITIVE,
                    "channel_depth": POSITIVE,
                    "elephant_foot_relief": NON_NEGATIVE,
                    "name": NAME,
                },
                ("shaft_diameter", "outer_diameter", "length"),
            ),
            family="bearing",
            aliases=(
                "bucha impressa",
                "mancal de deslizamento impresso",
                "printed plain bushing",
                "3d printed sleeve bearing",
            ),
            tags=(
                "bucha",
                "polimero",
                "canal de lubrificacao",
                "elephant foot",
                "plain bearing",
                "sleeve",
            ),
            examples=(
                "Crie uma bucha impressa para eixo de 12 mm com 0,3 mm de folga.",
            ),
            order=278,
            output_schema=OBJECT_RESULT,
        ),
    )

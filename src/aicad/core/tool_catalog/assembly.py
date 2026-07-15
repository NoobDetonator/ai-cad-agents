from __future__ import annotations

from aicad.core.tool_catalog.schemas import (
    INTERFERENCE_RESULT,
    NAME,
    NON_NEGATIVE,
    OBJECT_RESULT,
    PLACEMENT_RESULT,
    POSITIVE,
    REFERENCE,
    _object_schema,
    _spec,
)
from aicad.core.tool_registry import ToolRisk, ToolSpec


def assembly_tool_specs() -> tuple[ToolSpec, ...]:
    """Return reusable mechanical assembly and verification tools."""

    return (
        _spec(
            "cad.create_planetary_carrier",
            "Create a circular planetary carrier plate centered at the global "
            "origin and extruded along +Z. It has a center bore and an evenly "
            "spaced circle of planet-pin holes. All dimensions are millimeters.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "plate_diameter": POSITIVE,
                    "thickness": POSITIVE,
                    "center_bore_diameter": NON_NEGATIVE,
                    "planet_count": {"type": "integer", "minimum": 2, "maximum": 16},
                    "planet_pitch_diameter": POSITIVE,
                    "pin_hole_diameter": POSITIVE,
                    "name": NAME,
                },
                (
                    "plate_diameter",
                    "thickness",
                    "center_bore_diameter",
                    "planet_count",
                    "planet_pitch_diameter",
                    "pin_hole_diameter",
                ),
            ),
            family="assembly",
            aliases=("porta planetas", "porta-planetas", "planet carrier"),
            tags=("planetario", "pinos", "carrier", "planet", "pins"),
            examples=(
                "Crie um porta-planetas de 90 mm com três pinos em círculo de 72 mm.",
            ),
            order=260,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_ball_bearing",
            "Create a radial ball-bearing assembly centered at the global "
            "origin: inner race, outer race and evenly spaced balls. The result "
            "is one validated compound with explicit radial clearance.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "bore_diameter": POSITIVE,
                    "outer_diameter": POSITIVE,
                    "width": POSITIVE,
                    "ball_count": {"type": "integer", "minimum": 4, "maximum": 64},
                    "ball_diameter": POSITIVE,
                    "radial_clearance": NON_NEGATIVE,
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
            family="assembly",
            aliases=("rolamento", "rolamento de esferas", "ball bearing", "bearing"),
            tags=("pista", "esferas", "eixo", "race", "balls", "shaft"),
            examples=("Crie um rolamento 12 x 32 x 10 mm com oito esferas.",),
            order=262,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.apply_gear_backlash",
            "Create a derived gear with thinner teeth by intersecting two small "
            "angular offsets around its axis. backlash is tangential clearance "
            "at the pitch circle in millimeters; the source must expose gear "
            "module and tooth-count metadata.",
            ToolRisk.MODIFY,
            _object_schema(
                {"object": REFERENCE, "backlash": POSITIVE, "name": NAME},
                ("object", "backlash", "name"),
            ),
            family="assembly",
            aliases=("aplicar folga", "folga engrenagem", "gear backlash"),
            tags=("folga", "dentes", "tolerancia", "backlash", "teeth", "clearance"),
            examples=("Aplique 0,12 mm de backlash na engrenagem PlanetGear.",),
            order=264,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.align_concentric",
            "Align the XY axes of a moving solid to a reference solid, preserving "
            "its rotation. z_alignment may match base, center or top planes and "
            "axial_offset adds a signed Z distance in millimeters. This is a "
            "transactional placement constraint, not a live solver relation.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "moving": REFERENCE,
                    "reference": REFERENCE,
                    "z_alignment": {"type": "string", "enum": ["base", "center", "top"]},
                    "axial_offset": {"type": "number"},
                },
                ("moving", "reference"),
            ),
            family="assembly",
            aliases=(
                "alinhar concentricamente",
                "alinhe concentricamente",
                "concentrico",
                "concentric alignment",
                "concentrically align the bearing",
                "align bearing with shaft axis",
            ),
            tags=(
                "montagem",
                "eixo",
                "alinhamento",
                "concêntrico",
                "assembly",
                "axis",
                "alignment",
            ),
            examples=("Alinhe o rolamento concentricamente ao eixo pela base."),
            order=266,
            output_schema=PLACEMENT_RESULT,
        ),
        _spec(
            "cad.analyze_interferences",
            "Analyze every pair in an explicit object list. Reports true common "
            "volume, contact and requested minimum-clearance violations without "
            "changing the document. volume_tolerance filters microscopic kernel "
            "slivers in cubic millimeters.",
            ToolRisk.READ,
            _object_schema(
                {
                    "objects": {
                        "type": "array",
                        "items": REFERENCE,
                        "minItems": 2,
                        "maxItems": 32,
                        "uniqueItems": True,
                    },
                    "minimum_clearance": NON_NEGATIVE,
                    "volume_tolerance": NON_NEGATIVE,
                },
                ("objects",),
            ),
            family="analysis",
            aliases=(
                "analisar interferencias",
                "analise interferências",
                "verificar colisões",
                "interference analysis",
            ),
            tags=(
                "interferências",
                "colisao",
                "contato",
                "folga",
                "collision",
                "contact",
                "clearance",
            ),
            examples=("Analise interferências entre eixo, rolamento e carcaça."),
            order=268,
            output_schema=INTERFERENCE_RESULT,
        ),
    )

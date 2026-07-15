from __future__ import annotations

from aicad.core.tool_catalog.schemas import (
    NAME,
    OBJECT_RESULT,
    POSITIVE,
    _object_schema,
    _spec,
)
from aicad.core.tool_registry import ToolRisk, ToolSpec


def mechanical_part_tool_specs() -> tuple[ToolSpec, ...]:
    """Return the mechanical CAD tool specifications."""

    return (
        _spec(
            "cad.create_plate",
            "Create a rectangular plate with its MINIMUM CORNER at the global "
            "origin: it spans 0..length in X, 0..width in Y and "
            "0..thickness in Z, in millimeters. Corner-anchored, unlike "
            "cad.create_cylinder, which centres its axis on the origin.",
            ToolRisk.MODIFY,
            _object_schema(
                {"length": POSITIVE, "width": POSITIVE, "thickness": POSITIVE, "name": NAME},
                ("length", "width", "thickness"),
            ),
            family="mechanical",
            aliases=("placa", "chapa", "plate", "sheet"),
            tags=("comprimento", "largura", "espessura", "plate", "thickness"),
            examples=("Crie uma placa 100 x 60 x 8 mm.",),
            order=150,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_spur_gear",
            "Create an external involute spur gear centered at the global "
            "origin, extruded along +Z by thickness millimeters. Pitch "
            "diameter = module * teeth (mm); mesh two gears by spacing "
            "their centers at the sum of pitch radii and phasing one by the "
            "mesh_phase_deg returned here (half an angular pitch). "
            "bore_diameter 0 means solid; pressure_angle and phase are in "
            "degrees.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "teeth": {"type": "integer", "minimum": 6, "maximum": 200},
                    "module": {"type": "number", "exclusiveMinimum": 0},
                    "thickness": {"type": "number", "exclusiveMinimum": 0},
                    "bore_diameter": {"type": "number", "minimum": 0},
                    "pressure_angle": {
                        "type": "number",
                        "minimum": 14.5,
                        "maximum": 25,
                    },
                    "phase": {"type": "number", "minimum": -360, "maximum": 360},
                    "name": NAME,
                },
                ("teeth", "module", "thickness", "bore_diameter"),
            ),
            family="mechanical",
            aliases=("engrenagem reta", "engrenagem", "spur gear", "involute gear"),
            tags=("dentes", "módulo", "involuta", "gear", "teeth", "module"),
            examples=(
                "Crie uma engrenagem de 20 dentes, módulo 2 e 8 mm de espessura.",
            ),
            order=240,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_helical_gear",
            "Create an external involute helical gear centered at the global "
            "origin, extruded along +Z with a controlled twist. helix_angle "
            "is in degrees (1 to 45, sign sets hand); mesh two helical gears "
            "by using opposite signs, the same module and phasing one by the "
            "returned mesh_phase_deg. Pitch diameter = module * teeth (mm); "
            "bore_diameter 0 means solid; phase is in degrees.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "teeth": {"type": "integer", "minimum": 6, "maximum": 200},
                    "module": {"type": "number", "exclusiveMinimum": 0},
                    "thickness": {"type": "number", "exclusiveMinimum": 0},
                    "helix_angle": {
                        "type": "number",
                        "minimum": -45,
                        "maximum": 45,
                    },
                    "bore_diameter": {"type": "number", "minimum": 0},
                    "pressure_angle": {
                        "type": "number",
                        "minimum": 14.5,
                        "maximum": 25,
                    },
                    "phase": {"type": "number", "minimum": -360, "maximum": 360},
                    "name": NAME,
                },
                ("teeth", "module", "thickness", "helix_angle", "bore_diameter"),
            ),
            family="mechanical",
            aliases=(
                "engrenagem helicoidal",
                "helicoidal",
                "helical gear",
            ),
            tags=("dentes", "módulo", "hélice", "gear", "helix", "helical"),
            examples=(
                "Crie uma engrenagem helicoidal de 24 dentes, módulo 2, "
                "hélice de 15 graus.",
            ),
            order=242,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_external_thread",
            "Create an external ISO-style 60-degree thread as a solid: a "
            "core cylinder with a swept helical ridge, based at the global "
            "origin along +Z. diameter is the nominal major diameter, pitch "
            "and length in millimeters (e.g. M8x1.25: diameter 8, pitch "
            "1.25). Maximum 64 turns. Meant for 3D printing; join it to a "
            "part with cad.boolean_operation fuse.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "diameter": POSITIVE,
                    "pitch": POSITIVE,
                    "length": POSITIVE,
                    "name": NAME,
                },
                ("diameter", "pitch", "length"),
            ),
            family="mechanical",
            aliases=("rosca externa", "rosca", "external thread", "thread"),
            tags=("rosca", "parafuso", "passo", "thread", "screw", "pitch"),
            examples=("Crie uma rosca M8 com passo 1.25 e 20 mm de comprimento.",),
            order=244,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_internal_gear",
            "Create a true internal involute ring gear centered at the global "
            "origin and extruded along +Z. Pitch diameter = module * teeth; "
            "rim_thickness extends radially outside the tooth root. pressure_angle "
            "and phase are degrees.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "teeth": {"type": "integer", "minimum": 12, "maximum": 240},
                    "module": POSITIVE,
                    "thickness": POSITIVE,
                    "rim_thickness": POSITIVE,
                    "pressure_angle": {
                        "type": "number",
                        "minimum": 14.5,
                        "maximum": 25,
                    },
                    "phase": {"type": "number", "minimum": -360, "maximum": 360},
                    "name": NAME,
                },
                ("teeth", "module", "thickness", "rim_thickness"),
            ),
            family="mechanical",
            aliases=("engrenagem interna", "coroa interna", "internal gear", "ring gear"),
            tags=("dentes internos", "planetario", "coroa", "internal teeth", "planetary"),
            examples=("Crie uma coroa interna de 48 dentes, módulo 2 e 12 mm de largura."),
            order=246,
            output_schema=OBJECT_RESULT,
        ),
    )

from __future__ import annotations

from aicad.core.tool_catalog.schemas import (
    NAME,
    NUMBER,
    OBJECT_RESULT,
    POSITIVE,
    REFERENCE,
    _object_schema,
    _spec,
)
from aicad.core.tool_registry import ToolRisk, ToolSpec


def modeling_tool_specs() -> tuple[ToolSpec, ...]:
    """Return the modeling CAD tool specifications."""

    return (
        _spec(
            "cad.create_through_hole",
            "Cut one vertical through hole (along Z, through the full solid) at "
            "GLOBAL document coordinates x, y in millimeters. Diameter in "
            "millimeters. The result is a new derived object linked to the "
            "source. WARNING: by default the cutter spans the whole solid's Z "
            "extent, so on a fused body it drills EVERY feature sharing that "
            "(x, y) column, not just the one you mean. To confine the hole to "
            "one feature (for example boring only a raised boss), pass z_min "
            "and z_max: the cutter then spans exactly that window.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "object": REFERENCE,
                    "diameter": POSITIVE,
                    "x": NUMBER,
                    "y": NUMBER,
                    "name": NAME,
                    "z_min": NUMBER,
                    "z_max": NUMBER,
                },
                ("object", "diameter", "x", "y"),
            ),
            family="feature",
            aliases=("furo passante", "furar", "through hole", "drill"),
            tags=("furo", "diâmetro", "posição", "hole", "diameter"),
            examples=(
                "Faça um furo passante de 8 mm no centro da placa.",
                "Fure Ø40 apenas no ressalto entre z=90 e z=120.",
            ),
            order=160,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_counterbore_hole",
            "Cut one vertical through hole with a flat cylindrical counterbore "
            "recess on the TOP face, at GLOBAL coordinates x, y in "
            "millimeters. Fits socket head cap screws: counterbore_diameter "
            "must exceed diameter and counterbore_depth must be smaller "
            "than the solid height.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "object": REFERENCE,
                    "diameter": POSITIVE,
                    "x": NUMBER,
                    "y": NUMBER,
                    "counterbore_diameter": POSITIVE,
                    "counterbore_depth": POSITIVE,
                    "name": NAME,
                },
                (
                    "object",
                    "diameter",
                    "x",
                    "y",
                    "counterbore_diameter",
                    "counterbore_depth",
                ),
            ),
            family="feature",
            aliases=(
                "furo com rebaixo",
                "rebaixo",
                "furo rebaixado",
                "counterbore",
                "counterbore hole",
            ),
            tags=(
                "rebaixo",
                "parafuso",
                "allen",
                "cabeça",
                "counterbore",
                "socket",
                "cap screw",
                "recess",
            ),
            examples=(
                "Faça um furo com rebaixo para parafuso allen M6 na placa.",
                "Cut a counterbore hole for a socket head cap screw.",
            ),
            order=162,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_countersunk_hole",
            "Cut one vertical through hole with a conical countersink on the "
            "TOP face, at GLOBAL coordinates x, y in millimeters. Fits flat "
            "head screws: countersink_diameter must exceed diameter; "
            "countersink_angle is the full cone angle in degrees (60 to "
            "120, default 90).",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "object": REFERENCE,
                    "diameter": POSITIVE,
                    "x": NUMBER,
                    "y": NUMBER,
                    "countersink_diameter": POSITIVE,
                    "countersink_angle": {
                        "type": "number",
                        "minimum": 60,
                        "maximum": 120,
                    },
                    "name": NAME,
                },
                ("object", "diameter", "x", "y", "countersink_diameter"),
            ),
            family="feature",
            aliases=(
                "furo escareado",
                "escareado",
                "escarear",
                "countersink",
                "countersunk hole",
            ),
            tags=(
                "escareado",
                "cônico",
                "conico",
                "parafuso",
                "cabeça chata",
                "countersink",
                "flat head",
                "cone",
            ),
            examples=(
                "Faça um furo escareado para parafuso de cabeça chata.",
                "Cut a countersunk hole with a 90 degree angle.",
            ),
            order=164,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_threaded_hole",
            "Cut a blind internal ISO-style 60-degree threaded hole into an "
            "existing solid, from the TOP face down by depth millimeters, at "
            "GLOBAL coordinates x, y. diameter is the nominal major diameter "
            "and pitch the thread pitch (e.g. M8x1.25: diameter 8, pitch "
            "1.25). Maximum 64 turns. Meant for 3D printing.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "object": REFERENCE,
                    "diameter": POSITIVE,
                    "pitch": POSITIVE,
                    "x": NUMBER,
                    "y": NUMBER,
                    "depth": POSITIVE,
                    "name": NAME,
                },
                ("object", "diameter", "pitch", "x", "y", "depth"),
            ),
            family="feature",
            aliases=(
                "furo roscado",
                "rosca interna",
                "roscar furo",
                "threaded hole",
                "internal thread",
                "tapped hole",
            ),
            tags=(
                "rosca",
                "roscado",
                "furo",
                "parafuso",
                "porca",
                "thread",
                "tapped",
                "internal",
            ),
            examples=(
                "Faça um furo roscado M8 com passo 1.25 e 12 mm de profundidade.",
                "Cut an M6 threaded hole 10 mm deep into the block.",
            ),
            order=166,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_rectangular_sketch",
            "Create a closed rectangular sketch on the global XY plane with one "
            "corner at the origin, spanning width along X and height along "
            "Y in millimeters. The sketch is fully constrained.",
            ToolRisk.MODIFY,
            _object_schema({"width": POSITIVE, "height": POSITIVE, "name": NAME}, ("width", "height")),
            family="sketch",
            aliases=("sketch retangular", "esboço retangular", "rectangular sketch"),
            tags=("esboço", "retângulo", "perfil", "sketch", "rectangle", "profile"),
            examples=("Crie um sketch retangular de 40 por 20 mm.",),
            order=190,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_circular_sketch",
            "Create a closed circular sketch on the global XY plane centered "
            "at the origin, with diameter in millimeters. Move it with "
            "cad.transform_object to position loft sections or revolve "
            "profiles.",
            ToolRisk.MODIFY,
            _object_schema({"diameter": POSITIVE, "name": NAME}, ("diameter",)),
            family="sketch",
            aliases=("sketch circular", "círculo", "circular sketch", "circle"),
            tags=("esboço", "círculo", "diâmetro", "sketch", "circle", "profile"),
            examples=("Crie um sketch circular de 40 mm de diâmetro.",),
            order=191,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.pad_sketch",
            "Extrude one closed sketch along +Z by length millimeters into a "
            "validated solid linked to the sketch.",
            ToolRisk.MODIFY,
            _object_schema({"sketch": REFERENCE, "length": POSITIVE, "name": NAME}, ("sketch", "length")),
            family="feature",
            aliases=("extrudar sketch", "pad", "extrude sketch"),
            tags=("extrusão", "sólido", "comprimento", "pad", "extrude", "solid"),
            examples=("Faça um pad de 12 mm no sketch Perfil.",),
            order=195,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.revolve_sketch",
            "Revolve one closed sketch around the global X or Y axis through "
            "the origin by angle degrees (0 to 360). The sketch must lie "
            "entirely on one side of the axis; position it first with "
            "cad.transform_object. Good for pulleys, shafts and turned caps.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "angle": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "maximum": 360,
                    },
                    "axis": {"type": "string", "enum": ["x", "y"]},
                    "name": NAME,
                },
                ("sketch",),
            ),
            family="feature",
            aliases=("revolução", "revolucionar sketch", "revolve", "revolution"),
            tags=("revolução", "torno", "eixo", "revolve", "lathe", "turned"),
            examples=("Revolucione o perfil em 360 graus ao redor do eixo X.",),
            order=196,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.loft_sketches",
            "Loft two to eight closed sketches into one solid, in the given "
            "order. Sections must sit at different heights: create each "
            "sketch, then move it in Z with cad.transform_object before "
            "lofting. Ruled true gives straight flanks between sections.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketches": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 256,
                        },
                        "minItems": 2,
                        "maxItems": 8,
                    },
                    "ruled": {"type": "boolean"},
                    "name": NAME,
                },
                ("sketches",),
            ),
            family="feature",
            aliases=("loft", "transição entre perfis", "loft sketches"),
            tags=("loft", "seções", "transição", "sections", "blend"),
            examples=("Faça um loft entre os dois perfis circulares.",),
            order=197,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.create_sweep_path",
            "Create an open 3D trajectory of straight lines through the given "
            "points, each written as 'x,y,z' in millimeters (2 to 16 "
            "points). A positive corner_radius rounds every interior "
            "corner with a tangent arc. Use it as the path argument of "
            "cad.sweep_sketch.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "points": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "minLength": 5,
                            "maxLength": 64,
                        },
                        "minItems": 2,
                        "maxItems": 16,
                    },
                    "corner_radius": {"type": "number", "minimum": 0},
                    "name": NAME,
                },
                ("points",),
            ),
            family="sketch",
            aliases=(
                "trajetória",
                "trajetoria",
                "caminho de varredura",
                "sweep path",
                "trajectory",
            ),
            tags=(
                "trajetória",
                "trajetoria",
                "caminho",
                "linha",
                "arco",
                "path",
                "line",
                "arc",
            ),
            examples=(
                "Crie uma trajetória em L com cantos arredondados de 10 mm.",
                "Create a sweep path through 0,0,0 and 0,0,40.",
            ),
            order=198,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.sweep_sketch",
            "Sweep one closed sketch along a path created by "
            "cad.create_sweep_path into a validated solid. Keep the profile "
            "sketch on the XY plane at the origin: the tool moves it to the "
            "path start and orients it along the first segment. Good for "
            "tubes, ducts and handles.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "profile": REFERENCE,
                    "path": REFERENCE,
                    "name": NAME,
                },
                ("profile", "path"),
            ),
            family="feature",
            aliases=(
                "varredura",
                "varrer perfil",
                "sweep",
                "sweep profile",
            ),
            tags=(
                "varredura",
                "varrer",
                "tubo",
                "duto",
                "perfil",
                "sweep",
                "tube",
                "pipe",
            ),
            examples=(
                "Varra o perfil circular ao longo da trajetória em L.",
                "Sweep the profile along the path to make a tube.",
            ),
            order=199,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.boolean_operation",
            "Combine two solids into a new derived object: fuse is union, cut is "
            "left minus right, common is intersection. Source objects are "
            "kept and linked.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "left": REFERENCE,
                    "right": REFERENCE,
                    "operation": {"type": "string", "enum": ["fuse", "cut", "common"]},
                    "name": NAME,
                },
                ("left", "right", "operation"),
            ),
            family="boolean",
            aliases=("operação booleana", "união", "subtração", "interseção", "boolean"),
            tags=("fundir", "cortar", "comum", "fuse", "cut", "common"),
            examples=("Subtraia o Pino da Base.",),
            order=210,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.fillet_edges",
            "Round one edge with radius in millimeters. Obtain edge_reference "
            "from cad.get_object_details; ambiguous or stale references "
            "fail instead of guessing.",
            ToolRisk.MODIFY,
            _object_schema(
                {"object": REFERENCE, "radius": POSITIVE, "edge_reference": REFERENCE, "name": NAME},
                ("object", "radius", "edge_reference"),
            ),
            family="finish",
            aliases=("filete", "arredondar aresta", "fillet"),
            tags=("raio", "aresta", "acabamento", "radius", "edge", "round"),
            examples=("Aplique filete de 2 mm na aresta indicada.",),
            order=220,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.chamfer_edges",
            "Bevel one edge with size in millimeters. Obtain edge_reference "
            "from cad.get_object_details; ambiguous or stale references "
            "fail instead of guessing.",
            ToolRisk.MODIFY,
            _object_schema(
                {"object": REFERENCE, "size": POSITIVE, "edge_reference": REFERENCE, "name": NAME},
                ("object", "size", "edge_reference"),
            ),
            family="finish",
            aliases=("chanfro", "chanfrar aresta", "chamfer"),
            tags=("distância", "aresta", "acabamento", "distance", "edge", "bevel"),
            examples=("Aplique chanfro de 1 mm na aresta indicada.",),
            order=230,
            output_schema=OBJECT_RESULT,
        ),
    )

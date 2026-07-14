from __future__ import annotations

from typing import Any

from aicad.core.tool_registry import ToolRisk, ToolSpec


NAME = {
    "type": "string",
    "minLength": 1,
    "maxLength": 64,
    "pattern": "[A-Za-z][A-Za-z0-9_-]*",
}
REFERENCE = {"type": "string", "minLength": 1, "maxLength": 256}
POSITIVE = {"type": "number", "exclusiveMinimum": 0}
NUMBER = {"type": "number"}
INTEGER = {"type": "integer", "minimum": 1, "maximum": 128}


def _object_schema(
    properties: dict[str, Any],
    required: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


OBJECT_RESULT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "label": {"type": "string"},
        "valid": {"type": "boolean"},
    },
    "required": ["name", "label", "valid"],
}

DETAIL_RESULT = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "object": {"type": "object"},
        "editable_parameters": {"type": "array"},
        "edge_references": {"type": "array"},
        "edge_references_truncated": {"type": "boolean"},
    },
    "required": ["status", "object", "editable_parameters", "edge_references"],
}

MEASUREMENT_RESULT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "label": {"type": "string"},
        "length_mm": {"type": "number"},
        "width_mm": {"type": "number"},
        "height_mm": {"type": "number"},
        "bounds_mm": {"type": "array"},
        "center_mm": {"type": "array"},
        "volume_mm3": {"type": "number"},
        "area_mm2": {"type": "number"},
        "solids": {"type": "integer"},
        "valid": {"type": "boolean"},
    },
    "required": ["name", "label", "bounds_mm", "valid"],
}

DEPENDENCY_RESULT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "depends_on": {"type": "array"},
        "used_by": {"type": "array"},
    },
    "required": ["name", "depends_on", "used_by"],
}

RESOLUTION_RESULT = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["resolved", "awaiting_selection", "not_found"],
        },
        "object": {"type": "object"},
        "required": {"type": "string"},
        "candidates": {"type": "array"},
        "reference": {"type": "string"},
    },
    "required": ["status"],
}

PARAMETERS_RESULT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "label": {"type": "string"},
        "parameters": {"type": "array"},
    },
    "required": ["name", "label", "parameters"],
}

CAPTURE_RESULT = {
    "type": "object",
    "properties": {
        "capture_id": {"type": "string"},
        "mime_type": {"type": "string", "enum": ["image/png"]},
        "width": {"type": "integer"},
        "height": {"type": "integer"},
        "bytes": {"type": "integer"},
        "resource_uri": {"type": "string"},
    },
    "required": [
        "capture_id",
        "mime_type",
        "width",
        "height",
        "bytes",
        "resource_uri",
    ],
}


def _spec(
    name: str,
    description: str,
    risk: ToolRisk,
    input_schema: dict[str, Any],
    *,
    family: str,
    aliases: tuple[str, ...],
    tags: tuple[str, ...],
    examples: tuple[str, ...],
    order: int,
    output_schema: dict[str, Any] | None = None,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=description,
        risk=risk,
        input_schema=input_schema,
        output_schema=output_schema,
        family=family,
        aliases=aliases,
        tags=tags,
        examples=examples,
        canonical_order=order,
    )


def mechanical_tool_specs() -> tuple[ToolSpec, ...]:
    """Return the provider-neutral M4 catalog without importing FreeCAD."""

    return (
        _spec(
            "cad.get_object_details",
            "Read one object's properties, placement, shape summary and the stable "
            "edge_reference values required by cad.fillet_edges and "
            "cad.chamfer_edges.",
            ToolRisk.READ,
            _object_schema({"object": REFERENCE}, ("object",)),
            family="context",
            aliases=("detalhes do objeto", "propriedades", "object details"),
            tags=("objeto", "propriedades", "arestas", "properties", "edges"),
            examples=("Mostre os detalhes da Base.",),
            order=40,
            output_schema=DETAIL_RESULT,
        ),
        _spec(
            "cad.measure_object",
            "Measure one object in millimeters: bounding box, center, volume, "
            "area and principal dimensions. Use it to verify results after "
            "a mutation.",
            ToolRisk.READ,
            _object_schema({"object": REFERENCE}, ("object",)),
            family="measurement",
            aliases=("medir objeto", "bounding box", "dimensões", "measure"),
            tags=("medida", "volume", "área", "limites", "bounds", "size"),
            examples=("Meça a caixa e informe o bounding box.",),
            order=50,
            output_schema=MEASUREMENT_RESULT,
        ),
        _spec(
            "cad.get_dependencies",
            "Inspect which objects one object depends on and which objects use it.",
            ToolRisk.READ,
            _object_schema({"object": REFERENCE}, ("object",)),
            family="context",
            aliases=("dependências", "relações", "dependencies", "links"),
            tags=("dependência", "entrada", "saída", "upstream", "downstream"),
            examples=("Quais objetos dependem desta peça?",),
            order=60,
            output_schema=DEPENDENCY_RESULT,
        ),
        _spec(
            "cad.resolve_object",
            "Resolve a name or label to one object. An empty reference resolves "
            "the current GUI selection and may return awaiting_selection; "
            "ask the user to select exactly one object in FreeCAD.",
            ToolRisk.READ,
            _object_schema({"reference": REFERENCE}, ()),
            family="context",
            aliases=("resolver objeto", "objeto selecionado", "resolve selection"),
            tags=("seleção", "apelido", "nome", "selection", "alias", "resolve"),
            examples=("Use o objeto que está selecionado.",),
            order=70,
            output_schema=RESOLUTION_RESULT,
        ),
        _spec(
            "cad.get_editable_parameters",
            "List the numeric parameters accepted by cad.set_parameter for one "
            "object, with current values in millimeters or degrees.",
            ToolRisk.READ,
            _object_schema({"object": REFERENCE}, ("object",)),
            family="context",
            aliases=("parâmetros editáveis", "editar dimensões", "editable parameters"),
            tags=("parâmetro", "editar", "dimensão", "parameter", "editable"),
            examples=("Quais dimensões da Base posso alterar?",),
            order=80,
            output_schema=PARAMETERS_RESULT,
        ),
        _spec(
            "cad.capture_view",
            "Capture the active 3D view as PNG. The result contains a capture_id "
            "and a resource_uri (aicad://view/{capture_id}) to fetch the "
            "image as an MCP resource.",
            ToolRisk.READ,
            _object_schema(
                {
                    "width": {"type": "integer", "minimum": 320, "maximum": 1920},
                    "height": {"type": "integer", "minimum": 240, "maximum": 1080},
                },
                (),
            ),
            family="context",
            aliases=("capturar vista", "screenshot", "imagem do modelo"),
            tags=("visual", "imagem", "vista", "screenshot", "view"),
            examples=("Capture a vista atual do modelo.",),
            order=90,
            output_schema=CAPTURE_RESULT,
        ),
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
            "cad.create_plate",
            "Create a rectangular plate at the global origin: length along X, "
            "width along Y, thickness along Z, in millimeters.",
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
            "cad.create_through_hole",
            "Cut one vertical through hole (along Z, through the full solid) at "
            "GLOBAL document coordinates x, y in millimeters. Diameter in "
            "millimeters. The result is a new derived object linked to the "
            "source.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "object": REFERENCE,
                    "diameter": POSITIVE,
                    "x": NUMBER,
                    "y": NUMBER,
                    "name": NAME,
                },
                ("object", "diameter", "x", "y"),
            ),
            family="feature",
            aliases=("furo passante", "furar", "through hole", "drill"),
            tags=("furo", "diâmetro", "posição", "hole", "diameter"),
            examples=("Faça um furo passante de 8 mm no centro da placa.",),
            order=160,
            output_schema=OBJECT_RESULT,
        ),
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
            "cad.create_rectangular_sketch",
            "Create a closed rectangular sketch on the global XY plane with one "
            "corner at the origin, spanning width along X and height along "
            "Y in millimeters. The sketch is closed but not constrained.",
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
        _spec(
            "cad.create_spur_gear",
            "Create an external involute spur gear centered at the global "
            "origin, extruded along +Z by thickness millimeters. Pitch "
            "diameter = module * teeth (mm); mesh two gears by spacing "
            "their centers at the sum of pitch radii. bore_diameter 0 "
            "means solid; pressure_angle is in degrees.",
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
            "by using opposite signs and the same module. Pitch diameter = "
            "module * teeth (mm); bore_diameter 0 means solid.",
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
    )

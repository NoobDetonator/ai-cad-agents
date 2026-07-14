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
            "Read bounded properties, placement, shape and stable edge references.",
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
            "Measure bounds, center, volume, area and principal dimensions.",
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
            "Inspect upstream and downstream document relationships.",
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
            "Resolve an internal name, label, alias or current GUI selection.",
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
            "List safe editable numeric parameters and their current values.",
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
            "Capture the active 3D view into the bounded local visual cache.",
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
            "Rename one explicitly resolved object in a reversible transaction.",
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
            "Set one allowlisted numeric parameter and validate the resulting shape.",
            ToolRisk.MODIFY,
            _object_schema(
                {"object": REFERENCE, "parameter": REFERENCE, "value": NUMBER},
                ("object", "parameter", "value"),
            ),
            family="edit",
            aliases=("alterar parâmetro", "mudar dimensão", "set parameter"),
            tags=("comprimento", "largura", "altura", "raio", "parameter", "dimension"),
            examples=("Altere a altura da Base para 12 mm.",),
            order=130,
            output_schema=OBJECT_RESULT,
        ),
        _spec(
            "cad.transform_object",
            "Move and rotate an object with explicit millimeter and degree values.",
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
            "Create a parametric rectangular plate in one reversible transaction.",
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
            "Cut one explicit through hole from a solid and retain its source link.",
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
            "Cut a bounded rectangular grid of through holes from one solid.",
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
            "Cut a bounded circular pattern of through holes from one solid.",
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
            "Create a closed rectangular sketch on the XY plane.",
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
            "Pad one explicit closed rectangular sketch into a validated solid.",
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
            "cad.boolean_operation",
            "Apply fuse, cut or common to two explicit solid operands.",
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
            "Fillet one edge selected by a stable geometric reference.",
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
            "Chamfer one edge selected by a stable geometric reference.",
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

from __future__ import annotations

from aicad.core.tool_catalog.schemas import (
    NAME,
    NUMBER,
    POSITIVE,
    REFERENCE,
    _object_schema,
    _spec,
)
from aicad.core.tool_registry import ToolRisk, ToolSpec


GEOMETRY_INDEX = {"type": "integer", "minimum": 0, "maximum": 4095}
CONSTRAINT_INDEX = {"type": "integer", "minimum": 0, "maximum": 8191}
POINT_POSITION = {"type": "string", "enum": ["start", "end", "center"]}
INDEX_LIST = {
    "type": "array",
    "items": GEOMETRY_INDEX,
    "minItems": 1,
    "maxItems": 256,
    "uniqueItems": True,
}
POINT_LIST = {
    "type": "array",
    "items": {
        "type": "string",
        "minLength": 3,
        "maxLength": 64,
        "pattern": r"^\s*[-+0-9.eE]+\s*,\s*[-+0-9.eE]+\s*$",
    },
    "minItems": 2,
    "maxItems": 256,
}
SKETCH_RESULT = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "label": {"type": "string"},
        "geometry_count": {"type": "integer"},
        "constraint_count": {"type": "integer"},
        "fully_constrained": {"type": "boolean"},
        "valid": {"type": "boolean"},
    },
    "required": ["name", "label", "geometry_count", "constraint_count", "valid"],
}


def _sketch_spec(
    name: str,
    description: str,
    risk: ToolRisk,
    schema: dict,
    aliases: tuple[str, ...],
    tags: tuple[str, ...],
    example: str,
    order: int,
) -> ToolSpec:
    return _spec(
        name,
        description,
        risk,
        schema,
        family="sketch",
        aliases=aliases,
        tags=tags,
        examples=(example,),
        order=order,
        output_schema=SKETCH_RESULT,
    )


def sketch_tool_specs() -> tuple[ToolSpec, ...]:
    """Return the structured sketch creation, constraint and editing API."""

    return (
        _sketch_spec(
            "cad.create_empty_sketch",
            "Create an empty parametric sketch on the global XY, XZ or YZ plane. "
            "Offset is measured along that plane's normal in millimeters.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "plane": {"type": "string", "enum": ["xy", "xz", "yz"]},
                    "offset": NUMBER,
                    "name": NAME,
                },
                (),
            ),
            ("novo sketch", "sketch vazio", "empty sketch", "new sketch"),
            ("sketch", "plano", "perfil", "plane", "profile"),
            "Crie um sketch vazio no plano XZ.",
            181,
        ),
        _sketch_spec(
            "cad.add_sketch_line",
            "Add one finite line segment to an existing sketch using local sketch coordinates.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "x1": NUMBER,
                    "y1": NUMBER,
                    "x2": NUMBER,
                    "y2": NUMBER,
                    "construction": {"type": "boolean"},
                },
                ("sketch", "x1", "y1", "x2", "y2"),
            ),
            ("adicionar linha", "linha no sketch", "add sketch line"),
            ("linha", "segmento", "sketch", "line", "segment"),
            "Adicione uma linha de 0,0 até 40,0 no sketch Perfil.",
            182,
        ),
        _sketch_spec(
            "cad.add_sketch_polyline",
            "Add connected line segments through 2 to 256 local x,y points. "
            "Optionally close the last point back to the first.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "points": POINT_LIST,
                    "closed": {"type": "boolean"},
                    "construction": {"type": "boolean"},
                },
                ("sketch", "points"),
            ),
            ("polilinha", "contorno", "polyline", "outline"),
            ("linha", "contorno", "fechado", "polyline", "closed"),
            "Adicione uma polilinha fechada pelos pontos 0,0; 40,0; 30,20.",
            183,
        ),
        _sketch_spec(
            "cad.add_sketch_circle",
            "Add a circle to an existing sketch from center and radius in local coordinates.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "center_x": NUMBER,
                    "center_y": NUMBER,
                    "radius": POSITIVE,
                    "construction": {"type": "boolean"},
                },
                ("sketch", "center_x", "center_y", "radius"),
            ),
            ("adicionar círculo", "círculo no sketch", "add sketch circle"),
            ("círculo", "raio", "centro", "circle", "radius"),
            "Adicione um círculo de raio 8 mm no centro 20,15.",
            184,
        ),
        _sketch_spec(
            "cad.add_sketch_arc",
            "Add a circular arc from center, radius and start/end angles in degrees. "
            "The sweep is counter-clockwise and must be less than 360 degrees.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "center_x": NUMBER,
                    "center_y": NUMBER,
                    "radius": POSITIVE,
                    "start_angle": NUMBER,
                    "end_angle": NUMBER,
                    "construction": {"type": "boolean"},
                },
                (
                    "sketch",
                    "center_x",
                    "center_y",
                    "radius",
                    "start_angle",
                    "end_angle",
                ),
            ),
            ("adicionar arco", "arco no sketch", "add sketch arc"),
            ("arco", "ângulo", "raio", "arc", "angle"),
            "Adicione um arco de 0 a 180 graus com raio 12 mm.",
            185,
        ),
        _sketch_spec(
            "cad.add_sketch_ellipse",
            "Add a complete ellipse with major/minor radii and rotation in degrees.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "center_x": NUMBER,
                    "center_y": NUMBER,
                    "major_radius": POSITIVE,
                    "minor_radius": POSITIVE,
                    "rotation": NUMBER,
                    "construction": {"type": "boolean"},
                },
                ("sketch", "center_x", "center_y", "major_radius", "minor_radius"),
            ),
            ("adicionar elipse", "elipse no sketch", "add sketch ellipse"),
            ("elipse", "eixo maior", "eixo menor", "ellipse", "major axis"),
            "Adicione uma elipse 20 por 10 mm girada 30 graus.",
            186,
        ),
        _sketch_spec(
            "cad.add_sketch_rectangle",
            "Add a four-segment rectangle from lower-left position, width, height "
            "and optional rotation in local sketch coordinates.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "x": NUMBER,
                    "y": NUMBER,
                    "width": POSITIVE,
                    "height": POSITIVE,
                    "rotation": NUMBER,
                    "construction": {"type": "boolean"},
                },
                ("sketch", "x", "y", "width", "height"),
            ),
            ("adicionar retângulo", "retângulo no sketch", "add rectangle"),
            ("retângulo", "perfil", "rectangle", "profile"),
            "Adicione um retângulo 40 por 25 mm ao sketch Base.",
            187,
        ),
        _sketch_spec(
            "cad.add_sketch_slot",
            "Add a closed straight slot between two center points. Width is the "
            "full end diameter and the center points must be distinct.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "start_x": NUMBER,
                    "start_y": NUMBER,
                    "end_x": NUMBER,
                    "end_y": NUMBER,
                    "width": POSITIVE,
                    "construction": {"type": "boolean"},
                },
                ("sketch", "start_x", "start_y", "end_x", "end_y", "width"),
            ),
            ("rasgo", "oblongo", "slot", "obround"),
            ("rasgo", "ranhura", "slot", "closed profile"),
            "Adicione um rasgo de 30 mm entre centros e largura 8 mm.",
            188,
        ),
        _sketch_spec(
            "cad.add_sketch_regular_polygon",
            "Add a closed regular polygon from center, circumradius, side count "
            "and rotation in degrees.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "center_x": NUMBER,
                    "center_y": NUMBER,
                    "radius": POSITIVE,
                    "sides": {"type": "integer", "minimum": 3, "maximum": 128},
                    "rotation": NUMBER,
                    "construction": {"type": "boolean"},
                },
                ("sketch", "center_x", "center_y", "radius", "sides"),
            ),
            ("polígono regular", "hexágono", "regular polygon"),
            ("polígono", "lados", "polygon", "sides"),
            "Adicione um hexágono de raio 12 mm ao sketch.",
            189,
        ),
        _sketch_spec(
            "cad.add_sketch_external_geometry",
            "Link one stable edge reference from another CAD object into a sketch "
            "as external reference geometry.",
            ToolRisk.MODIFY,
            _object_schema(
                {"sketch": REFERENCE, "object": REFERENCE, "edge_reference": REFERENCE},
                ("sketch", "object", "edge_reference"),
            ),
            ("geometria externa", "projetar aresta", "external geometry"),
            ("referência", "aresta", "projeção", "external", "edge"),
            "Projete a aresta indicada da Base no sketch Perfil.",
            192,
        ),
        _sketch_spec(
            "cad.add_sketch_geometric_constraint",
            "Add a geometric constraint: horizontal, vertical, parallel, "
            "perpendicular, tangent, equal, coincident, concentric, "
            "point_on_object or block.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "constraint_type": {
                        "type": "string",
                        "enum": [
                            "horizontal",
                            "vertical",
                            "parallel",
                            "perpendicular",
                            "tangent",
                            "equal",
                            "coincident",
                            "concentric",
                            "point_on_object",
                            "block",
                        ],
                    },
                    "first_geometry": GEOMETRY_INDEX,
                    "second_geometry": GEOMETRY_INDEX,
                    "first_position": POINT_POSITION,
                    "second_position": POINT_POSITION,
                },
                ("sketch", "constraint_type", "first_geometry"),
            ),
            ("restrição geométrica", "constraint", "geometric constraint"),
            ("restrição", "coincidente", "tangente", "constraint", "tangent"),
            "Deixe as geometrias 2 e 3 perpendiculares.",
            193,
        ),
        _sketch_spec(
            "cad.add_sketch_dimensional_constraint",
            "Add a driving dimensional constraint in millimeters, except angle "
            "which is supplied in degrees: length, radius, diameter, angle, "
            "distance, distance_x or distance_y.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "constraint_type": {
                        "type": "string",
                        "enum": [
                            "length",
                            "radius",
                            "diameter",
                            "angle",
                            "distance",
                            "distance_x",
                            "distance_y",
                        ],
                    },
                    "geometry": GEOMETRY_INDEX,
                    "value": POSITIVE,
                    "position": POINT_POSITION,
                    "second_geometry": GEOMETRY_INDEX,
                    "second_position": POINT_POSITION,
                },
                ("sketch", "constraint_type", "geometry", "value"),
            ),
            ("restrição dimensional", "cota", "dimension constraint"),
            ("cota", "distância", "raio", "dimension", "distance"),
            "Defina o diâmetro da geometria 4 como 20 mm.",
            194,
        ),
        _sketch_spec(
            "cad.set_sketch_constraint_value",
            "Change the value of an existing dimensional constraint. Unit must "
            "be mm or deg and the solver validates the result transactionally.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "constraint_index": CONSTRAINT_INDEX,
                    "value": POSITIVE,
                    "unit": {"type": "string", "enum": ["mm", "deg"]},
                },
                ("sketch", "constraint_index", "value"),
            ),
            ("alterar cota", "mudar restrição", "set constraint value"),
            ("cota", "valor", "datum", "constraint", "value"),
            "Altere a cota 5 para 32 mm.",
            201,
        ),
        _sketch_spec(
            "cad.set_sketch_constraint_driving",
            "Switch a dimensional constraint between driving and reference mode.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "constraint_index": CONSTRAINT_INDEX,
                    "driving": {"type": "boolean"},
                },
                ("sketch", "constraint_index", "driving"),
            ),
            ("cota de referência", "cota dirigente", "driving constraint"),
            ("referência", "dirigente", "driving", "reference"),
            "Transforme a cota 3 em cota de referência.",
            202,
        ),
        _sketch_spec(
            "cad.move_sketch_point",
            "Move one geometry start, end or center point to an absolute local "
            "sketch coordinate while respecting active constraints.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "geometry": GEOMETRY_INDEX,
                    "position": POINT_POSITION,
                    "x": NUMBER,
                    "y": NUMBER,
                },
                ("sketch", "geometry", "position", "x", "y"),
            ),
            ("mover ponto", "editar vértice", "move sketch point"),
            ("ponto", "vértice", "posição", "point", "vertex"),
            "Mova o final da linha 2 para 40,25.",
            203,
        ),
        _sketch_spec(
            "cad.toggle_sketch_construction",
            "Toggle selected geometry between normal profile and construction mode.",
            ToolRisk.MODIFY,
            _object_schema({"sketch": REFERENCE, "geometry_indices": INDEX_LIST}, ("sketch", "geometry_indices")),
            ("geometria de construção", "alternar construção", "construction geometry"),
            ("construção", "auxiliar", "construction", "helper"),
            "Transforme as geometrias 0 e 1 em linhas de construção.",
            204,
        ),
        _sketch_spec(
            "cad.delete_sketch_geometry",
            "Delete selected sketch geometry and its dependent constraints.",
            ToolRisk.MODIFY,
            _object_schema({"sketch": REFERENCE, "geometry_indices": INDEX_LIST}, ("sketch", "geometry_indices")),
            ("apagar geometria", "remover linha", "delete sketch geometry"),
            ("apagar", "geometria", "delete", "geometry"),
            "Apague as geometrias 4 e 5 do sketch.",
            205,
        ),
        _sketch_spec(
            "cad.delete_sketch_constraint",
            "Delete one or more sketch constraints by stable indices.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "constraint_indices": {
                        "type": "array",
                        "items": CONSTRAINT_INDEX,
                        "minItems": 1,
                        "maxItems": 512,
                        "uniqueItems": True,
                    },
                },
                ("sketch", "constraint_indices"),
            ),
            ("apagar restrição", "remover cota", "delete constraint"),
            ("apagar", "restrição", "delete", "constraint"),
            "Apague as restrições 2 e 3.",
            206,
        ),
        _sketch_spec(
            "cad.trim_sketch_geometry",
            "Trim a line, arc, circle or ellipse at the supplied local point. "
            "The point selects which segment is affected.",
            ToolRisk.MODIFY,
            _object_schema(
                {"sketch": REFERENCE, "geometry": GEOMETRY_INDEX, "x": NUMBER, "y": NUMBER},
                ("sketch", "geometry", "x", "y"),
            ),
            ("aparar sketch", "trim", "trim sketch geometry"),
            ("aparar", "cortar", "trim", "curve"),
            "Apare a geometria 3 perto do ponto 20,0.",
            207,
        ),
        _sketch_spec(
            "cad.extend_sketch_geometry",
            "Extend a line or curve endpoint by a positive increment in millimeters.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "geometry": GEOMETRY_INDEX,
                    "position": {"type": "string", "enum": ["start", "end"]},
                    "increment": POSITIVE,
                },
                ("sketch", "geometry", "position", "increment"),
            ),
            ("estender sketch", "extend", "extend geometry"),
            ("estender", "linha", "extend", "endpoint"),
            "Estenda o final da linha 1 em 12 mm.",
            208,
        ),
        _sketch_spec(
            "cad.fillet_sketch_corner",
            "Create a tangent sketch fillet between two geometries near their "
            "selected points, with optional trimming.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "first_geometry": GEOMETRY_INDEX,
                    "second_geometry": GEOMETRY_INDEX,
                    "first_x": NUMBER,
                    "first_y": NUMBER,
                    "second_x": NUMBER,
                    "second_y": NUMBER,
                    "radius": POSITIVE,
                    "trim": {"type": "boolean"},
                },
                (
                    "sketch",
                    "first_geometry",
                    "second_geometry",
                    "first_x",
                    "first_y",
                    "second_x",
                    "second_y",
                    "radius",
                ),
            ),
            ("filete no sketch", "arredondar canto", "sketch fillet"),
            ("filete", "tangente", "canto", "fillet", "corner"),
            "Crie um filete de 4 mm entre as linhas 0 e 1.",
            209,
        ),
        _sketch_spec(
            "cad.copy_sketch_geometry",
            "Copy selected geometry by a local displacement. Constraints are not "
            "copied unless clone_constraints is true.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "geometry_indices": INDEX_LIST,
                    "dx": NUMBER,
                    "dy": NUMBER,
                    "clone_constraints": {"type": "boolean"},
                },
                ("sketch", "geometry_indices", "dx", "dy"),
            ),
            ("copiar geometria", "duplicar sketch", "copy sketch geometry"),
            ("copiar", "deslocamento", "copy", "displacement"),
            "Copie as geometrias 0 a 3 deslocando 50 mm em X.",
            211,
        ),
        _sketch_spec(
            "cad.mirror_sketch_geometry",
            "Mirror selected geometry about the horizontal axis, vertical axis "
            "or an explicit construction line in the same sketch.",
            ToolRisk.MODIFY,
            _object_schema(
                {
                    "sketch": REFERENCE,
                    "geometry_indices": INDEX_LIST,
                    "axis": {"type": "string", "enum": ["horizontal", "vertical", "geometry"]},
                    "axis_geometry": GEOMETRY_INDEX,
                },
                ("sketch", "geometry_indices", "axis"),
            ),
            ("espelhar sketch", "simetria", "mirror sketch geometry"),
            ("espelhar", "eixo", "simetria", "mirror", "axis"),
            "Espelhe as geometrias 2 e 3 pelo eixo vertical.",
            212,
        ),
        _sketch_spec(
            "cad.get_sketch_info",
            "Read structured sketch geometry, constraints, construction state, "
            "closed wires, solver status and plane without modifying the document.",
            ToolRisk.READ,
            _object_schema({"sketch": REFERENCE}, ("sketch",)),
            ("inspecionar sketch", "listar restrições", "sketch info"),
            ("inspeção", "solver", "geometria", "constraints", "solver"),
            "Mostre as geometrias e restrições do sketch Perfil.",
            213,
        ),
    )

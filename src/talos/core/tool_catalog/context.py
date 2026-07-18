from __future__ import annotations

from talos.core.tool_catalog.schemas import (
    CAPTURE_RESULT,
    CAPTURES_RESULT,
    DOCUMENT_SUMMARY_RESULT,
    DEPENDENCY_RESULT,
    DETAIL_RESULT,
    DISTANCE_RESULT,
    EMPTY_OBJECT,
    MASS_PROPERTIES_RESULT,
    MEASUREMENT_RESULT,
    PRINT_READINESS_RESULT,
    SELECTION_RESULT,
    PARAMETERS_RESULT,
    REFERENCE,
    RESOLUTION_RESULT,
    SECTION_CAPTURE_RESULT,
    _object_schema,
    _spec,
)
from talos.core.context import ContextSnapshot
from talos.core.tool_registry import ToolRisk, ToolSpec


def context_tool_specs() -> tuple[ToolSpec, ...]:
    """Return the context CAD tool specifications."""

    return (
        ToolSpec(
            name="cad.get_document_summary",
            description="Read the active CAD document and its object tree.",
            risk=ToolRisk.READ,
            input_schema=EMPTY_OBJECT,
            output_schema=DOCUMENT_SUMMARY_RESULT,
            family="context",
            aliases=(
                "resumo",
                "resumo do documento",
                "document summary",
                "object tree",
            ),
            tags=(
                "documento",
                "modelo",
                "objetos",
                "existe",
                "atualmente",
                "document",
                "model",
                "objects",
                "exists",
            ),
            examples=(
                "O que existe atualmente neste modelo?",
                "Show the document object tree.",
            ),
            canonical_order=10,
        ),
        ToolSpec(
            name="cad.get_selection",
            description="Read the objects, faces and edges selected by the user.",
            risk=ToolRisk.READ,
            input_schema=EMPTY_OBJECT,
            output_schema=SELECTION_RESULT,
            family="context",
            aliases=(
                "seleção",
                "seleção atual",
                "selected objects",
                "current selection",
            ),
            tags=(
                "selecionado",
                "selecionados",
                "faces",
                "arestas",
                "selected",
                "selection",
                "edges",
            ),
            examples=(
                "Quais objetos e faces eu selecionei?",
                "Which edges are selected?",
            ),
            canonical_order=20,
        ),
        ToolSpec(
            name="cad.get_context_snapshot",
            description=(
                "Read a bounded, versioned snapshot of the active document, "
                "selection and recently changed objects. Call it first: its "
                "state_token is required to detect external changes and to "
                "submit plans."
            ),
            risk=ToolRisk.READ,
            input_schema={
                "type": "object",
                "properties": {
                    "detail_level": {
                        "type": "string",
                        "enum": ["minimal", "work"],
                    },
                    "max_objects": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "cursor": {
                        "type": "integer",
                        "minimum": 0,
                    },
                },
                "additionalProperties": False,
            },
            output_schema=ContextSnapshot.model_json_schema(),
            family="context",
            aliases=(
                "contexto",
                "contexto atual",
                "estado atual",
                "current context",
                "recent objects",
            ),
            tags=(
                "recente",
                "último",
                "ultima",
                "ele",
                "essas",
                "context",
                "recent",
                "current",
            ),
            examples=(
                "Leia o estado atual e os objetos recentes.",
                "Use the current selection and recent object.",
            ),
            essential=True,
            canonical_order=30,
        ),
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
            "cad.measure_mass_properties",
            "Measure mass, volume and volume-weighted center of gravity of one "
            "solid object from an explicit material density in g/cm3. Example "
            'call: {"object": "Body", "density": 1.24}. Common densities: '
            "PLA 1.24, PETG 1.27, ABS 1.04, aluminium 2.70, steel 7.85.",
            ToolRisk.READ,
            _object_schema(
                {
                    "object": REFERENCE,
                    "density": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "maximum": 30,
                    },
                },
                ("object", "density"),
            ),
            family="measurement",
            aliases=(
                "massa",
                "peso da peça",
                "centro de gravidade",
                "mass properties",
                "weight",
                "center of gravity",
            ),
            tags=(
                "massa",
                "densidade",
                "gravidade",
                "inércia",
                "mass",
                "density",
                "weight",
            ),
            examples=("Qual a massa da peça em PLA?",),
            order=56,
            output_schema=MASS_PROPERTIES_RESULT,
        ),
        _spec(
            "cad.analyze_print_readiness",
            "Analyze one solid for upright FDM printing along +Z: closed solids, "
            "bed contact area, floating solids and downward faces steeper than "
            "the printable overhang limit (normals sampled at face centers). "
            'Example call: {"object": "Body", "max_overhang_angle_deg": 45}.',
            ToolRisk.READ,
            _object_schema(
                {
                    "object": REFERENCE,
                    "max_overhang_angle_deg": {
                        "type": "number",
                        "minimum": 20,
                        "maximum": 85,
                    },
                },
                ("object",),
            ),
            family="analysis",
            aliases=(
                "prontidão de impressão",
                "análise de impressão 3d",
                "overhang",
                "print readiness",
                "printability",
                "support analysis",
            ),
            tags=(
                "impressão 3d",
                "fdm",
                "suporte",
                "balanço",
                "printing",
                "overhang",
                "support",
            ),
            examples=("A peça imprime sem suporte?",),
            order=57,
            output_schema=PRINT_READINESS_RESULT,
        ),
        _spec(
            "cad.measure_distance",
            "Measure the minimum surface distance and bounding-box center distance "
            "between two different valid shape objects. Return the closest point "
            "pair in global millimeter coordinates and report contact/intersection.",
            ToolRisk.READ,
            _object_schema(
                {"left": REFERENCE, "right": REFERENCE},
                ("left", "right"),
            ),
            family="measurement",
            aliases=(
                "medir distância",
                "distância entre objetos",
                "folga entre peças",
                "measure distance",
                "clearance between parts",
            ),
            tags=(
                "distância",
                "folga",
                "contato",
                "interseção",
                "distance",
                "clearance",
                "contact",
            ),
            examples=("Meça a menor distância entre Base e Tampa.",),
            order=55,
            output_schema=DISTANCE_RESULT,
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
            "and a resource_uri (talos://view/{capture_id}) to fetch the "
            "image as an MCP resource. By default it shoots whatever camera "
            "the user left in the GUI, which may be zoomed somewhere else "
            "entirely: pass view (isometric, top, bottom, front, rear, left, "
            "right) and fit=true to get a reproducible framing of the whole "
            "model. Orientation and fit move the camera temporarily, so prefer "
            "the default when "
            "you only want to see what they see. The original camera is restored "
            "before the tool returns.",
            ToolRisk.READ,
            _object_schema(
                {
                    "width": {"type": "integer", "minimum": 320, "maximum": 1920},
                    "height": {"type": "integer", "minimum": 240, "maximum": 1080},
                    "view": {
                        "type": "string",
                        "enum": [
                            "current",
                            "isometric",
                            "top",
                            "bottom",
                            "front",
                            "rear",
                            "left",
                            "right",
                        ],
                    },
                    "fit": {"type": "boolean"},
                },
                (),
            ),
            family="context",
            aliases=("capturar vista", "screenshot", "imagem do modelo"),
            tags=("visual", "imagem", "vista", "screenshot", "view"),
            examples=(
                "Capture a vista atual do modelo.",
                "Capture o modelo inteiro em isométrico enquadrado.",
            ),
            order=90,
            output_schema=CAPTURE_RESULT,
        ),
        _spec(
            "cad.capture_views",
            "Capture one to eight independent standard views as PNG resources in "
            "a single call. Defaults to isometric, front, top and right. Every "
            "view starts from the same camera snapshot, optional fit is applied, "
            "and the user's original camera is restored even when capture fails.",
            ToolRisk.READ,
            _object_schema(
                {
                    "views": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "current",
                                "isometric",
                                "top",
                                "bottom",
                                "front",
                                "rear",
                                "left",
                                "right",
                            ],
                        },
                        "minItems": 1,
                        "maxItems": 8,
                        "uniqueItems": True,
                    },
                    "width": {"type": "integer", "minimum": 320, "maximum": 1920},
                    "height": {"type": "integer", "minimum": 240, "maximum": 1080},
                    "fit": {"type": "boolean"},
                },
                (),
            ),
            family="context",
            aliases=(
                "capturar vistas",
                "múltiplos ângulos",
                "multi view screenshot",
            ),
            tags=(
                "visual",
                "vistas",
                "ângulos",
                "inspeção",
                "views",
                "camera",
            ),
            examples=(
                "Capture vistas isométrica, frontal, superior e direita.",
                "Show this part from several standard angles.",
            ),
            order=95,
            output_schema=CAPTURES_RESULT,
        ),
        _spec(
            "cad.capture_section_view",
            "Capture a non-destructive visual section through the active model "
            "using the XY, XZ or YZ plane. Offset is measured from the global "
            "origin along the plane normal. The default keeps the negative-normal "
            "side; flip=true keeps the positive-normal side. With the default "
            "isometric view the camera is placed on the discarded side so the "
            "cut face always faces the capture. This is viewport "
            "clipping, so cut faces are not capped. The temporary clipping plane, "
            "camera and visual overlays are restored before return. Refuses to "
            "replace a clipping plane already configured by the user.",
            ToolRisk.READ,
            _object_schema(
                {
                    "plane": {
                        "type": "string",
                        "enum": ["xy", "xz", "yz"],
                    },
                    "offset": {
                        "type": "number",
                        "minimum": -1_000_000,
                        "maximum": 1_000_000,
                    },
                    "flip": {"type": "boolean"},
                    "width": {"type": "integer", "minimum": 320, "maximum": 1920},
                    "height": {"type": "integer", "minimum": 240, "maximum": 1080},
                    "view": {
                        "type": "string",
                        "enum": [
                            "current",
                            "isometric",
                            "top",
                            "bottom",
                            "front",
                            "rear",
                            "left",
                            "right",
                        ],
                    },
                    "fit": {"type": "boolean"},
                },
                (),
            ),
            family="context",
            aliases=(
                "vista em corte",
                "corte visual",
                "raio x",
                "section view",
                "clipping plane",
            ),
            tags=(
                "visual",
                "corte",
                "seção",
                "interior",
                "section",
                "clipping",
                "inspection",
            ),
            examples=(
                "Mostre um corte XY da peça na altura Z igual a 10 mm.",
                "Capture an isometric YZ section keeping the positive side.",
            ),
            order=97,
            output_schema=SECTION_CAPTURE_RESULT,
        ),
    )

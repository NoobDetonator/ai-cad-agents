from __future__ import annotations

from aicad.core.tool_catalog.schemas import (
    CAD_EXPORT_SCHEMA,
    EMPTY_OBJECT,
)
from aicad.core.tool_registry import ToolRisk, ToolSpec


def document_tool_specs() -> tuple[ToolSpec, ...]:
    """Return the documents CAD tool specifications."""

    return (
        ToolSpec(
            name="cad.list_documents",
            description=(
                "List every open document with name, label, saved file path "
                "and object count, and report which one is active. All other "
                "tools operate on the active document."
            ),
            risk=ToolRisk.READ,
            input_schema=EMPTY_OBJECT,
            family="document",
            aliases=(
                "listar documentos",
                "documentos abertos",
                "list documents",
                "open documents",
            ),
            tags=("documento", "abertos", "ativo", "document", "open", "active"),
            examples=(
                "Quais documentos estão abertos?",
                "Which document is active?",
            ),
            canonical_order=330,
        ),
        ToolSpec(
            name="cad.new_document",
            description=(
                "Create a new empty document and make it the active one. Use "
                "separate documents to keep independent parts organized. The "
                "name must start with a letter and use only letters, digits, "
                "underscore or hyphen."
            ),
            risk=ToolRisk.MODIFY,
            input_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 64,
                        "pattern": "[A-Za-z][A-Za-z0-9_-]*",
                    },
                },
                "additionalProperties": False,
            },
            family="document",
            aliases=(
                "novo documento",
                "criar documento",
                "new document",
                "create document",
            ),
            tags=("documento", "novo", "separar", "document", "new", "part"),
            examples=(
                "Crie um documento novo chamado Engrenagens.",
                "Start a new document for the housing part.",
            ),
            canonical_order=340,
        ),
        ToolSpec(
            name="cad.set_active_document",
            description=(
                "Switch the active document to another open document by name "
                "or label. All subsequent reads and mutations target the "
                "newly active document."
            ),
            risk=ToolRisk.MODIFY,
            input_schema={
                "type": "object",
                "properties": {
                    "document": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 256,
                    },
                },
                "required": ["document"],
                "additionalProperties": False,
            },
            family="document",
            aliases=(
                "ativar documento",
                "trocar documento",
                "switch document",
                "activate document",
            ),
            tags=("documento", "ativo", "trocar", "document", "switch", "active"),
            examples=(
                "Ative o documento Engrenagens.",
                "Switch to the Housing document.",
            ),
            canonical_order=350,
        ),
        ToolSpec(
            name="cad.save_document",
            description=(
                "Save the active document. Pass an explicit absolute .FCStd "
                "destination on first save (no silent overwrite); omit the "
                "destination to save a document to its existing file. The "
                "result includes size and sha256."
            ),
            risk=ToolRisk.EXPORT,
            input_schema={
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 1024,
                    },
                    "overwrite": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
            family="document",
            aliases=(
                "salvar documento",
                "salvar projeto",
                "save document",
                "save file",
            ),
            tags=("documento", "salvar", "fcstd", "document", "save", "file"),
            examples=(
                "Salve o documento em C:/projetos/engrenagens.FCStd.",
                "Save the active document.",
            ),
            canonical_order=360,
        ),
        ToolSpec(
            name="cad.export_stl",
            description=(
                "Export one validated solid object as an STL mesh file to one "
                "explicit absolute destination without silent overwrite. The "
                "document is validated first and the result includes size and "
                "sha256 so the caller can verify the artifact."
            ),
            risk=ToolRisk.EXPORT,
            input_schema=CAD_EXPORT_SCHEMA,
            family="export",
            aliases=(
                "exportar stl",
                "export stl",
                "salvar stl",
                "save stl",
            ),
            tags=(
                "stl",
                "malha",
                "mesh",
                "impressão",
                "impressao",
                "3d print",
                "exportar",
                "export",
                "arquivo",
                "file",
            ),
            examples=(
                "Exporte a peça Base como STL para impressão 3D.",
                "Export the MountingPlate object to C:/parts/plate.stl.",
            ),
            canonical_order=400,
        ),
        ToolSpec(
            name="cad.export_step",
            description=(
                "Export one validated solid object as a STEP file to one "
                "explicit absolute destination without silent overwrite. The "
                "document is validated first and the result includes size and "
                "sha256 so the caller can verify the artifact."
            ),
            risk=ToolRisk.EXPORT,
            input_schema=CAD_EXPORT_SCHEMA,
            family="export",
            aliases=(
                "exportar step",
                "export step",
                "salvar step",
                "save step",
            ),
            tags=(
                "step",
                "stp",
                "cad",
                "fabricação",
                "fabricacao",
                "manufacturing",
                "exportar",
                "export",
                "arquivo",
                "file",
            ),
            examples=(
                "Exporte o flange como STEP para o fornecedor.",
                "Export the Flange object to C:/parts/flange.step.",
            ),
            canonical_order=410,
        ),
    )

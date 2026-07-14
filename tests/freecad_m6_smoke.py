from __future__ import annotations

import hashlib
import os
import shutil
import sys
import uuid
from pathlib import Path


project_root = Path(os.environ["AICAD_PROJECT_ROOT"])
sys.path.insert(0, str(project_root / "src"))

import FreeCAD as App

from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.application import build_cad_tool_registry


for document_name in list(App.listDocuments()):
    App.closeDocument(document_name)

document = App.newDocument("AICadM6Smoke")
document.UndoMode = 1
adapter = FreeCadAdapter()
registry = build_cad_tool_registry(adapter)

export_dir = project_root / ".runtime" / f"m6-smoke-{uuid.uuid4().hex[:8]}"
export_dir.mkdir(parents=True)
try:
    plate = registry.execute(
        "cad.create_plate",
        {"length": 100, "width": 60, "thickness": 8, "name": "M6Plate"},
        confirmed=True,
    )
    assert plate["valid"] is True

    stl_path = export_dir / "plate.stl"
    stl = registry.execute(
        "cad.export_stl",
        {"destination": str(stl_path), "object": "M6Plate"},
        confirmed=True,
    )
    assert stl["valid"] is True
    assert stl["format"] == "stl"
    assert stl_path.is_file()
    payload = stl_path.read_bytes()
    assert stl["size_bytes"] == len(payload) > 0
    assert stl["sha256"] == hashlib.sha256(payload).hexdigest()
    assert not stl_path.with_name("plate.stl.partial").exists()

    step_path = export_dir / "plate.step"
    step = registry.execute(
        "cad.export_step",
        {"destination": str(step_path), "object": "M6Plate"},
        confirmed=True,
    )
    assert step["valid"] is True
    assert step_path.is_file()
    assert step["size_bytes"] == step_path.stat().st_size > 0
    assert b"ISO-10303" in step_path.read_bytes()[:200]

    overwrite_refused = False
    try:
        registry.execute(
            "cad.export_stl",
            {"destination": str(stl_path), "object": "M6Plate"},
            confirmed=True,
        )
    except FileExistsError:
        overwrite_refused = True
    assert overwrite_refused
    assert stl_path.read_bytes() == payload

    replaced = registry.execute(
        "cad.export_stl",
        {
            "destination": str(stl_path),
            "object": "M6Plate",
            "overwrite": True,
        },
        confirmed=True,
    )
    assert replaced["valid"] is True

    unknown_refused = False
    try:
        registry.execute(
            "cad.export_step",
            {"destination": str(export_dir / "ghost.step"), "object": "Ghost"},
            confirmed=True,
        )
    except KeyError:
        unknown_refused = True
    assert unknown_refused
    assert not (export_dir / "ghost.step").exists()
finally:
    App.closeDocument(document.Name)
    shutil.rmtree(export_dir, ignore_errors=True)

print("FREECAD_M6_SMOKE_OK")

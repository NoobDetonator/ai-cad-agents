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

adapter = FreeCadAdapter()
registry = build_cad_tool_registry(adapter)

work_dir = project_root / ".runtime" / f"m7-smoke-{uuid.uuid4().hex[:8]}"
work_dir.mkdir(parents=True)
try:
    created = registry.execute(
        "cad.new_document", {"name": "PecaA"}, confirmed=True
    )
    assert created["name"] == "PecaA"
    assert created["active"] is True
    registry.execute(
        "cad.create_box",
        {"length": 10, "width": 10, "height": 10, "name": "CuboA"},
        confirmed=True,
    )

    registry.execute("cad.new_document", {"name": "PecaB"}, confirmed=True)
    listing = registry.execute("cad.list_documents")
    names = {item["name"] for item in listing["documents"]}
    assert {"PecaA", "PecaB"} <= names
    assert listing["active_document"] == "PecaB"

    duplicate_refused = False
    try:
        registry.execute("cad.new_document", {"name": "PecaA"}, confirmed=True)
    except ValueError:
        duplicate_refused = True
    assert duplicate_refused

    switched = registry.execute(
        "cad.set_active_document", {"document": "PecaA"}, confirmed=True
    )
    assert switched["name"] == "PecaA"
    summary = registry.execute("cad.get_document_summary")
    assert summary["name"] == "PecaA"
    assert any(item["name"] == "CuboA" for item in summary["objects"])

    unsaved_refused = False
    try:
        registry.execute("cad.save_document", {}, confirmed=True)
    except ValueError:
        unsaved_refused = True
    assert unsaved_refused

    destination = work_dir / "peca-a.FCStd"
    saved = registry.execute(
        "cad.save_document", {"destination": str(destination)}, confirmed=True
    )
    assert destination.is_file()
    payload = destination.read_bytes()
    assert saved["size_bytes"] == len(payload) > 0
    assert saved["sha256"] == hashlib.sha256(payload).hexdigest()

    resaved = registry.execute("cad.save_document", {}, confirmed=True)
    assert resaved["destination"] == str(destination)

    overwrite_refused = False
    try:
        registry.execute(
            "cad.save_document",
            {"destination": str(destination)},
            confirmed=True,
        )
    except FileExistsError:
        overwrite_refused = True
    assert overwrite_refused

    # --- M7.2: revolve, loft, helical gear and external thread ---

    def fingerprint() -> str:
        snapshot = adapter.get_context_snapshot()
        return snapshot["state_token"]["document_fingerprint"]

    registry.execute(
        "cad.create_circular_sketch",
        {"diameter": 20, "name": "PerfilAnel"},
        confirmed=True,
    )
    registry.execute(
        "cad.transform_object",
        {"object": "PerfilAnel", "y": 30},
        confirmed=True,
    )
    ring = registry.execute(
        "cad.revolve_sketch",
        {"sketch": "PerfilAnel", "name": "Anel"},
        confirmed=True,
    )
    import math

    torus_volume = 2 * math.pi**2 * 30 * 10**2
    assert abs(ring["volume_mm3"] - torus_volume) / torus_volume < 0.02

    registry.execute(
        "cad.create_circular_sketch",
        {"diameter": 30, "name": "PerfilCentral"},
        confirmed=True,
    )
    straddle_refused = False
    try:
        registry.execute(
            "cad.revolve_sketch",
            {"sketch": "PerfilCentral", "name": "Invalido"},
            confirmed=True,
        )
    except ValueError:
        straddle_refused = True
    assert straddle_refused

    registry.execute(
        "cad.create_circular_sketch",
        {"diameter": 40, "name": "LoftBase"},
        confirmed=True,
    )
    registry.execute(
        "cad.create_circular_sketch",
        {"diameter": 20, "name": "LoftTopo"},
        confirmed=True,
    )
    registry.execute(
        "cad.transform_object",
        {"object": "LoftTopo", "z": 25},
        confirmed=True,
    )
    funnel = registry.execute(
        "cad.loft_sketches",
        {"sketches": ["LoftBase", "LoftTopo"], "name": "Funil"},
        confirmed=True,
    )
    frustum_volume = math.pi * 25 / 3 * (20**2 + 20 * 10 + 10**2)
    assert abs(funnel["volume_mm3"] - frustum_volume) / frustum_volume < 0.02

    gear = registry.execute(
        "cad.create_helical_gear",
        {
            "teeth": 24,
            "module": 2,
            "thickness": 8,
            "helix_angle": 15,
            "bore_diameter": 8,
            "name": "Helicoidal",
        },
        confirmed=True,
    )
    assert gear["pitch_diameter_mm"] == 48
    outside_cylinder = math.pi * (gear["outside_diameter_mm"] / 2) ** 2 * 8
    assert 0.5 * outside_cylinder < gear["volume_mm3"] < outside_cylinder

    before_thread = fingerprint()
    thread = registry.execute(
        "cad.create_external_thread",
        {"diameter": 8, "pitch": 1.25, "length": 10, "name": "RoscaM8"},
        confirmed=True,
    )
    core_volume = math.pi * (thread["minor_diameter_mm"] / 2) ** 2 * 10
    assert thread["volume_mm3"] > core_volume
    assert registry.execute("cad.validate_document")["valid"] is True
    undone = registry.execute("cad.undo", confirmed=True)
    assert undone["undone"] is True
    assert fingerprint() == before_thread

    # --- M7.3: counterbore, countersink, sweep and constrained sketches ---

    registry.execute(
        "cad.create_plate",
        {"length": 40, "width": 40, "thickness": 10, "name": "PlacaRebaixo"},
        confirmed=True,
    )
    counterbore = registry.execute(
        "cad.create_counterbore_hole",
        {
            "object": "PlacaRebaixo",
            "diameter": 6,
            "x": 20,
            "y": 20,
            "counterbore_diameter": 11,
            "counterbore_depth": 4,
            "name": "FuroRebaixo",
        },
        confirmed=True,
    )
    assert counterbore["counterbore_depth_mm"] == 4
    expected_counterbore = (
        40 * 40 * 10
        - math.pi * 3**2 * 10
        - math.pi * (5.5**2 - 3**2) * 4
    )
    measured = registry.execute("cad.measure_object", {"object": "FuroRebaixo"})
    assert (
        abs(measured["volume_mm3"] - expected_counterbore) / expected_counterbore
        < 0.01
    )

    before_too_deep = fingerprint()
    too_deep_refused = False
    try:
        registry.execute(
            "cad.create_counterbore_hole",
            {
                "object": "FuroRebaixo",
                "diameter": 6,
                "x": 10,
                "y": 10,
                "counterbore_diameter": 11,
                "counterbore_depth": 12,
                "name": "RebaixoInvalido",
            },
            confirmed=True,
        )
    except ValueError:
        too_deep_refused = True
    assert too_deep_refused
    assert fingerprint() == before_too_deep

    registry.execute(
        "cad.create_plate",
        {"length": 40, "width": 40, "thickness": 10, "name": "PlacaEscareada"},
        confirmed=True,
    )
    countersunk = registry.execute(
        "cad.create_countersunk_hole",
        {
            "object": "PlacaEscareada",
            "diameter": 6,
            "x": 20,
            "y": 20,
            "countersink_diameter": 12,
            "name": "FuroEscareado",
        },
        confirmed=True,
    )
    assert abs(countersunk["countersink_depth_mm"] - 3) < 1e-9
    expected_countersunk = 40 * 40 * 10 - math.pi * 3**2 * 10 - 36 * math.pi
    measured = registry.execute("cad.measure_object", {"object": "FuroEscareado"})
    assert (
        abs(measured["volume_mm3"] - expected_countersunk) / expected_countersunk
        < 0.01
    )

    rectangle = registry.execute(
        "cad.create_rectangular_sketch",
        {"width": 30, "height": 20, "name": "PerfilConstrangido"},
        confirmed=True,
    )
    assert rectangle["closed"] is True
    assert rectangle["fully_constrained"] is True

    profile = registry.execute(
        "cad.create_circular_sketch",
        {"diameter": 10, "name": "PerfilTubo"},
        confirmed=True,
    )
    assert profile["fully_constrained"] is True
    path = registry.execute(
        "cad.create_sweep_path",
        {
            "points": ["0,0,0", "0,0,30", "30,0,30"],
            "corner_radius": 10,
            "name": "TrajetoriaL",
        },
        confirmed=True,
    )
    expected_length = 20 + 20 + math.pi * 10 / 2
    assert abs(path["length_mm"] - expected_length) < 0.01

    before_tube = fingerprint()
    swept = registry.execute(
        "cad.sweep_sketch",
        {"profile": "PerfilTubo", "path": "TrajetoriaL", "name": "TuboL"},
        confirmed=True,
    )
    expected_tube = math.pi * 5**2 * expected_length
    assert abs(swept["volume_mm3"] - expected_tube) / expected_tube < 0.02
    assert registry.execute("cad.validate_document")["valid"] is True
    undone = registry.execute("cad.undo", confirmed=True)
    assert undone["undone"] is True
    assert fingerprint() == before_tube
finally:
    for document_name in list(App.listDocuments()):
        App.closeDocument(document_name)
    shutil.rmtree(work_dir, ignore_errors=True)

print("FREECAD_M7_SMOKE_OK")

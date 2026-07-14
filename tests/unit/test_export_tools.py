from pathlib import Path

import pytest

from aicad.adapters.freecad_adapter import FreeCadAdapter
from aicad.core.tool_registry import (
    ToolConfirmationRequired,
    ToolInputError,
    ToolRisk,
    build_default_registry,
)


def test_export_specs_use_export_risk_and_shared_schema() -> None:
    registry = build_default_registry()
    for name in ("cad.export_stl", "cad.export_step"):
        spec = registry.get_spec(name)
        assert spec.risk is ToolRisk.EXPORT
        assert spec.family == "export"
        assert spec.input_schema["required"] == ["destination", "object"]
        assert spec.input_schema["additionalProperties"] is False


def test_export_arguments_are_validated_before_any_handler() -> None:
    registry = build_default_registry()
    with pytest.raises(ToolInputError):
        registry.validate_arguments("cad.export_stl", {"destination": "x.stl"})
    with pytest.raises(ToolInputError):
        registry.validate_arguments(
            "cad.export_step",
            {"destination": "x.step", "object": "Base", "extra": True},
        )
    checked = registry.validate_arguments(
        "cad.export_stl",
        {"destination": "C:/parts/base.stl", "object": "Base", "overwrite": True},
    )
    assert checked["overwrite"] is True


def test_export_requires_explicit_confirmation() -> None:
    registry = build_default_registry()
    registry.bind("cad.export_stl", lambda **_: {"valid": True})
    with pytest.raises(ToolConfirmationRequired):
        registry.execute(
            "cad.export_stl",
            {"destination": "C:/parts/base.stl", "object": "Base"},
        )


def test_export_destination_is_checked_before_freecad(tmp_path: Path) -> None:
    adapter = FreeCadAdapter()
    with pytest.raises(ValueError, match="absolute"):
        adapter.export_stl("relative/base.stl", "Base")
    with pytest.raises(ValueError, match="end with"):
        adapter.export_stl(str(tmp_path / "base.step"), "Base")
    with pytest.raises(ValueError, match="end with"):
        adapter.export_step(str(tmp_path / "base.stl"), "Base")
    with pytest.raises(ValueError, match="directory does not exist"):
        adapter.export_stl(str(tmp_path / "missing" / "base.stl"), "Base")

    existing = tmp_path / "base.stl"
    existing.write_bytes(b"solid")
    with pytest.raises(FileExistsError):
        adapter.export_stl(str(existing), "Base")

    # A valid destination reaches the FreeCAD boundary; in this environment
    # there is either no FreeCAD or no active document, never a written file.
    boundary = "inside FreeCAD|No active CAD document"
    with pytest.raises(RuntimeError, match=boundary):
        adapter.export_stl(str(tmp_path / "ok.stl"), "Base")
    with pytest.raises(RuntimeError, match=boundary):
        adapter.export_step(str(existing.with_suffix(".stp")), "Base")
    assert not (tmp_path / "ok.stl").exists()


def test_step_accepts_both_step_and_stp_suffixes(tmp_path: Path) -> None:
    adapter = FreeCadAdapter()
    for suffix in (".step", ".stp"):
        with pytest.raises(RuntimeError, match="inside FreeCAD|No active CAD document"):
            adapter.export_step(str(tmp_path / f"part{suffix}"), "Base")

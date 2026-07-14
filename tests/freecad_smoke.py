from pathlib import Path
import math
import sys


project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

from aicad.adapters.freecad_adapter import FreeCadAdapter

import FreeCAD as App


for document_name in list(App.listDocuments()):
    App.closeDocument(document_name)
App.newDocument("AICadSmokeTest")
adapter = FreeCadAdapter()
result = adapter.create_box(10, 20, 30, "SmokeTestBox")
cylinder_result = adapter.create_cylinder(30, 60, "SmokeTestCylinder")
validation = adapter.validate_document()

assert result["valid"] is True
assert result["volume_mm3"] == 6000.0
assert cylinder_result["valid"] is True
assert math.isclose(
    cylinder_result["volume_mm3"],
    math.pi * 15**2 * 60,
    rel_tol=1e-9,
)
assert validation["valid"] is True, validation
assert len(App.ActiveDocument.Objects) == 2
assert App.ActiveDocument.UndoCount == 2
undo_result = adapter.undo()
assert undo_result["undone"] is True
assert len(App.ActiveDocument.Objects) == 1
assert App.ActiveDocument.Objects[0].Label == "SmokeTestBox"
undo_result = adapter.undo()
assert undo_result["undone"] is True
assert len(App.ActiveDocument.Objects) == 0
print("FREECAD_SMOKE_OK")
App.closeDocument("AICadSmokeTest")

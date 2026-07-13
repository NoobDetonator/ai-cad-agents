from pathlib import Path
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
validation = adapter.validate_document()

assert result["valid"] is True
assert result["volume_mm3"] == 6000.0
assert validation["valid"] is True, validation
assert len(App.ActiveDocument.Objects) == 1
print("FREECAD_SMOKE_OK")
App.closeDocument("AICadSmokeTest")

from __future__ import annotations

from aicad.adapters.freecad.base import FreeCadAdapterBase
from aicad.adapters.freecad.assembly import AssemblyMixin
from aicad.adapters.freecad.bearings import BearingMixin
from aicad.adapters.freecad.context import ContextReadsMixin
from aicad.adapters.freecad.documents import DocumentMixin
from aicad.adapters.freecad.edits import EditMixin
from aicad.adapters.freecad.export import ExportMixin
from aicad.adapters.freecad.features import FeatureMixin
from aicad.adapters.freecad.mechanical import MechanicalMixin
from aicad.adapters.freecad.objects import ObjectMixin
from aicad.adapters.freecad.parameters import ParameterMixin
from aicad.adapters.freecad.partdesign import PartDesignMixin
from aicad.adapters.freecad.patterns import PatternMixin
from aicad.adapters.freecad.primitives import PrimitiveMixin
from aicad.adapters.freecad.sketches import SketchMixin
from aicad.adapters.freecad.sketch_constraints import SketchConstraintMixin
from aicad.adapters.freecad.sketch_geometry import SketchGeometryMixin
from aicad.adapters.freecad.sweeps import SweepMixin


class FreeCadAdapter(
    ContextReadsMixin,
    PrimitiveMixin,
    ObjectMixin,
    EditMixin,
    SketchMixin,
    SketchGeometryMixin,
    SketchConstraintMixin,
    PartDesignMixin,
    ParameterMixin,
    FeatureMixin,
    SweepMixin,
    PatternMixin,
    MechanicalMixin,
    BearingMixin,
    AssemblyMixin,
    DocumentMixin,
    ExportMixin,
    FreeCadAdapterBase,
):
    """Small, explicit boundary around FreeCAD's Python API.

    Each domain lives in one mixin under :mod:`aicad.adapters.freecad`;
    the shared validation and transaction core lives in
    :class:`FreeCadAdapterBase`.
    """


__all__ = ["FreeCadAdapter"]

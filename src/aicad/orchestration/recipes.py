from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from aicad.core.tool_registry import ToolRegistry
from aicad.orchestration.models import OrchestrationPlan, PlannedToolCall


class _RecipeParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MountingPlateParameters(_RecipeParameters):
    length: float = Field(gt=0, le=10000)
    width: float = Field(gt=0, le=10000)
    thickness: float = Field(gt=0, le=1000)
    hole_diameter: float = Field(gt=0, le=1000)
    edge_offset: float = Field(gt=0, le=5000)
    name: str = Field(default="MountingPlateBlank", pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    result_name: str = Field(default="MountingPlate", pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")

    @model_validator(mode="after")
    def validate_layout(self) -> MountingPlateParameters:
        if self.length <= 2 * self.edge_offset or self.width <= 2 * self.edge_offset:
            raise ValueError("The edge offset leaves no rectangular hole spacing.")
        if self.hole_diameter >= 2 * self.edge_offset:
            raise ValueError("The holes do not fit inside the requested edge offset.")
        return self


class FlangeParameters(_RecipeParameters):
    outer_diameter: float = Field(gt=0, le=10000)
    thickness: float = Field(gt=0, le=1000)
    hole_diameter: float = Field(gt=0, le=1000)
    hole_count: int = Field(ge=3, le=64)
    pitch_diameter: float = Field(gt=0, le=10000)
    name: str = Field(default="FlangeBlank", pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    result_name: str = Field(default="Flange", pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")

    @model_validator(mode="after")
    def validate_layout(self) -> FlangeParameters:
        if self.pitch_diameter + self.hole_diameter >= self.outer_diameter:
            raise ValueError("The bolt circle does not fit inside the flange.")
        return self


class RectangularPadParameters(_RecipeParameters):
    width: float = Field(gt=0, le=10000)
    height: float = Field(gt=0, le=10000)
    length: float = Field(gt=0, le=10000)
    sketch_name: str = Field(default="PadProfile", pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    result_name: str = Field(default="RectangularPad", pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


class SteppedShaftParameters(_RecipeParameters):
    first_diameter: float = Field(gt=0, le=10000)
    first_length: float = Field(gt=0, le=10000)
    second_diameter: float = Field(gt=0, le=10000)
    second_length: float = Field(gt=0, le=10000)
    result_name: str = Field(default="SteppedShaft", pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,47}$")


class FlatPulleyParameters(_RecipeParameters):
    flange_diameter: float = Field(gt=0, le=10000)
    flange_thickness: float = Field(gt=0, le=1000)
    body_diameter: float = Field(gt=0, le=10000)
    body_width: float = Field(gt=0, le=10000)
    bore_diameter: float = Field(gt=0, le=1000)
    result_name: str = Field(default="Pulley", pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,47}$")

    @model_validator(mode="after")
    def validate_layout(self) -> FlatPulleyParameters:
        if self.body_diameter >= self.flange_diameter:
            raise ValueError("The pulley body must be smaller than the flanges.")
        if self.bore_diameter >= self.body_diameter:
            raise ValueError("The bore does not fit inside the pulley body.")
        return self


RecipeCompiler = Callable[[BaseModel], tuple[tuple[str, dict[str, JsonValue]], ...]]


@dataclass(frozen=True, slots=True)
class RecipeDefinition:
    recipe_id: str
    title: str
    description: str
    steps: tuple[str, ...]
    parameter_model: type[BaseModel]
    compiler: RecipeCompiler

    def public_record(self) -> dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "title": self.title,
            "description": self.description,
            "steps": list(self.steps),
            "parameter_schema": self.parameter_model.model_json_schema(),
        }


def _mounting_plate(parameters: BaseModel):
    checked = MountingPlateParameters.model_validate(parameters)
    return (
        (
            "cad.create_plate",
            {
                "length": checked.length,
                "width": checked.width,
                "thickness": checked.thickness,
                "name": checked.name,
            },
        ),
        (
            "cad.create_rectangular_hole_pattern",
            {
                "object": checked.name,
                "diameter": checked.hole_diameter,
                "rows": 2,
                "columns": 2,
                "spacing_x": checked.length - 2 * checked.edge_offset,
                "spacing_y": checked.width - 2 * checked.edge_offset,
                "origin_x": checked.edge_offset,
                "origin_y": checked.edge_offset,
                "name": checked.result_name,
            },
        ),
    )


def _flange(parameters: BaseModel):
    checked = FlangeParameters.model_validate(parameters)
    return (
        (
            "cad.create_cylinder",
            {
                "diameter": checked.outer_diameter,
                "height": checked.thickness,
                "name": checked.name,
            },
        ),
        (
            "cad.create_circular_hole_pattern",
            {
                "object": checked.name,
                "diameter": checked.hole_diameter,
                "count": checked.hole_count,
                "pitch_diameter": checked.pitch_diameter,
                "start_angle": 0,
                "name": checked.result_name,
            },
        ),
    )


def _rectangular_pad(parameters: BaseModel):
    checked = RectangularPadParameters.model_validate(parameters)
    return (
        (
            "cad.create_rectangular_sketch",
            {
                "width": checked.width,
                "height": checked.height,
                "name": checked.sketch_name,
            },
        ),
        (
            "cad.pad_sketch",
            {
                "sketch": checked.sketch_name,
                "length": checked.length,
                "name": checked.result_name,
            },
        ),
    )


def _stepped_shaft(parameters: BaseModel):
    checked = SteppedShaftParameters.model_validate(parameters)
    first_name = f"{checked.result_name}StepA"
    second_name = f"{checked.result_name}StepB"
    return (
        (
            "cad.create_cylinder",
            {
                "diameter": checked.first_diameter,
                "height": checked.first_length,
                "name": first_name,
            },
        ),
        (
            "cad.create_cylinder",
            {
                "diameter": checked.second_diameter,
                "height": checked.second_length,
                "name": second_name,
            },
        ),
        (
            "cad.transform_object",
            {"object": second_name, "z": checked.first_length},
        ),
        (
            "cad.boolean_operation",
            {
                "left": first_name,
                "right": second_name,
                "operation": "fuse",
                "name": checked.result_name,
            },
        ),
    )


def _flat_pulley(parameters: BaseModel):
    checked = FlatPulleyParameters.model_validate(parameters)
    flange_a = f"{checked.result_name}FlangeA"
    body = f"{checked.result_name}Body"
    flange_b = f"{checked.result_name}FlangeB"
    half = f"{checked.result_name}Half"
    blank = f"{checked.result_name}Blank"
    return (
        (
            "cad.create_cylinder",
            {
                "diameter": checked.flange_diameter,
                "height": checked.flange_thickness,
                "name": flange_a,
            },
        ),
        (
            "cad.create_cylinder",
            {
                "diameter": checked.body_diameter,
                "height": checked.body_width,
                "name": body,
            },
        ),
        (
            "cad.transform_object",
            {"object": body, "z": checked.flange_thickness},
        ),
        (
            "cad.create_cylinder",
            {
                "diameter": checked.flange_diameter,
                "height": checked.flange_thickness,
                "name": flange_b,
            },
        ),
        (
            "cad.transform_object",
            {
                "object": flange_b,
                "z": checked.flange_thickness + checked.body_width,
            },
        ),
        (
            "cad.boolean_operation",
            {
                "left": flange_a,
                "right": body,
                "operation": "fuse",
                "name": half,
            },
        ),
        (
            "cad.boolean_operation",
            {
                "left": half,
                "right": flange_b,
                "operation": "fuse",
                "name": blank,
            },
        ),
        (
            "cad.create_through_hole",
            {
                "object": blank,
                "diameter": checked.bore_diameter,
                "x": 0,
                "y": 0,
                "name": checked.result_name,
            },
        ),
    )


_RECIPES = (
    RecipeDefinition(
        recipe_id="mounting_plate",
        title="Placa de montagem com quatro furos",
        description="Cria uma placa paramétrica e corta quatro furos de canto.",
        steps=("Criar a placa base.", "Cortar o padrão retangular de quatro furos."),
        parameter_model=MountingPlateParameters,
        compiler=_mounting_plate,
    ),
    RecipeDefinition(
        recipe_id="flange",
        title="Flange com círculo de parafusos",
        description="Cria um disco e corta um padrão circular de furos.",
        steps=("Criar o disco da flange.", "Cortar o círculo de parafusos."),
        parameter_model=FlangeParameters,
        compiler=_flange,
    ),
    RecipeDefinition(
        recipe_id="rectangular_pad",
        title="Pad retangular",
        description="Cria um sketch retangular e o extruda em um sólido.",
        steps=("Criar o sketch retangular.", "Extrudar o perfil pelo comprimento."),
        parameter_model=RectangularPadParameters,
        compiler=_rectangular_pad,
    ),
    RecipeDefinition(
        recipe_id="stepped_shaft",
        title="Eixo escalonado de dois degraus",
        description="Cria dois cilindros coaxiais empilhados e os funde em um eixo.",
        steps=(
            "Criar o primeiro degrau do eixo.",
            "Criar o segundo degrau do eixo.",
            "Empilhar o segundo degrau sobre o primeiro.",
            "Fundir os dois degraus em um eixo único.",
        ),
        parameter_model=SteppedShaftParameters,
        compiler=_stepped_shaft,
    ),
    RecipeDefinition(
        recipe_id="flat_pulley",
        title="Polia plana com flanges",
        description=(
            "Cria o corpo e duas flanges coaxiais, funde tudo e fura o eixo "
            "central."
        ),
        steps=(
            "Criar a flange inferior.",
            "Criar e posicionar o corpo da polia.",
            "Criar e posicionar a flange superior.",
            "Fundir flanges e corpo.",
            "Furar o eixo central.",
        ),
        parameter_model=FlatPulleyParameters,
        compiler=_flat_pulley,
    ),
)


class RecipeCatalog:
    """Trusted declarative recipes compiled only into registered tool calls."""

    def __init__(self, definitions: tuple[RecipeDefinition, ...] = _RECIPES) -> None:
        self._definitions = {item.recipe_id: item for item in definitions}
        if len(self._definitions) != len(definitions):
            raise ValueError("Recipe IDs must be unique.")

    def list_recipes(self) -> tuple[dict[str, Any], ...]:
        return tuple(item.public_record() for item in self._definitions.values())

    def get(self, recipe_id: str) -> RecipeDefinition:
        try:
            return self._definitions[recipe_id]
        except KeyError as exc:
            raise KeyError(f"Unknown CAD recipe: {recipe_id}") from exc

    def create_plan(
        self,
        recipe_id: str,
        parameters: Mapping[str, Any],
        registry: ToolRegistry,
    ) -> OrchestrationPlan:
        definition = self.get(recipe_id)
        checked_parameters = definition.parameter_model.model_validate(dict(parameters))
        compiled = definition.compiler(checked_parameters)
        calls: list[PlannedToolCall] = []
        for index, (tool_name, arguments) in enumerate(compiled, start=1):
            spec = registry.get_spec(tool_name)
            checked_arguments = registry.validate_arguments(tool_name, arguments)
            calls.append(
                PlannedToolCall(
                    call_id=f"recipe-{recipe_id}-{index}",
                    name=tool_name,
                    arguments=checked_arguments,
                    risk=spec.risk,
                    requires_confirmation=True,
                )
            )
        return OrchestrationPlan(
            intention=definition.title,
            assumptions=("Dimensões em milímetros.",),
            steps=definition.steps,
            message=definition.description,
            tool_calls=tuple(calls),
        )


def default_recipe_catalog() -> RecipeCatalog:
    return RecipeCatalog()

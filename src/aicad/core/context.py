from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from typing import Annotated, Literal, Mapping
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)


CONTEXT_CONTRACT_VERSION = "1.0"
MAX_CONTEXT_SNAPSHOT_BYTES = 64 * 1024
MAX_RECENT_OBJECTS = 16

ObjectName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z][A-Za-z0-9_]*$",
    ),
]
Fingerprint = Annotated[
    str,
    StringConstraints(pattern=r"^[a-f0-9]{64}$"),
]


class ContextDetailLevel(StrEnum):
    MINIMAL = "minimal"
    WORK = "work"


class DocumentStateToken(BaseModel):
    """Comparable identity for the CAD and selection state used by a plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal[CONTEXT_CONTRACT_VERSION] = CONTEXT_CONTRACT_VERSION
    session_id: UUID
    document_id: str | None = Field(default=None, max_length=128)
    revision: int = Field(ge=0)
    document_fingerprint: Fingerprint
    selection_fingerprint: Fingerprint


class ContextShapeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    is_null: bool
    is_valid: bool
    volume_mm3: float | None = Field(default=None, ge=0)
    area_mm2: float | None = Field(default=None, ge=0)
    bounds_mm: tuple[float, float, float, float, float, float] | None = None
    solids: int = Field(default=0, ge=0)
    faces: int = Field(default=0, ge=0)
    edges: int = Field(default=0, ge=0)


class ContextObject(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    name: ObjectName
    label: str = Field(min_length=1, max_length=256)
    type_id: str = Field(min_length=1, max_length=256)
    has_error: bool
    selected: bool = False
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    position_mm: tuple[float, float, float] | None = None
    rotation_quaternion: tuple[float, float, float, float] | None = None
    shape: ContextShapeSummary | None = None


class ContextSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: ObjectName
    label: str = Field(min_length=1, max_length=256)
    type_id: str = Field(min_length=1, max_length=256)
    subelements: tuple[str, ...] = Field(default_factory=tuple, max_length=256)

    @field_validator("subelements")
    @classmethod
    def reject_duplicate_subelements(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("Selected subelements must be unique.")
        if any(len(item) > 128 for item in value):
            raise ValueError("A selected subelement name is too long.")
        return value


class ContextSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    object_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)


class ContextPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cursor: int = Field(ge=0)
    returned: int = Field(ge=0)
    total_objects: int = Field(ge=0)
    next_cursor: int | None = Field(default=None, ge=0)
    truncated: bool

    @model_validator(mode="after")
    def validate_page(self) -> ContextPage:
        if self.cursor > self.total_objects:
            raise ValueError("Context cursor cannot exceed the object count.")
        if self.returned > self.total_objects - self.cursor:
            raise ValueError("Context page returned too many objects.")
        expected_truncated = self.next_cursor is not None
        if self.truncated != expected_truncated:
            raise ValueError("Context pagination flags are inconsistent.")
        if self.next_cursor is not None:
            if self.next_cursor != self.cursor + self.returned:
                raise ValueError("The next context cursor is inconsistent.")
            if self.next_cursor >= self.total_objects:
                raise ValueError("A final context page cannot have a next cursor.")
        return self


class ContextSnapshot(BaseModel):
    """Bounded L0/L1 context shared by internal chat and MCP."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    contract_version: Literal[CONTEXT_CONTRACT_VERSION] = CONTEXT_CONTRACT_VERSION
    detail_level: ContextDetailLevel
    active: bool
    document_name: str | None = Field(default=None, max_length=128)
    document_label: str | None = Field(default=None, max_length=256)
    internal_length_unit: Literal["mm"] = "mm"
    state_token: DocumentStateToken
    summary: ContextSummary
    selection: tuple[ContextSelection, ...] = Field(default_factory=tuple, max_length=256)
    objects: tuple[ContextObject, ...] = Field(default_factory=tuple, max_length=100)
    recent_objects: tuple[ObjectName, ...] = Field(
        default_factory=tuple,
        max_length=MAX_RECENT_OBJECTS,
    )
    page: ContextPage

    @model_validator(mode="after")
    def validate_snapshot(self) -> ContextSnapshot:
        if self.active:
            if self.document_name is None or self.document_label is None:
                raise ValueError("An active context requires document identity.")
            if self.state_token.document_id != self.document_name:
                raise ValueError("The state token belongs to another document.")
        elif any(
            value is not None
            for value in (self.document_name, self.document_label, self.state_token.document_id)
        ):
            raise ValueError("An inactive context cannot identify a document.")
        if (
            self.detail_level is ContextDetailLevel.WORK
            and self.summary.selected_count != len(self.selection)
        ):
            raise ValueError("The selected object count is inconsistent.")
        if self.page.returned != len(self.objects):
            raise ValueError("The context page size is inconsistent.")
        payload = self.model_dump(mode="json")
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > MAX_CONTEXT_SNAPSHOT_BYTES:
            raise ValueError("The context snapshot is too large.")
        return self


@dataclass(frozen=True, slots=True)
class ContextObservation:
    token: DocumentStateToken
    recent_objects: tuple[str, ...]


@dataclass(slots=True)
class _TrackedDocument:
    document_fingerprint: str
    selection_fingerprint: str
    revision: int
    object_fingerprints: dict[str, str]
    recent_objects: tuple[str, ...]


class ContextStateTracker:
    """Track relevant manual and registered changes without importing FreeCAD."""

    def __init__(self, session_id: UUID | None = None) -> None:
        self._session_id = session_id or uuid4()
        self._documents: dict[str, _TrackedDocument] = {}
        self._pending_recent: dict[str, list[str]] = {}

    @property
    def session_id(self) -> UUID:
        return self._session_id

    def record_recent(self, document_id: str, object_names: tuple[str, ...]) -> None:
        pending = self._pending_recent.setdefault(document_id, [])
        for name in object_names:
            if name not in pending:
                pending.insert(0, name)

    def observe(
        self,
        document_id: str | None,
        document_fingerprint: str,
        selection_fingerprint: str,
        object_fingerprints: Mapping[str, str],
    ) -> ContextObservation:
        if document_id is None:
            return ContextObservation(
                token=DocumentStateToken(
                    session_id=self._session_id,
                    document_id=None,
                    revision=0,
                    document_fingerprint=document_fingerprint,
                    selection_fingerprint=selection_fingerprint,
                ),
                recent_objects=(),
            )

        current_objects = dict(object_fingerprints)
        previous = self._documents.get(document_id)
        if previous is None:
            revision = 1
            changed_objects = list(current_objects)
            previous_recent: tuple[str, ...] = ()
        else:
            changed = (
                previous.document_fingerprint != document_fingerprint
                or previous.selection_fingerprint != selection_fingerprint
            )
            revision = previous.revision + 1 if changed else previous.revision
            changed_objects = [
                name
                for name, fingerprint in current_objects.items()
                if previous.object_fingerprints.get(name) != fingerprint
            ]
            previous_recent = previous.recent_objects

        pending = self._pending_recent.pop(document_id, [])
        recent: list[str] = []
        for name in (*pending, *changed_objects, *previous_recent):
            if name in current_objects and name not in recent:
                recent.append(name)
            if len(recent) == MAX_RECENT_OBJECTS:
                break

        tracked = _TrackedDocument(
            document_fingerprint=document_fingerprint,
            selection_fingerprint=selection_fingerprint,
            revision=revision,
            object_fingerprints=current_objects,
            recent_objects=tuple(recent),
        )
        self._documents[document_id] = tracked
        return ContextObservation(
            token=DocumentStateToken(
                session_id=self._session_id,
                document_id=document_id,
                revision=revision,
                document_fingerprint=document_fingerprint,
                selection_fingerprint=selection_fingerprint,
            ),
            recent_objects=tracked.recent_objects,
        )

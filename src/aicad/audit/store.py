from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import secrets
import stat
from threading import RLock
from uuid import UUID

from platformdirs import user_data_path
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from aicad.audit.models import AuditActionRecord, AuditExportBundle
from aicad.audit.redaction import AuditRedactionError, redact_json


MAX_AUDIT_RECORD_BYTES = 512 * 1024
MAX_AUDIT_EXPORT_BYTES = 16 * 1024 * 1024
_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
_SCHEMA_DIRECTORY = "v1"


class AuditStoreError(RuntimeError):
    """Local audit history could not be stored or read safely."""


class AuditRetentionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_age_days: int = Field(default=90, ge=1, le=3_650)
    max_sessions: int = Field(default=50, ge=1, le=1_000)
    max_actions_per_session: int = Field(default=1_000, ge=1, le=100_000)


class AuditStore:
    """Atomic, bounded audit snapshots stored outside the project directory."""

    def __init__(
        self,
        root_directory: str | os.PathLike[str],
        *,
        retention: AuditRetentionPolicy | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._root = Path(root_directory).absolute()
        self._schema_root = self._root / _SCHEMA_DIRECTORY
        self._retention = retention or AuditRetentionPolicy()
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._lock = RLock()

    @property
    def root_directory(self) -> Path:
        return self._root

    @property
    def retention(self) -> AuditRetentionPolicy:
        return self._retention

    def save(
        self,
        record: AuditActionRecord,
        *,
        sensitive_values: tuple[str, ...] = (),
    ) -> AuditActionRecord:
        safe_record = self._redact_record(record, sensitive_values=sensitive_values)
        encoded = (safe_record.model_dump_json(indent=2) + "\n").encode("utf-8")
        if len(encoded) > MAX_AUDIT_RECORD_BYTES:
            raise AuditStoreError("The audit action exceeds the storage size limit.")

        with self._lock:
            session_directory = self._prepare_session_directory(record.session_id)
            destination = session_directory / f"{record.action_id.hex}.json"
            self._reject_symlink(destination)
            if destination.exists():
                existing = self._load_path(destination)
                if existing == safe_record:
                    return existing
                if safe_record.revision != existing.revision + 1:
                    raise AuditStoreError(
                        "An audit action update must advance exactly one revision."
                    )
                if (
                    existing.session_id != safe_record.session_id
                    or existing.action_id != safe_record.action_id
                    or existing.parent_action_id != safe_record.parent_action_id
                    or existing.source != safe_record.source
                    or existing.kind != safe_record.kind
                    or existing.started_at != safe_record.started_at
                ):
                    raise AuditStoreError("Immutable audit action identity changed.")
            elif safe_record.revision != 1:
                raise AuditStoreError("A new audit action must start at revision one.")
            self._atomic_write(destination, encoded, overwrite=True)
            self.prune()
        return safe_record

    def load(self, session_id: UUID, action_id: UUID) -> AuditActionRecord:
        with self._lock:
            session_directory = self._session_directory(session_id)
            self._require_safe_directory(session_directory)
            return self._load_path(session_directory / f"{action_id.hex}.json")

    def list_records(self, session_id: UUID) -> tuple[AuditActionRecord, ...]:
        with self._lock:
            session_directory = self._session_directory(session_id)
            self._require_safe_directory(session_directory)
            records = [
                self._load_path(path)
                for path in self._record_paths(session_directory)
            ]
        return tuple(sorted(records, key=lambda item: (item.started_at, item.action_id.hex)))

    def export_session(
        self,
        session_id: UUID,
        destination: str | os.PathLike[str],
        *,
        overwrite: bool = False,
        sensitive_values: tuple[str, ...] = (),
    ) -> Path:
        target = Path(destination).absolute()
        if target.is_symlink():
            raise AuditStoreError("The audit export destination cannot be a symlink.")
        if target.exists() and not overwrite:
            raise AuditStoreError("The audit export destination already exists.")
        if not target.parent.is_dir() or target.parent.is_symlink():
            raise AuditStoreError("The audit export directory is unavailable or unsafe.")

        records = tuple(
            self._redact_record(record, sensitive_values=sensitive_values)
            for record in self.list_records(session_id)
        )
        bundle = AuditExportBundle(
            session_id=session_id,
            exported_at=self._checked_now(),
            records=records,
        )
        checked = redact_json(
            bundle.model_dump(mode="json"),
            sensitive_values=sensitive_values,
        )
        safe_bundle = AuditExportBundle.model_validate(checked.value)
        encoded = (safe_bundle.model_dump_json(indent=2) + "\n").encode("utf-8")
        if len(encoded) > MAX_AUDIT_EXPORT_BYTES:
            raise AuditStoreError("The audit export exceeds the size limit.")
        with self._lock:
            self._atomic_write(target, encoded, overwrite=overwrite)
        return target

    def prune(self) -> int:
        """Apply retention only to recognized audit files without following links."""

        with self._lock:
            if not self._schema_root.exists():
                return 0
            self._require_safe_directory(self._schema_root)
            removed = 0
            cutoff = self._checked_now() - timedelta(
                days=self._retention.max_age_days
            )
            sessions: list[tuple[datetime, Path]] = []
            for directory in self._session_directories():
                records: list[tuple[datetime, Path]] = []
                for path in self._record_paths(directory):
                    try:
                        record = self._load_path(path)
                    except AuditStoreError:
                        continue
                    if record.started_at < cutoff:
                        path.unlink(missing_ok=True)
                        removed += 1
                    else:
                        records.append((record.started_at, path))
                records.sort(key=lambda item: (item[0], item[1].name), reverse=True)
                for _, path in records[self._retention.max_actions_per_session :]:
                    path.unlink(missing_ok=True)
                    removed += 1
                kept = records[: self._retention.max_actions_per_session]
                if kept:
                    sessions.append((kept[0][0], directory))
                else:
                    self._remove_empty_directory(directory)

            sessions.sort(key=lambda item: (item[0], item[1].name), reverse=True)
            for _, directory in sessions[self._retention.max_sessions :]:
                for path in self._record_paths(directory):
                    path.unlink(missing_ok=True)
                    removed += 1
                self._remove_empty_directory(directory)
            return removed

    def _redact_record(
        self,
        record: AuditActionRecord,
        *,
        sensitive_values: tuple[str, ...],
    ) -> AuditActionRecord:
        try:
            checked = redact_json(
                record.model_dump(mode="json"),
                sensitive_values=sensitive_values,
            )
            if not isinstance(checked.value, dict):
                raise AuditRedactionError("The redacted audit action is not an object.")
            checked.value["redaction_count"] = (
                record.redaction_count + checked.redaction_count
            )
            return AuditActionRecord.model_validate(checked.value)
        except (AuditRedactionError, ValidationError, ValueError) as exc:
            raise AuditStoreError("The audit action could not be redacted safely.") from exc

    def _prepare_session_directory(self, session_id: UUID) -> Path:
        for directory in (self._root, self._schema_root):
            self._prepare_directory(directory)
        session_directory = self._session_directory(session_id)
        self._prepare_directory(session_directory)
        return session_directory

    def _session_directory(self, session_id: UUID) -> Path:
        return self._schema_root / session_id.hex

    def _session_directories(self) -> tuple[Path, ...]:
        return tuple(
            path
            for path in self._schema_root.iterdir()
            if not path.is_symlink()
            and path.is_dir()
            and _ID_PATTERN.fullmatch(path.name) is not None
        )

    def _record_paths(self, session_directory: Path) -> tuple[Path, ...]:
        self._require_safe_directory(session_directory)
        return tuple(
            path
            for path in session_directory.iterdir()
            if not path.is_symlink()
            and path.is_file()
            and path.suffix == ".json"
            and _ID_PATTERN.fullmatch(path.stem) is not None
        )

    @staticmethod
    def _prepare_directory(path: Path) -> None:
        if path.is_symlink():
            raise AuditStoreError("An audit storage directory cannot be a symlink.")
        try:
            path.mkdir(parents=True, exist_ok=True)
            path.chmod(stat.S_IRWXU)
        except OSError as exc:
            raise AuditStoreError("The audit storage directory is unavailable.") from exc
        if not path.is_dir():
            raise AuditStoreError("The audit storage path is not a directory.")

    @staticmethod
    def _require_safe_directory(path: Path) -> None:
        if path.is_symlink() or not path.is_dir():
            raise AuditStoreError("The audit storage directory is unavailable or unsafe.")

    @staticmethod
    def _reject_symlink(path: Path) -> None:
        if path.is_symlink():
            raise AuditStoreError("An audit record cannot be a symlink.")

    @staticmethod
    def _remove_empty_directory(path: Path) -> None:
        try:
            next(path.iterdir())
        except StopIteration:
            path.rmdir()
        except (FileNotFoundError, OSError):
            pass

    @staticmethod
    def _load_path(path: Path) -> AuditActionRecord:
        if path.is_symlink():
            raise AuditStoreError("An audit record cannot be a symlink.")
        try:
            size = path.stat().st_size
            if size == 0 or size > MAX_AUDIT_RECORD_BYTES:
                raise AuditStoreError("The audit record size is invalid.")
            return AuditActionRecord.model_validate_json(path.read_bytes())
        except AuditStoreError:
            raise
        except FileNotFoundError as exc:
            raise AuditStoreError("The audit action was not found.") from exc
        except (OSError, ValidationError) as exc:
            raise AuditStoreError("The audit record is invalid.") from exc

    @staticmethod
    def _atomic_write(path: Path, payload: bytes, *, overwrite: bool) -> None:
        if path.is_symlink():
            raise AuditStoreError("The audit destination cannot be a symlink.")
        if path.exists() and not overwrite:
            raise AuditStoreError("The audit destination already exists.")
        temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
        descriptor: int | None = None
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = None
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError as exc:
            raise AuditStoreError("The audit file could not be written atomically.") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _checked_now(self) -> datetime:
        value = self._now()
        if value.utcoffset() is None:
            raise AuditStoreError("The audit clock must return a timezone-aware value.")
        return value


def default_audit_store() -> AuditStore:
    override = os.environ.get("AICAD_AUDIT_DIR")
    root = (
        Path(override)
        if override
        else user_data_path("ai-cad-workbench", appauthor=False) / "audit"
    )
    return AuditStore(root)

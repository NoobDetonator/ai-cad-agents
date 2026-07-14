from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
import math
from pathlib import Path
import re
from typing import Any
from uuid import UUID

from pydantic import BaseModel, JsonValue, SecretBytes, SecretStr


REDACTION_MARKER = "[REDACTED]"
TRUNCATION_MARKER = "[TRUNCATED]"
MAX_REDACTION_DEPTH = 16
MAX_REDACTION_ITEMS = 4_096
MAX_REDACTED_STRING_CHARS = 32_768

_SENSITIVE_KEY_PARTS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "credentials",
        "key",
        "password",
        "passwd",
        "private_key",
        "secret",
        "session_token",
        "token",
    }
)
_KEY_SPLIT_PATTERN = re.compile(r"[^a-z0-9]+")
_BEARER_PATTERN = re.compile(
    r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"
)
_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b("
    r"api[ _-]?key|access[ _-]?token|refresh[ _-]?token|session[ _-]?token|"
    r"authorization|credential|password|passwd|private[ _-]?key|secret|token"
    r")(\s*[:=]\s*|\s+)([^\s]+)"
)
_WINDOWS_USER_PATH_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:[A-Z]:\\Users\\[^\\\s]+(?:\\[^\s]*)?)"
)
_POSIX_USER_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])/(?:home|Users)/[^/\s]+(?:/[^\s]*)?"
)


class AuditRedactionError(ValueError):
    """Audit data could not be converted to bounded, safe JSON."""


@dataclass(frozen=True, slots=True)
class RedactionResult:
    value: JsonValue
    redaction_count: int


def is_sensitive_key(key: str) -> bool:
    normalized = key.strip().casefold().replace("-", "_").replace(" ", "_")
    if normalized in {"state_token", "base_state_token"}:
        return False
    if normalized in _SENSITIVE_KEY_PARTS:
        return True
    parts = tuple(part for part in _KEY_SPLIT_PATTERN.split(normalized) if part)
    if any(part in _SENSITIVE_KEY_PARTS for part in parts):
        return True
    return normalized.endswith(("_token", "_secret", "_password", "_api_key"))


def redact_json(
    value: Any,
    *,
    sensitive_values: Sequence[str] = (),
    max_depth: int = MAX_REDACTION_DEPTH,
    max_items: int = MAX_REDACTION_ITEMS,
    max_string_chars: int = MAX_REDACTED_STRING_CHARS,
) -> RedactionResult:
    """Return JSON-compatible data with secrets and local user paths removed."""

    if max_depth < 1 or max_items < 1 or max_string_chars < 1:
        raise ValueError("Redaction limits must be positive.")
    known_secrets = tuple(
        item for item in sensitive_values if isinstance(item, str) and item
    )
    seen_items = 0

    def visit(item: Any, *, depth: int) -> tuple[JsonValue, int]:
        nonlocal seen_items
        if depth > max_depth:
            raise AuditRedactionError("Audit data exceeds the nesting limit.")
        seen_items += 1
        if seen_items > max_items:
            raise AuditRedactionError("Audit data exceeds the item limit.")

        if isinstance(item, (SecretStr, SecretBytes, bytes, bytearray, memoryview)):
            return REDACTION_MARKER, 1
        if isinstance(item, BaseModel):
            item = item.model_dump(mode="json")
        elif isinstance(item, Enum):
            item = item.value
        elif isinstance(item, (UUID, datetime, date, Path)):
            item = str(item)

        if item is None or isinstance(item, (str, bool, int, float)):
            if isinstance(item, float) and not math.isfinite(item):
                raise AuditRedactionError("Audit data contains a non-finite number.")
            if isinstance(item, str):
                return redact_text(
                    item,
                    sensitive_values=known_secrets,
                    max_chars=max_string_chars,
                )
            return item, 0

        if isinstance(item, Mapping):
            result: dict[str, JsonValue] = {}
            redactions = 0
            for key, nested in item.items():
                if not isinstance(key, str):
                    raise AuditRedactionError("Audit mapping keys must be strings.")
                if is_sensitive_key(key):
                    result[key] = REDACTION_MARKER
                    redactions += 1
                    continue
                checked, count = visit(nested, depth=depth + 1)
                result[key] = checked
                redactions += count
            return result, redactions

        if isinstance(item, Sequence):
            result_items: list[JsonValue] = []
            redactions = 0
            for nested in item:
                checked, count = visit(nested, depth=depth + 1)
                result_items.append(checked)
                redactions += count
            return result_items, redactions

        raise AuditRedactionError(
            f"Audit data contains unsupported type {type(item).__name__}."
        )

    checked, count = visit(value, depth=0)
    return RedactionResult(value=checked, redaction_count=count)


def redact_text(
    text: str,
    *,
    sensitive_values: Sequence[str] = (),
    max_chars: int = MAX_REDACTED_STRING_CHARS,
) -> tuple[str, int]:
    if max_chars < 1:
        raise ValueError("The audit text limit must be positive.")
    checked = text
    count = 0

    for secret in sensitive_values:
        if secret and secret in checked:
            occurrences = checked.count(secret)
            checked = checked.replace(secret, REDACTION_MARKER)
            count += occurrences

    def replace_bearer(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"Bearer {REDACTION_MARKER}"

    def replace_assignment(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"{match.group(1)}{match.group(2)}{REDACTION_MARKER}"

    def replace_path(_: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return "[REDACTED_PATH]"

    checked = _BEARER_PATTERN.sub(replace_bearer, checked)
    checked = _ASSIGNMENT_PATTERN.sub(replace_assignment, checked)
    checked = _WINDOWS_USER_PATH_PATTERN.sub(replace_path, checked)
    checked = _POSIX_USER_PATH_PATTERN.sub(replace_path, checked)
    if len(checked) > max_chars:
        checked = checked[:max_chars] + TRUNCATION_MARKER
        count += 1
    return checked, count

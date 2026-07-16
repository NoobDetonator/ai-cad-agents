from __future__ import annotations

import os
from pathlib import Path
import re
from uuid import uuid4

from platformdirs import user_cache_path


CAPTURE_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
MAX_CAPTURE_BYTES = 8 * 1024 * 1024
MAX_CACHED_CAPTURES = 8
MAX_CAPTURE_BATCH_BYTES = 32 * 1024 * 1024


def visual_cache_directory() -> Path:
    override = os.environ.get("AICAD_VISUAL_CACHE")
    root = Path(override) if override else user_cache_path("ai-cad-workbench") / "views"
    root.mkdir(parents=True, exist_ok=True)
    return root


def new_capture_path() -> tuple[str, Path]:
    capture_id = uuid4().hex
    return capture_id, visual_cache_directory() / f"{capture_id}.png"


def capture_path(capture_id: str) -> Path:
    if CAPTURE_ID_PATTERN.fullmatch(capture_id) is None:
        raise ValueError("The visual capture ID is invalid.")
    return visual_cache_directory() / f"{capture_id}.png"


def read_capture(capture_id: str) -> bytes:
    path = capture_path(capture_id)
    payload = path.read_bytes()
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("The cached visual context is not a PNG image.")
    if len(payload) > MAX_CAPTURE_BYTES:
        raise ValueError("The cached visual context exceeds the size limit.")
    return payload


def prune_visual_cache() -> None:
    files = sorted(
        visual_cache_directory().glob("*.png"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for path in files[MAX_CACHED_CAPTURES:]:
        path.unlink(missing_ok=True)

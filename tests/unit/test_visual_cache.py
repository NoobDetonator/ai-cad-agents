from __future__ import annotations

import os

from aicad.core.visual_cache import (
    MAX_CACHED_CAPTURES,
    capture_path,
    new_capture_path,
    prune_visual_cache,
    read_capture,
)


def test_visual_cache_uses_opaque_ids_and_prunes_old_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AICAD_VISUAL_CACHE", str(tmp_path))
    created = []
    for index in range(MAX_CACHED_CAPTURES + 2):
        capture_id, path = new_capture_path()
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes([index]))
        os.utime(path, (index + 1, index + 1))
        created.append(capture_id)

    prune_visual_cache()

    assert len(list(tmp_path.glob("*.png"))) == MAX_CACHED_CAPTURES
    assert not capture_path(created[0]).exists()
    assert read_capture(created[-1]).startswith(b"\x89PNG")

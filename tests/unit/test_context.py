from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from aicad.core.context import (
    ContextDetailLevel,
    ContextPage,
    ContextSnapshot,
    ContextStateTracker,
    ContextSummary,
)


FINGERPRINT_A = "a" * 64
FINGERPRINT_B = "b" * 64
FINGERPRINT_C = "c" * 64
SESSION_ID = UUID("12345678-1234-5678-1234-567812345678")


def test_state_tracker_is_stable_and_detects_manual_object_changes() -> None:
    tracker = ContextStateTracker(SESSION_ID)
    first = tracker.observe(
        "Document",
        FINGERPRINT_A,
        FINGERPRINT_B,
        {"Box": FINGERPRINT_A},
    )
    unchanged = tracker.observe(
        "Document",
        FINGERPRINT_A,
        FINGERPRINT_B,
        {"Box": FINGERPRINT_A},
    )
    changed = tracker.observe(
        "Document",
        FINGERPRINT_C,
        FINGERPRINT_B,
        {"Box": FINGERPRINT_C},
    )

    assert first.token.revision == 1
    assert unchanged.token == first.token
    assert changed.token.revision == 2
    assert changed.token.document_fingerprint == FINGERPRINT_C
    assert changed.recent_objects == ("Box",)


def test_state_tracker_detects_selection_and_registered_recent_objects() -> None:
    tracker = ContextStateTracker(SESSION_ID)
    tracker.observe("Document", FINGERPRINT_A, FINGERPRINT_A, {})
    tracker.record_recent("Document", ("Cylinder",))

    observed = tracker.observe(
        "Document",
        FINGERPRINT_B,
        FINGERPRINT_C,
        {"Cylinder": FINGERPRINT_B},
    )

    assert observed.token.revision == 2
    assert observed.token.selection_fingerprint == FINGERPRINT_C
    assert observed.recent_objects == ("Cylinder",)


def test_inactive_minimal_snapshot_is_versioned_and_bounded() -> None:
    observation = ContextStateTracker(SESSION_ID).observe(
        None,
        FINGERPRINT_A,
        FINGERPRINT_B,
        {},
    )
    snapshot = ContextSnapshot(
        detail_level=ContextDetailLevel.MINIMAL,
        active=False,
        state_token=observation.token,
        summary=ContextSummary(object_count=0, error_count=0, selected_count=0),
        page=ContextPage(
            cursor=0,
            returned=0,
            total_objects=0,
            truncated=False,
        ),
    )

    assert snapshot.contract_version == "1.0"
    assert snapshot.internal_length_unit == "mm"
    assert snapshot.state_token.revision == 0


def test_context_page_rejects_inconsistent_pagination() -> None:
    with pytest.raises(ValidationError, match="next context cursor"):
        ContextPage(
            cursor=5,
            returned=2,
            total_objects=10,
            next_cursor=9,
            truncated=True,
        )

"""Semantic validation at the Recovery persistence boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import DamagedJournalError, DamagedStateError

_STATUSES = {"active", "paused", "released"}
_STATE_FIELDS = {
    "schema_version": int,
    "worktree_id": str,
    "binding_id": str,
    "work": str,
    "cycle_id": str,
    "status": str,
    "bound_at": str,
}
_RECORD_FIELDS = {
    "bound": ((), ()),
    "intent": (("action_id", "action"), ()),
    "begin": (("action_id",), ("target", "expected_change", "recovery_check")),
    "end": (("action_id",), ("observation",)),
    "operation-handoff": (
        ("handoff_id", "action_id", "summary", "recovery_instructions"),
        (),
    ),
    "paused": ((), ()),
    "released": ((), ()),
    "rotated": (
        (
            "checkpoint_event_id",
            "checkpoint_commit",
            "head_at_rotation",
            "next_intent",
        ),
        (),
    ),
}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_state(
    state: dict[str, Any], path: Path, *, expected_worktree_id: str
) -> None:
    for field, expected_type in _STATE_FIELDS.items():
        if type(state.get(field)) is not expected_type:
            raise DamagedStateError(
                f"damaged recovery state at {path}: invalid {field}"
            )
    if state["schema_version"] != 1:
        raise DamagedStateError(
            f"damaged recovery state at {path}: unsupported schema_version"
        )
    for field in ("worktree_id", "binding_id", "work", "cycle_id", "bound_at"):
        if not _text(state[field]):
            raise DamagedStateError(f"damaged recovery state at {path}: empty {field}")
    if state["worktree_id"] != expected_worktree_id:
        raise DamagedStateError(
            f"damaged recovery state at {path}: worktree identity mismatch"
        )
    if state["status"] not in _STATUSES:
        raise DamagedStateError(f"damaged recovery state at {path}: invalid status")


def validate_record(
    record: dict[str, Any],
    path: Path,
    *,
    expected_binding_id: str | None = None,
    expected_work: str | None = None,
    expected_cycle_id: str | None = None,
) -> None:
    required_text = (
        "record_id",
        "recorded_at",
        "binding_id",
        "work",
        "cycle_id",
        "type",
    )
    if record.get("schema_version") != 1:
        raise _journal_error(path, "invalid schema_version")
    for field in required_text:
        if not _text(record.get(field)):
            raise _journal_error(path, f"invalid {field}")
    record_type = record["type"]
    if record_type not in _RECORD_FIELDS:
        raise _journal_error(path, f"unknown record type {record['type']}")
    expected = {
        "binding_id": expected_binding_id,
        "work": expected_work,
        "cycle_id": expected_cycle_id,
    }
    for field, value in expected.items():
        if value is not None and record[field] != value:
            raise _journal_error(path, f"{field} does not match journal binding")

    _validate_record_payload(record, path, record_type)


def _validate_record_payload(
    record: dict[str, Any], path: Path, record_type: str
) -> None:
    text_fields, object_fields = _RECORD_FIELDS[record_type]
    for field in text_fields:
        if not _text(record.get(field)):
            raise _journal_error(path, f"invalid {record_type} {field}")
    for field in object_fields:
        if not isinstance(record.get(field), dict):
            raise _journal_error(path, f"invalid {record_type} {field}")

    if record_type == "intent":
        scope = record.get("scope")
        if not isinstance(scope, list) or any(
            not isinstance(item, str) for item in scope
        ):
            raise _journal_error(path, "intent scope must be a string list")
    elif (
        record_type == "rotated"
        and record.get("durable_events_acknowledged") is not True
    ):
        raise _journal_error(path, "rotation lacks durable-event acknowledgement")


def _journal_error(path: Path, reason: str) -> DamagedJournalError:
    return DamagedJournalError(f"damaged recovery journal at {path}: {reason}")

"""Pure projections over validated Recovery journal records."""

from __future__ import annotations

from typing import Any


def _operation_records(records: list[dict[str, Any]]):
    """Index operation records once for the projections below."""

    begins: dict[tuple[str, str], dict[str, Any]] = {}
    ended: set[tuple[str, str]] = set()
    handoffs: list[dict[str, Any]] = []
    for record in records:
        action_id = record.get("action_id")
        if not isinstance(action_id, str):
            continue
        key = (record["binding_id"], action_id)
        if record["type"] == "begin":
            begins[key] = record
        elif record["type"] == "end":
            ended.add(key)
        elif record["type"] == "operation-handoff":
            handoffs.append(record)
    return begins, ended, handoffs


def open_begins(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    begins, ended, _ = _operation_records(records)
    return [record for key, record in begins.items() if key not in ended]


def unexplained_begins(
    records: list[dict[str, Any]],
    open_records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    open_records = open_records if open_records is not None else open_begins(records)
    handed_off = {
        record["action_id"]
        for record in records
        if record["type"] == "operation-handoff"
    }
    return [record for record in open_records if record["action_id"] not in handed_off]


def pending_handoffs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    begins, ended, handoffs = _operation_records(records)
    pending = []
    for handoff in handoffs:
        key = (handoff["binding_id"], handoff["action_id"])
        begin = begins.get(key)
        if begin is not None and key not in ended:
            pending.append({**handoff, "begin": begin})
    return sorted(pending, key=lambda item: item["recorded_at"])

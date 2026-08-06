"""Canonical shared-event identity and the narrow storage port."""

from __future__ import annotations

import copy
import json
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from ..errors import EventIdentityConflict, EventValidationError

STRUCTURAL_KINDS = {
    "checkpoint-created",
    "checkpoint-remapped",
    "event-resolved",
    "verification-observed",
    "work-reopened",
}

_STRUCTURAL_FIELDS = {
    "checkpoint-created": ("commit",),
    "checkpoint-remapped": (
        "checkpoint_event_id",
        "old_commit",
        "new_commit",
        "reason",
    ),
    "verification-observed": ("subject_commit", "observation"),
    "event-resolved": ("resolves",),
}


class SharedWorkLogStore(Protocol):
    """Validated shared events with conflict-aware logical lookup."""

    def append_event(self, work: str, event: dict[str, Any]) -> dict[str, Any]: ...

    def list_events(self, work: str) -> list[dict[str, Any]]: ...

    def find_event(self, work: str, event_id: str) -> dict[str, Any] | None: ...


def durable_fields(event: dict[str, Any]) -> dict[str, Any]:
    """Copy the provider-independent fields of a validated event."""

    return copy.deepcopy(
        {key: value for key, value in event.items() if key != "remote"}
    )


def canonical_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Return durable fields as JSON-native values, excluding provider facts."""

    durable = durable_fields(event)
    try:
        encoded = json.dumps(
            durable,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise EventValidationError(
            f"shared event is not canonical JSON: {error}"
        ) from error
    canonical = json.loads(encoded)
    if canonical != durable:
        raise EventValidationError("shared event must contain only JSON-native values")
    return canonical


def prepare_event(
    event: dict[str, Any], *, expected_work: str | None = None
) -> dict[str, Any]:
    """Copy, canonicalize and validate a durable shared event."""

    prepared = canonical_payload(event)
    _validate_event(prepared, expected_work=expected_work)
    return prepared


def new_event(
    work: str,
    cycle_id: str,
    kind: str,
    producer: str,
    *,
    summary: str | None = None,
    observation: dict[str, Any] | None = None,
    references: list[str] | None = None,
    resolves: list[str] | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    """Build an unvalidated event for a dedicated publication operation."""

    event: dict[str, Any] = {
        "event_id": event_id or f"evt-{uuid.uuid4().hex}",
        "kind": kind,
        "work": work,
        "cycle_id": cycle_id,
        "producer": producer,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    if summary is not None:
        event["summary"] = summary
    if observation is not None:
        event["observation"] = observation
    if references:
        event["references"] = references
    if resolves:
        event["resolves"] = resolves
    return event


def _validate_event(event: dict[str, Any], expected_work: str | None = None) -> None:
    required = (
        "event_id",
        "kind",
        "work",
        "cycle_id",
        "producer",
        "created_at",
    )
    missing = [field for field in required if not event.get(field)]
    if missing:
        raise EventValidationError(f"shared event missing: {', '.join(missing)}")
    if any(not isinstance(event[field], str) for field in required):
        raise EventValidationError("shared event identity fields must be strings")
    if expected_work is not None and event["work"] != expected_work:
        raise EventValidationError(
            f"event work {event['work']} does not match partition {expected_work}"
        )
    if not event["event_id"].startswith("evt-"):
        raise EventValidationError("event_id must be a stable evt-* identity")

    _validate_relations(event)
    _validate_structural_fields(event)
    _validate_content(event)


def _validate_relations(event: dict[str, Any]) -> None:
    """Validate fields that point at other events or project artifacts."""

    resolves = event.get("resolves", [])
    if not isinstance(resolves, list) or any(
        not isinstance(item, str) or not item.startswith("evt-") for item in resolves
    ):
        raise EventValidationError("resolves must contain event_id values")
    references = event.get("references", [])
    if not isinstance(references, list) or any(
        not isinstance(reference, str) or not reference.strip()
        for reference in references
    ):
        raise EventValidationError("references must contain non-empty strings")


def _validate_structural_fields(event: dict[str, Any]) -> None:
    """Validate fields owned by dedicated structural event operations."""

    missing_structural = [
        field
        for field in _STRUCTURAL_FIELDS.get(event["kind"], ())
        if event.get(field) in (None, "", [])
    ]
    if missing_structural:
        raise EventValidationError(
            f"{event['kind']} requires {', '.join(missing_structural)}"
        )
    string_structural = {
        field
        for field in _STRUCTURAL_FIELDS.get(event["kind"], ())
        if field not in {"observation", "resolves"}
    }
    if any(
        not isinstance(event[field], str) or not event[field].strip()
        for field in string_structural
    ):
        raise EventValidationError(
            f"{event['kind']} structural identity fields must be strings"
        )
    checkpoint_event_id = event.get("checkpoint_event_id")
    if checkpoint_event_id is not None and (
        not isinstance(checkpoint_event_id, str)
        or not checkpoint_event_id.startswith("evt-")
    ):
        raise EventValidationError("checkpoint_event_id must be an event identity")


def _validate_content(event: dict[str, Any]) -> None:
    """Validate optional fact content interpreted by readers and filters."""

    summary = event.get("summary")
    if "summary" in event and (not isinstance(summary, str) or not summary.strip()):
        raise EventValidationError("summary must be a non-empty string")
    observation = event.get("observation")
    if "observation" in event and not isinstance(observation, dict):
        raise EventValidationError("observation must be an object")
    if "artifact" in event and (
        not isinstance(event["artifact"], dict) or not event["artifact"]
    ):
        raise EventValidationError("artifact must be a non-empty object")
    if "unresolved" in event and not isinstance(event["unresolved"], bool):
        raise EventValidationError("unresolved must be a boolean")
    if "pr" in event and (
        isinstance(event["pr"], bool)
        or not isinstance(event["pr"], int)
        or event["pr"] < 1
    ):
        raise EventValidationError("pr must be a positive integer")
    if summary is None and "observation" not in event:
        raise EventValidationError("shared event requires summary or observation")


def assert_same_event(expected: dict[str, Any], observed: dict[str, Any]) -> None:
    """Reject a stable identity that forks into different durable facts."""

    if durable_fields(expected) != durable_fields(observed):
        event_id = expected.get("event_id", "<unknown>")
        raise EventIdentityConflict(f"event identity conflict for {event_id}")


def logical_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse identical physical comments; reject identity forks."""

    by_id: dict[str, dict[str, Any]] = {}
    logical: list[dict[str, Any]] = []
    for event in events:
        event_id = event["event_id"]
        existing = by_id.get(event_id)
        if existing is None:
            by_id[event_id] = event
            logical.append(event)
        else:
            assert_same_event(existing, event)
    return logical

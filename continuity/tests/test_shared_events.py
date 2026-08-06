from __future__ import annotations

import pytest
from continuity.worklog.events import canonical_payload, prepare_event

from continuity import (
    CheckpointConflictError,
    EventIdentityConflict,
    EventValidationError,
    SharedStoreError,
    WorkEventPublisher,
)

from .conftest import git


def test_interpreted_optional_event_fields_are_validated():
    base = {
        "event_id": "evt-invalid-optional",
        "kind": "finding",
        "work": "issue-5",
        "cycle_id": "cycle-1",
        "producer": "agent:test",
        "created_at": "2026-08-06T00:00:00Z",
        "summary": "Fact",
    }
    invalid_fields = (
        ("references", ["valid", 3], "references"),
        ("artifact", [], "artifact"),
        ("unresolved", "yes", "unresolved"),
        ("pr", True, "pr"),
        ("observation", "passed", "observation"),
    )
    for field, value, message in invalid_fields:
        with pytest.raises(EventValidationError, match=message):
            prepare_event({**base, field: value})


def test_structural_event_requires_domain_operation(recovery, publisher):
    recovery.bind("issue-5", "cycle-1")
    with pytest.raises(EventValidationError, match="domain operation"):
        publisher.append_significant(
            "issue-5",
            "cycle-1",
            "checkpoint-created",
            "agent:test",
            summary="missing the checkpoint contract",
        )


def test_shared_append_response_loss_is_reconciled_by_event_id(
    repo, shared, recovery, reader, publisher
):
    recovery.bind("issue-5", "cycle-1")
    event_id = "evt-response-lost"
    shared.lose_response_once(event_id)

    with pytest.raises(SharedStoreError, match="response loss"):
        publisher.create_checkpoint(
            "issue-5",
            "cycle-1",
            git(repo, "rev-parse", "HEAD"),
            "agent:a",
            event_id=event_id,
        )

    assert shared.append_count == 1
    assert recovery.open_begins()[0]["target"]["event_id"] == event_id

    replacement = WorkEventPublisher(reader, recovery)
    result = replacement.reconcile_pending_shared_events()
    assert result == [
        {
            "action_id": f"publish-{event_id}",
            "event_id": event_id,
            "status": "confirmed",
            "retried": False,
        }
    ]
    assert shared.append_count == 1
    assert recovery.open_begins() == []


def test_identical_physical_comments_are_one_logical_event(
    shared, recovery, reader, publisher
):
    recovery.bind("issue-5", "cycle-1")
    event = publisher.append_significant(
        "issue-5",
        "cycle-1",
        "finding",
        "agent:a",
        summary="One durable fact",
        event_id="evt-physical-duplicate",
    )

    shared.append_event("issue-5", event)

    assert shared.append_count == 2
    assert [item["event_id"] for item in reader.events("issue-5")] == [
        "evt-physical-duplicate"
    ]


def test_identity_conflict_keeps_unknown_publication_open(
    shared, recovery, reader, publisher
):
    recovery.bind("issue-5", "cycle-1")
    shared.lose_response_once("evt-conflict")
    with pytest.raises(SharedStoreError, match="response loss"):
        publisher.append_significant(
            "issue-5",
            "cycle-1",
            "finding",
            "agent:a",
            summary="Expected fact",
            event_id="evt-conflict",
        )

    expected = recovery.open_begins()[0]["expected_change"]["event"]
    conflicting = prepare_event(
        {**canonical_payload(expected), "summary": "Conflicting fact"}
    )
    shared.append_event("issue-5", conflicting)

    replacement = WorkEventPublisher(reader, recovery)
    with pytest.raises(EventIdentityConflict, match="identity conflict"):
        replacement.reconcile_pending_shared_events()
    assert len(recovery.open_begins()) == 1


def test_collaborator_events_and_resolves_use_stable_identity(
    recovery, reader, publisher
):
    recovery.bind("issue-5", "cycle-1")
    publisher.append_significant(
        "issue-5",
        "cycle-1",
        "finding",
        "agent:a",
        summary="The old storage model is unsafe",
        unresolved=True,
        event_id="evt-finding",
    )
    other = publisher.append_significant(
        "issue-5",
        "cycle-1",
        "finding",
        "agent:b",
        summary="A second collaborator found another risk",
        unresolved=True,
        event_id="evt-other-risk",
    )
    assert {event["event_id"] for event in reader.events("issue-5")} == {
        "evt-finding",
        "evt-other-risk",
    }

    resolution = publisher.resolve_event(
        "issue-5",
        "cycle-1",
        "evt-finding",
        "agent:b",
        "The shared Issue store replaces it",
        event_id="evt-resolution",
    )
    assert resolution["resolves"] == ["evt-finding"]
    assert reader.unresolved_events("issue-5") == [other]
    assert all("seq" not in event for event in reader.events("issue-5"))


def test_checkpoint_remap_fork_is_diagnostic(repo, shared, recovery, reader, publisher):
    recovery.bind("issue-5", "cycle-1")
    old_commit = git(repo, "rev-parse", "HEAD")
    checkpoint = publisher.create_checkpoint(
        "issue-5",
        "cycle-1",
        old_commit,
        "agent:a",
        event_id="evt-forked-checkpoint",
    )
    first_commit = git(
        repo, "commit-tree", old_commit + "^{tree}", "-p", old_commit, "-m", "first"
    )
    second_commit = git(
        repo, "commit-tree", old_commit + "^{tree}", "-p", old_commit, "-m", "second"
    )

    for event_id, new_commit in (
        ("evt-remap-first", first_commit),
        ("evt-remap-second", second_commit),
    ):
        shared.append_event(
            "issue-5",
            prepare_event(
                {
                    "event_id": event_id,
                    "kind": "checkpoint-remapped",
                    "work": "issue-5",
                    "cycle_id": "cycle-1",
                    "producer": "agent:test",
                    "created_at": f"2026-08-07T00:00:0{len(event_id)}Z",
                    "summary": "Concurrent history remap",
                    "checkpoint_event_id": checkpoint["event_id"],
                    "old_commit": old_commit,
                    "new_commit": new_commit,
                    "reason": "concurrent rewrite",
                }
            ),
        )

    with pytest.raises(
        CheckpointConflictError, match="checkpoint remap conflict"
    ) as failure:
        reader.resolve_checkpoint_event(checkpoint)
    assert failure.value.code == "checkpoint_conflict"

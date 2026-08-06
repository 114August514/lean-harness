from __future__ import annotations

import threading

import pytest
from continuity.recovery import utc_now
from continuity.shared import parse_comment, render_comment

from continuity import EventValidationError, SharedStoreError, WorkEvents

from .conftest import commit_file, git
from .fakes import FakeSharedStore


def test_github_comment_is_machine_identifiable_and_human_readable(repo, system):
    _, recovery, events, _ = system
    recovery.bind("issue-5", "cycle-1")
    event = events.create_checkpoint(
        "issue-5",
        "cycle-1",
        git(repo, "rev-parse", "HEAD"),
        "agent:test",
        summary="Complete shared work-log reference implementation",
        event_id="evt-comment-format",
    )

    body = render_comment(
        {key: value for key, value in event.items() if key != "remote"}
    )
    assert "<!-- lean-harness-work-event:v1 event_id=evt-comment-format -->" in body
    assert "Complete shared work-log reference implementation" in body
    parsed = parse_comment(
        {
            "id": 41,
            "created_at": "2026-08-06T00:00:00Z",
            "html_url": "https://example.test/comments/41",
            "body": body,
        }
    )
    assert parsed["event_id"] == "evt-comment-format"
    assert parsed["remote"]["comment_id"] == 41


def test_structural_event_cannot_bypass_domain_operation(repo, system):
    _, recovery, events, _ = system
    recovery.bind("issue-5", "cycle-1")
    with pytest.raises(EventValidationError, match="domain operation"):
        events.append_significant(
            "issue-5",
            "cycle-1",
            "checkpoint-created",
            "agent:test",
            summary="missing the checkpoint contract",
        )

    checkpoint = events.create_checkpoint(
        "issue-5",
        "cycle-1",
        git(repo, "rev-parse", "HEAD"),
        "agent:test",
    )
    assert checkpoint["kind"] == "checkpoint-created"
    assert "seq" not in checkpoint


def test_shared_append_response_loss_is_reconciled_by_event_id(repo, system):
    shared, recovery, events, _ = system
    recovery.bind("issue-5", "cycle-1")
    event_id = "evt-response-lost"
    shared.lose_response_once(event_id)

    with pytest.raises(SharedStoreError, match="response loss"):
        events.create_checkpoint(
            "issue-5",
            "cycle-1",
            git(repo, "rev-parse", "HEAD"),
            "agent:a",
            event_id=event_id,
        )

    assert shared.append_count == 1
    assert recovery.open_begins()[0]["target"]["event_id"] == event_id

    replacement = WorkEvents(repo, shared, recovery)
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


def test_unresolved_and_resolves_use_event_identity(repo, system):
    _, recovery, events, _ = system
    recovery.bind("issue-5", "cycle-1")
    finding = events.append_significant(
        "issue-5",
        "cycle-1",
        "finding",
        "agent:a",
        summary="The old storage model is unsafe",
        unresolved=True,
        event_id="evt-finding",
    )
    assert events.unresolved_events("issue-5") == [finding]

    resolution = events.resolve_event(
        "issue-5",
        "cycle-1",
        "evt-finding",
        "agent:b",
        "The shared Issue store replaces it",
        event_id="evt-resolution",
    )
    assert resolution["resolves"] == ["evt-finding"]
    assert events.unresolved_events("issue-5") == []
    assert all("seq" not in event for event in events.events("issue-5"))


def test_two_collaborators_append_without_a_global_sequence():
    shared = FakeSharedStore()
    barrier = threading.Barrier(3)

    def append(event_id: str, producer: str) -> None:
        event = {
            "event_id": event_id,
            "kind": "finding",
            "work": "issue-5",
            "cycle_id": "cycle-1",
            "producer": producer,
            "created_at": utc_now(),
            "summary": producer,
            "unresolved": True,
        }
        barrier.wait()
        shared.append_event("issue-5", event)

    workers = [
        threading.Thread(target=append, args=("evt-a", "collaborator:a")),
        threading.Thread(target=append, args=("evt-b", "collaborator:b")),
    ]
    for worker in workers:
        worker.start()
    barrier.wait()
    for worker in workers:
        worker.join()

    events = shared.list_events("issue-5")
    assert {event["event_id"] for event in events} == {"evt-a", "evt-b"}
    assert all("seq" not in event for event in events)


def test_checkpoint_remap_is_append_only(repo, system):
    _, recovery, events, _ = system
    recovery.bind("issue-5", "cycle-1")
    old = git(repo, "rev-parse", "HEAD")
    checkpoint = events.create_checkpoint(
        "issue-5", "cycle-1", old, "agent:a", event_id="evt-checkpoint"
    )
    new = commit_file(repo, "new.py", "value = 1\n", "replacement artifact")
    remap = events.remap_checkpoint(
        "issue-5",
        "cycle-1",
        checkpoint["event_id"],
        new,
        "squash",
        "agent:a",
        event_id="evt-remap",
    )

    assert events.find_event("issue-5", "evt-checkpoint")["commit"] == old
    assert remap["old_commit"] == old
    assert events.resolve_checkpoint_event(checkpoint) == new

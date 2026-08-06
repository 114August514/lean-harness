from __future__ import annotations

import pytest
from continuity.shared import parse_comment, render_comment

from continuity import EventValidationError, SharedStoreError, WorkEvents

from .conftest import git


def test_github_comment_is_machine_identifiable_and_human_readable():
    event = {
        "event_id": "evt-comment-format",
        "kind": "finding",
        "work": "issue-5",
        "cycle_id": "cycle-1",
        "producer": "agent:test",
        "created_at": "2026-08-06T00:00:00Z",
        "summary": "Human-readable durable fact",
    }
    body = render_comment(event)
    assert "<!-- lean-harness-work-event:v1 event_id=evt-comment-format -->" in body
    assert "Human-readable durable fact" in body
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


def test_collaborator_events_and_resolves_use_stable_identity(repo, system):
    _, recovery, events, _ = system
    recovery.bind("issue-5", "cycle-1")
    events.append_significant(
        "issue-5",
        "cycle-1",
        "finding",
        "agent:a",
        summary="The old storage model is unsafe",
        unresolved=True,
        event_id="evt-finding",
    )
    other = events.append_significant(
        "issue-5",
        "cycle-1",
        "finding",
        "agent:b",
        summary="A second collaborator found another risk",
        unresolved=True,
        event_id="evt-other-risk",
    )
    assert {event["event_id"] for event in events.events("issue-5")} == {
        "evt-finding",
        "evt-other-risk",
    }

    resolution = events.resolve_event(
        "issue-5",
        "cycle-1",
        "evt-finding",
        "agent:b",
        "The shared Issue store replaces it",
        event_id="evt-resolution",
    )
    assert resolution["resolves"] == ["evt-finding"]
    assert events.unresolved_events("issue-5") == [other]
    assert all("seq" not in event for event in events.events("issue-5"))

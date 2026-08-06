from __future__ import annotations

import json
import subprocess

import continuity.shared as shared_module
import pytest
from continuity.shared import render_comment

from continuity import GitHubIssueSharedStore, SharedStoreError


def _event(**overrides):
    event = {
        "event_id": "evt-github-adapter",
        "kind": "finding",
        "work": "issue-5",
        "cycle_id": "cycle-1",
        "producer": "agent:test",
        "created_at": "2026-08-06T00:00:00Z",
        "summary": "Adapter fact",
    }
    event.update(overrides)
    return event


def _comment(event, comment_id=41):
    return {
        "id": comment_id,
        "created_at": "2026-08-06T00:00:01Z",
        "html_url": f"https://example.test/comments/{comment_id}",
        "body": render_comment(event),
    }


def _completed(arguments, *, stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(arguments, returncode, stdout, stderr)


def test_github_store_lists_and_appends_structured_comments(repo, monkeypatch):
    existing = _event()
    appended = _event(event_id="evt-appended", summary="Appended fact")
    calls = []

    def run(arguments, **kwargs):
        calls.append(arguments)
        if "--method" in arguments:
            body_argument = next(
                value for value in arguments if value.startswith("body=")
            )
            assert "lean-harness-work-event:v1" in body_argument
            return _completed(arguments, stdout=json.dumps(_comment(appended, 42)))
        assert "--paginate" in arguments
        assert "--slurp" in arguments
        payload = [[{"id": 1, "body": "ordinary comment"}], [_comment(existing)]]
        return _completed(arguments, stdout=json.dumps(payload))

    monkeypatch.setattr(shared_module.subprocess, "run", run)
    store = GitHubIssueSharedStore(repo, repository="owner/repo")

    assert store.list_events("issue-5")[0]["event_id"] == existing["event_id"]
    created = store.append_event("issue-5", appended)
    assert created["remote"]["comment_id"] == 42
    assert sum("--method" in arguments for arguments in calls) == 1


def test_github_store_rejects_event_identity_conflict(repo, monkeypatch):
    original = _event()

    def run(arguments, **kwargs):
        return _completed(arguments, stdout=json.dumps([[_comment(original)]]))

    monkeypatch.setattr(shared_module.subprocess, "run", run)
    store = GitHubIssueSharedStore(repo, repository="owner/repo")

    with pytest.raises(SharedStoreError, match="event identity conflict"):
        store.append_event(
            "issue-5", _event(kind="direction-changed", summary="Different fact")
        )


def test_pull_request_facts_include_minimal_check_summary(repo, monkeypatch):
    payload = {
        "number": 6,
        "url": "https://example.test/pr/6",
        "title": "Continuity",
        "state": "OPEN",
        "headRefName": "feature",
        "baseRefName": "main",
        "headRefOid": "abc123",
        "mergeStateStatus": "CLEAN",
        "reviewDecision": "APPROVED",
        "statusCheckRollup": [
            {
                "__typename": "CheckRun",
                "name": "tests",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            },
            {
                "__typename": "CheckRun",
                "name": "lint",
                "status": "IN_PROGRESS",
                "conclusion": None,
            },
            {
                "__typename": "StatusContext",
                "context": "policy",
                "state": "FAILURE",
            },
        ],
    }

    def run(arguments, **kwargs):
        assert arguments[1:4] == ["pr", "view", "main"]
        return _completed(arguments, stdout=json.dumps(payload))

    monkeypatch.setattr(shared_module, "current_branch", lambda repo: "main")
    monkeypatch.setattr(shared_module.subprocess, "run", run)
    store = GitHubIssueSharedStore(repo, repository="owner/repo")

    facts = store.get_current_pull_request()

    assert facts["availability"] == "present"
    assert facts["mergeStateStatus"] == "CLEAN"
    assert facts["checks"] == {
        "total": 3,
        "passed": 1,
        "pending": 1,
        "failed": 1,
        "pending_names": ["lint"],
        "failing_names": ["policy"],
    }


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        ("no-pr", "absent"),
        ("auth", "unavailable"),
        ("missing-gh", "unavailable"),
    ],
)
def test_pull_request_facts_distinguish_absent_from_unavailable(
    repo, monkeypatch, failure, expected
):
    def run(arguments, **kwargs):
        if failure == "missing-gh":
            raise FileNotFoundError("gh")
        stderr = (
            "no pull requests found for branch main"
            if failure == "no-pr"
            else "authentication required"
        )
        return _completed(arguments, stderr=stderr, returncode=1)

    monkeypatch.setattr(shared_module, "current_branch", lambda repo: "main")
    monkeypatch.setattr(shared_module.subprocess, "run", run)
    store = GitHubIssueSharedStore(repo, repository="owner/repo")

    facts = store.get_current_pull_request()
    assert facts["availability"] == expected

from __future__ import annotations

import json
import subprocess

import continuity.github as github_module
import pytest
from continuity.github import parse_comment, render_comment
from continuity.worklog.events import prepare_event

from continuity import EventValidationError, GitHubAdapter, SharedStoreError


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
    return prepare_event(event)


def _comment(event, comment_id=41):
    return {
        "id": comment_id,
        "created_at": "2026-08-06T00:00:01Z",
        "html_url": f"https://example.test/comments/{comment_id}",
        "body": render_comment(event),
    }


def _completed(arguments, *, stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(arguments, returncode, stdout, stderr)


def test_github_comment_parser_validates_tagged_remote_payload():
    invalid = {**_event(), "unresolved": "yes"}

    with pytest.raises(EventValidationError, match="unresolved"):
        parse_comment(_comment(invalid))


def test_github_comment_parser_round_trips_nested_payload():
    nested = _event(
        observation={
            "check": "targeted recovery scenarios",
            "results": {"passed": 4, "failed": 0},
        }
    )

    parsed = parse_comment(_comment(nested))

    assert parsed is not None
    assert parsed["observation"] == nested["observation"]


def test_github_comment_parser_tolerates_json_fence_in_summary():
    event = _event(
        summary='Findings:\n\n```json\n{"status": "unknown"}\n```',
        observation={"conclusion": "payload survives a fenced summary"},
    )

    parsed = parse_comment(_comment(event))

    assert parsed is not None
    assert parsed["observation"] == event["observation"]
    assert parsed["summary"] == event["summary"]


def test_github_comment_parser_reports_payload_not_immediately_after_marker():
    comment = _comment(_event())
    marker_end = comment["body"].index("-->") + len("-->")
    comment["body"] = (
        comment["body"][:marker_end]
        + "\n\ninterleaved prose"
        + comment["body"][marker_end:]
    )

    with pytest.raises(SharedStoreError, match="malformed tagged work-event"):
        parse_comment(comment)


def test_github_comment_parser_tolerates_stray_fence_line_in_summary():
    event = _event(
        summary=("Fence example follows.\n\n```\nplain code, not json\n```"),
        observation={"conclusion": "payload survives a stray closing fence"},
    )

    parsed = parse_comment(_comment(event))

    assert parsed is not None
    assert parsed["observation"] == event["observation"]
    assert parsed["summary"] == event["summary"]


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
            assert "Appended fact" in body_argument
            return _completed(arguments, stdout=json.dumps(_comment(appended, 42)))
        assert "--paginate" in arguments
        assert "--slurp" in arguments
        payload = [
            [{"id": 1, "body": "ordinary comment"}],
            [_comment(existing), _comment(existing, 43)],
        ]
        return _completed(arguments, stdout=json.dumps(payload))

    monkeypatch.setattr(github_module.subprocess, "run", run)
    store = GitHubAdapter(repo, repository="owner/repo")

    listed = store.list_events("issue-5")
    assert [event["event_id"] for event in listed] == [existing["event_id"]]
    created = store.append_event("issue-5", appended)
    assert created["remote"]["comment_id"] == 42
    assert sum("--method" in arguments for arguments in calls) == 1


def test_github_store_rejects_created_comment_identity_conflict(repo, monkeypatch):
    observed = _event(kind="direction-changed", summary="Different fact")

    def run(arguments, **kwargs):
        assert "--method" in arguments
        return _completed(arguments, stdout=json.dumps(_comment(observed)))

    monkeypatch.setattr(github_module.subprocess, "run", run)
    store = GitHubAdapter(repo, repository="owner/repo")

    with pytest.raises(SharedStoreError, match="event identity conflict"):
        store.append_event("issue-5", _event())


def test_github_store_checks_partition_and_response_before_trusting_write(
    repo, monkeypatch
):
    calls = []

    def run(arguments, **kwargs):
        calls.append(arguments)
        return _completed(arguments, stdout="[]")

    monkeypatch.setattr(github_module.subprocess, "run", run)
    store = GitHubAdapter(repo, repository="owner/repo")

    with pytest.raises(SharedStoreError, match="does not match partition"):
        store.append_event("issue-5", _event(work="issue-9"))
    assert calls == []

    with pytest.raises(SharedStoreError, match="unexpected shape"):
        store.append_event("issue-5", _event())
    assert len(calls) == 1


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
            {
                "__typename": "StatusContext",
                "context": "merge-gate",
                "state": "EXPECTED",
            },
        ],
    }

    def run(arguments, **kwargs):
        assert arguments[1:4] == ["pr", "view", "main"]
        return _completed(arguments, stdout=json.dumps(payload))

    monkeypatch.setattr(github_module, "current_branch", lambda repo: "main")
    monkeypatch.setattr(github_module.subprocess, "run", run)
    store = GitHubAdapter(repo, repository="owner/repo")

    facts = store.get_current_pull_request()

    assert facts["availability"] == "present"
    assert facts["mergeStateStatus"] == "CLEAN"
    assert facts["checks"] == {
        "total": 4,
        "passed": 1,
        "pending": 2,
        "failed": 1,
        "pending_names": ["lint", "merge-gate"],
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

    monkeypatch.setattr(github_module, "current_branch", lambda repo: "main")
    monkeypatch.setattr(github_module.subprocess, "run", run)
    store = GitHubAdapter(repo, repository="owner/repo")

    facts = store.get_current_pull_request()
    assert facts["availability"] == expected


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        ("missing-issue", "absent"),
        ("hidden-repository", "unavailable"),
        ("auth", "unavailable"),
        ("missing-gh", "unavailable"),
        ("invalid-json", "error"),
    ],
)
def test_work_item_facts_expose_availability(repo, monkeypatch, failure, expected):
    def run(arguments, **kwargs):
        if failure == "missing-gh":
            raise FileNotFoundError("gh")
        if failure == "invalid-json":
            return _completed(arguments, stdout="{broken")
        if failure in {"missing-issue", "hidden-repository"}:
            if failure == "missing-issue" and arguments[-1] == "repos/owner/repo":
                return _completed(arguments, stdout="{}")
            return _completed(arguments, stderr="HTTP 404: Not Found", returncode=1)
        stderr = "auth required"
        return _completed(arguments, stderr=stderr, returncode=1)

    monkeypatch.setattr(github_module.subprocess, "run", run)
    store = GitHubAdapter(repo, repository="owner/repo")

    assert store.get_work_item("issue-5")["availability"] == expected

"""Project-shared work events stored as structured GitHub Issue comments."""

from __future__ import annotations

import copy
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .errors import EventValidationError, SharedStoreError
from .git_facts import run_git

MARKER_VERSION = "v1"
MARKER_PREFIX = "lean-harness-work-event"
_MARKER = re.compile(rf"<!-- {MARKER_PREFIX}:{MARKER_VERSION} event_id=([^ ]+) -->")
_PAYLOAD = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
_WORK = re.compile(r"^issue-([1-9][0-9]*)$")

STRUCTURAL_KINDS = {
    "checkpoint-created",
    "checkpoint-remapped",
    "event-resolved",
    "verification-observed",
    "work-reopened",
}

SIGNIFICANT_KINDS = {
    "work-started",
    "finding",
    "hypothesis-resolved",
    "direction-changed",
    "scope-changed",
    "evidence-staled",
    "review-finding",
    "remediation-completed",
    "worker-result-absorbed",
    "handoff",
    "pr-opened",
    "pr-closed",
    "pr-merged",
    "cycle-finished",
    "work-finished",
}

EVENT_KINDS = STRUCTURAL_KINDS | SIGNIFICANT_KINDS


class SharedWorkLogStore(Protocol):
    """The deliberately narrow shared storage port."""

    def append_event(self, work: str, event: dict[str, Any]) -> dict[str, Any]: ...

    def list_events(self, work: str) -> list[dict[str, Any]]: ...

    def find_event(self, work: str, event_id: str) -> dict[str, Any] | None: ...


def issue_number(work: str) -> int:
    match = _WORK.fullmatch(work)
    if match is None:
        raise SharedStoreError(
            f"GitHub shared work must use an issue-N partition, got: {work}"
        )
    return int(match.group(1))


def validate_event(event: dict[str, Any], expected_work: str | None = None) -> None:
    required = ("event_id", "kind", "work", "cycle_id", "producer", "created_at")
    missing = [name for name in required if not event.get(name)]
    if missing:
        raise EventValidationError(f"shared event missing: {', '.join(missing)}")
    for field in required:
        if not isinstance(event[field], str):
            raise EventValidationError(f"shared event {field} must be a string")
    if expected_work is not None and event["work"] != expected_work:
        raise EventValidationError(
            f"event work {event['work']} does not match partition {expected_work}"
        )
    if event["kind"] not in EVENT_KINDS:
        raise EventValidationError(f"unknown shared event kind: {event['kind']}")
    if not isinstance(event["event_id"], str) or not event["event_id"].startswith(
        "evt-"
    ):
        raise EventValidationError("event_id must be a stable evt-* identity")
    resolves = event.get("resolves", [])
    if not isinstance(resolves, list) or any(
        not isinstance(item, str) or not item.startswith("evt-") for item in resolves
    ):
        raise EventValidationError("resolves must contain event_id values")
    kind = event["kind"]
    if kind == "checkpoint-created" and not event.get("commit"):
        raise EventValidationError("checkpoint-created requires commit")
    if kind == "checkpoint-remapped":
        keys = ("checkpoint_event_id", "old_commit", "new_commit", "reason")
        if any(not event.get(key) for key in keys):
            raise EventValidationError(
                "checkpoint-remapped requires checkpoint_event_id, old_commit, "
                "new_commit, and reason"
            )
    if kind == "verification-observed" and (
        not event.get("subject_commit") or "observation" not in event
    ):
        raise EventValidationError(
            "verification-observed requires subject_commit and observation"
        )
    if kind == "event-resolved" and not resolves:
        raise EventValidationError("event-resolved requires resolves")
    if not event.get("summary") and "observation" not in event:
        raise EventValidationError("shared event requires summary or observation")


def render_comment(event: dict[str, Any]) -> str:
    validate_event(event)
    marker = f"<!-- {MARKER_PREFIX}:{MARKER_VERSION} event_id={event['event_id']} -->"
    summary = event.get("summary") or "Structured observation attached."
    payload = json.dumps(event, ensure_ascii=False, indent=2, sort_keys=True)
    return (
        f"{marker}\n"
        f"### Lean Harness work event · `{event['kind']}`\n\n"
        f"{summary}\n\n"
        f"```json\n{payload}\n```"
    )


def parse_comment(comment: dict[str, Any]) -> dict[str, Any] | None:
    body = comment.get("body")
    if not isinstance(body, str):
        return None
    marker = _MARKER.search(body)
    if marker is None:
        return None
    payload = _PAYLOAD.search(body)
    if payload is None:
        raise SharedStoreError(
            f"malformed tagged work-event comment {comment.get('id', '<unknown>')}"
        )
    try:
        event = json.loads(payload.group(1))
    except json.JSONDecodeError as error:
        raise SharedStoreError(
            f"malformed work-event JSON in comment {comment.get('id', '<unknown>')}: "
            f"{error}"
        ) from error
    if not isinstance(event, dict):
        raise SharedStoreError("tagged work-event payload must be an object")
    validate_event(event)
    if event["event_id"] != marker.group(1):
        raise SharedStoreError(
            f"work-event marker/payload identity mismatch in comment {comment.get('id')}"
        )
    enriched = copy.deepcopy(event)
    enriched["remote"] = {
        "comment_id": comment.get("id"),
        "created_at": comment.get("created_at"),
        "url": comment.get("html_url"),
    }
    return enriched


def _repository_from_origin(repo: Path) -> str:
    result = run_git(repo, "remote", "get-url", "origin")
    if result.returncode != 0:
        raise SharedStoreError("cannot discover GitHub repository: origin is missing")
    origin = result.stdout.strip()
    patterns = (
        r"^git@github\.com:([^/]+/[^/]+?)(?:\.git)?$",
        r"^https://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$",
        r"^ssh://git@github\.com/([^/]+/[^/]+?)(?:\.git)?/?$",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, origin)
        if match is not None:
            return match.group(1)
    raise SharedStoreError(f"origin is not a supported GitHub repository URL: {origin}")


@dataclass
class GitHubIssueSharedStore:
    """GitHub implementation: one tagged Issue comment per durable event."""

    repo: Path
    repository: str | None = None
    gh_binary: str = "gh"

    def __post_init__(self) -> None:
        self.repo = Path(self.repo).resolve()
        if self.repository is None:
            self.repository = _repository_from_origin(self.repo)

    def _gh(self, *arguments: str) -> Any:
        result = subprocess.run(
            [self.gh_binary, *arguments],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            raise SharedStoreError(f"GitHub request failed: {message}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise SharedStoreError(f"GitHub returned invalid JSON: {error}") from error

    def _comments(self, work: str) -> list[dict[str, Any]]:
        number = issue_number(work)
        payload = self._gh(
            "api",
            "--paginate",
            "--slurp",
            f"repos/{self.repository}/issues/{number}/comments?per_page=100",
        )
        if not isinstance(payload, list):
            raise SharedStoreError(
                "GitHub comment listing returned an unexpected shape"
            )
        comments: list[dict[str, Any]] = []
        for page in payload:
            if not isinstance(page, list):
                raise SharedStoreError(
                    "GitHub comment page returned an unexpected shape"
                )
            comments.extend(page)
        return comments

    def list_events(self, work: str) -> list[dict[str, Any]]:
        events = []
        for comment in self._comments(work):
            event = parse_comment(comment)
            if event is not None:
                validate_event(event, expected_work=work)
                events.append(event)
        return events

    def find_event(self, work: str, event_id: str) -> dict[str, Any] | None:
        return next(
            (
                event
                for event in self.list_events(work)
                if event["event_id"] == event_id
            ),
            None,
        )

    def append_event(self, work: str, event: dict[str, Any]) -> dict[str, Any]:
        validate_event(event, expected_work=work)
        existing = self.find_event(work, event["event_id"])
        if existing is not None:
            return existing
        number = issue_number(work)
        comment = self._gh(
            "api",
            "--method",
            "POST",
            f"repos/{self.repository}/issues/{number}/comments",
            "--field",
            f"body={render_comment(event)}",
        )
        parsed = parse_comment(comment)
        if parsed is None:
            raise SharedStoreError(
                "GitHub created a comment without the work-event marker"
            )
        return parsed

    def get_work_item(self, work: str) -> dict[str, Any]:
        """Read the Issue/Spec facts needed by context reconstruction."""

        number = issue_number(work)
        issue = self._gh("api", f"repos/{self.repository}/issues/{number}")
        return {
            "work": work,
            "number": issue.get("number"),
            "title": issue.get("title"),
            "state": issue.get("state"),
            "body": issue.get("body"),
            "url": issue.get("html_url"),
        }

    def get_current_pull_request(self) -> dict[str, Any] | None:
        result = subprocess.run(
            [
                self.gh_binary,
                "pr",
                "view",
                "--repo",
                str(self.repository),
                "--json",
                "number,url,title,state,headRefName,baseRefName,headRefOid,reviewDecision",
            ],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise SharedStoreError(
                f"GitHub returned invalid PR JSON: {error}"
            ) from error

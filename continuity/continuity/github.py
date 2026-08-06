"""GitHub adapter for shared work events and current project facts."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .artifacts import current_branch, origin_url, unavailable_fact
from .errors import SharedStoreError
from .worklog.events import (
    assert_same_event,
    durable_fields,
    logical_events,
    prepare_event,
)

MARKER_VERSION = "v1"
MARKER_PREFIX = "lean-harness-work-event"
_MARKER = re.compile(rf"<!-- {MARKER_PREFIX}:{MARKER_VERSION} event_id=([^ ]+) -->")
_PAYLOAD = re.compile(r"```json\s*(\{.*\})\s*```", re.DOTALL)
_WORK = re.compile(r"^issue-([1-9][0-9]*)$")


def issue_number(work: str) -> int:
    match = _WORK.fullmatch(work)
    if match is None:
        raise SharedStoreError(
            f"GitHub shared work must use an issue-N partition, got: {work}"
        )
    return int(match.group(1))


def render_comment(event: dict[str, Any]) -> str:
    marker = f"<!-- {MARKER_PREFIX}:{MARKER_VERSION} event_id={event['event_id']} -->"
    summary = event.get("summary") or "Structured observation attached."
    durable_event = durable_fields(event)
    payload = json.dumps(durable_event, ensure_ascii=False, indent=2, sort_keys=True)
    return (
        f"{marker}\n"
        f"### Lean Harness work event · `{event['kind']}`\n\n"
        f"{summary}\n\n"
        f"```json\n{payload}\n```"
    )


def parse_comment(
    comment: dict[str, Any], *, expected_work: str | None = None
) -> dict[str, Any] | None:
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
    event = prepare_event(event, expected_work=expected_work)
    if event["event_id"] != marker.group(1):
        raise SharedStoreError(
            f"work-event marker/payload identity mismatch in comment {comment.get('id')}"
        )
    event["remote"] = {
        "comment_id": comment.get("id"),
        "created_at": comment.get("created_at"),
        "url": comment.get("html_url"),
    }
    return event


def _repository_from_origin(repo: Path) -> str:
    origin = origin_url(repo)
    if origin is None:
        raise SharedStoreError("cannot discover GitHub repository: origin is missing")
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


def _not_found(message: str) -> bool:
    lowered = message.lower()
    return "404" in lowered or "not found" in lowered


def _no_pull_request(message: str) -> bool:
    lowered = message.lower()
    return any(
        text in lowered
        for text in (
            "no pull requests found",
            "could not find pull request",
            "no pull request found",
        )
    )


def _response_message(result: subprocess.CompletedProcess[str]) -> str:
    return result.stderr.strip() or result.stdout.strip()


def _check_summary(checks: Any) -> dict[str, Any]:
    if not isinstance(checks, list):
        checks = []
    passed = 0
    pending_names = []
    failing_names = []
    successful = {"SUCCESS", "NEUTRAL", "SKIPPED"}
    for check in checks:
        if not isinstance(check, dict):
            continue
        name = check.get("name") or check.get("context") or "unnamed-check"
        if (
            check.get("status") not in {None, "COMPLETED"}
            or check.get("state") == "PENDING"
        ):
            pending_names.append(name)
        elif check.get("conclusion") in successful or check.get("state") == "SUCCESS":
            passed += 1
        else:
            failing_names.append(name)
    return {
        "total": passed + len(pending_names) + len(failing_names),
        "passed": passed,
        "pending": len(pending_names),
        "failed": len(failing_names),
        "pending_names": pending_names,
        "failing_names": failing_names,
    }


class GitHubAdapter:
    """One adapter implementing two narrow ports without merging their domains."""

    def __init__(
        self,
        repo: Path,
        repository: str | None = None,
        gh_binary: str = "gh",
    ) -> None:
        self.repo = Path(repo).resolve()
        self.repository = repository or _repository_from_origin(self.repo)
        self.gh_binary = gh_binary

    def _run(self, *arguments: str) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                [self.gh_binary, *arguments],
                cwd=self.repo,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return None

    def _json(self, *arguments: str) -> Any:
        result = self._run(*arguments)
        if result is None:
            raise SharedStoreError("gh executable not found")
        if result.returncode != 0:
            raise SharedStoreError(
                f"GitHub request failed: {_response_message(result)}"
            )
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise SharedStoreError(f"GitHub returned invalid JSON: {error}") from error

    def _comments(self, work: str) -> list[dict[str, Any]]:
        payload = self._json(
            "api",
            "--paginate",
            "--slurp",
            f"repos/{self.repository}/issues/{issue_number(work)}/comments?per_page=100",
        )
        if not isinstance(payload, list) or any(
            not isinstance(page, list) for page in payload
        ):
            raise SharedStoreError(
                "GitHub comment listing returned an unexpected shape"
            )
        comments = [comment for page in payload for comment in page]
        if any(not isinstance(comment, dict) for comment in comments):
            raise SharedStoreError("GitHub comment page contains a non-object")
        return comments

    def list_events(self, work: str) -> list[dict[str, Any]]:
        physical = []
        for comment in self._comments(work):
            event = parse_comment(comment, expected_work=work)
            if event is not None:
                physical.append(event)
        return logical_events(physical)

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
        if event.get("work") != work:
            raise SharedStoreError(
                f"event work {event.get('work')} does not match partition {work}"
            )
        comment = self._json(
            "api",
            "--method",
            "POST",
            f"repos/{self.repository}/issues/{issue_number(work)}/comments",
            "--field",
            f"body={render_comment(event)}",
        )
        if not isinstance(comment, dict):
            raise SharedStoreError(
                "GitHub comment creation returned an unexpected shape"
            )
        parsed = parse_comment(comment, expected_work=work)
        if parsed is None:
            raise SharedStoreError(
                "GitHub created a comment without the work-event marker"
            )
        assert_same_event(event, parsed)
        return parsed

    def get_work_item(self, work: str) -> dict[str, Any]:
        result = self._run(
            "api", f"repos/{self.repository}/issues/{issue_number(work)}"
        )
        if result is None:
            return unavailable_fact("gh executable not found")
        if result.returncode != 0:
            message = _response_message(result)
            if not _not_found(message):
                return unavailable_fact(message)
            repository = self._run("api", f"repos/{self.repository}")
            if repository is None:
                return unavailable_fact(
                    "gh executable not found while confirming Issue absence"
                )
            if repository.returncode != 0:
                return unavailable_fact(
                    "cannot confirm Issue absence because the repository is unavailable: "
                    f"{_response_message(repository)}"
                )
            return {"availability": "absent", "reason": message}
        try:
            issue = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            return {
                "availability": "error",
                "reason": f"GitHub returned invalid Issue JSON: {error}",
            }
        if not isinstance(issue, dict):
            return {
                "availability": "error",
                "reason": "GitHub returned an unexpected Issue shape",
            }
        return {
            "availability": "present",
            "work": work,
            "number": issue.get("number"),
            "title": issue.get("title"),
            "state": issue.get("state"),
            "body": issue.get("body"),
            "url": issue.get("html_url"),
        }

    def get_current_pull_request(self) -> dict[str, Any]:
        branch = current_branch(self.repo)
        if branch is None:
            return unavailable_fact("current Git worktree is detached")
        result = self._run(
            "pr",
            "view",
            branch,
            "--repo",
            str(self.repository),
            "--json",
            (
                "number,url,title,state,headRefName,baseRefName,headRefOid,"
                "mergeStateStatus,reviewDecision,statusCheckRollup"
            ),
        )
        if result is None:
            return unavailable_fact("gh executable not found")
        if result.returncode != 0:
            message = _response_message(result)
            availability = "absent" if _no_pull_request(message) else "unavailable"
            return {"availability": availability, "reason": message}
        try:
            pull_request = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            return {
                "availability": "error",
                "reason": f"GitHub returned invalid PR JSON: {error}",
            }
        if not isinstance(pull_request, dict):
            return {
                "availability": "error",
                "reason": "GitHub returned an unexpected PR shape",
            }
        checks = _check_summary(pull_request.pop("statusCheckRollup", []))
        return {"availability": "present", **pull_request, "checks": checks}

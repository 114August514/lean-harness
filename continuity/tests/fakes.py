from __future__ import annotations

import copy
import threading
from collections import defaultdict
from typing import Any

from continuity.errors import SharedStoreError
from continuity.worklog.events import logical_events


class FakeSharedStore:
    """Deterministic comment-like store shared by independent clone tests."""

    def __init__(self):
        self._events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._lock = threading.Lock()
        self._next_comment_id = 1
        self._lose_once: set[str] = set()
        self.append_count = 0

    def lose_response_once(self, event_id: str) -> None:
        self._lose_once.add(event_id)

    def append_event(self, work: str, event: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            stored = copy.deepcopy(event)
            stored["remote"] = {
                "comment_id": self._next_comment_id,
                "created_at": event["created_at"],
                "url": f"https://example.test/comments/{self._next_comment_id}",
            }
            self._next_comment_id += 1
            self.append_count += 1
            self._events[work].append(stored)
            if event["event_id"] in self._lose_once:
                self._lose_once.remove(event["event_id"])
                raise SharedStoreError("simulated response loss after remote append")
            return copy.deepcopy(stored)

    def list_events(self, work: str) -> list[dict[str, Any]]:
        with self._lock:
            physical = copy.deepcopy(self._events[work])
        return logical_events(physical)

    def find_event(self, work: str, event_id: str) -> dict[str, Any] | None:
        return next(
            (item for item in self.list_events(work) if item["event_id"] == event_id),
            None,
        )


class FakeProjectFacts:
    """Deterministic Issue and PR facts, independent of shared-log storage."""

    def get_work_item(self, work: str) -> dict[str, Any]:
        return {
            "availability": "present",
            "work": work,
            "number": int(work.removeprefix("issue-")),
            "title": "Continuity work unit",
            "state": "open",
            "body": "Acceptance and scope facts",
            "url": f"https://example.test/{work}",
        }

    def get_current_pull_request(self) -> dict[str, Any]:
        return {
            "availability": "present",
            "number": 6,
            "title": "Continuity reference implementation",
            "state": "OPEN",
            "url": "https://example.test/pr/6",
            "checks": {
                "total": 1,
                "passed": 1,
                "pending": 0,
                "failed": 0,
                "pending_names": [],
                "failing_names": [],
            },
        }

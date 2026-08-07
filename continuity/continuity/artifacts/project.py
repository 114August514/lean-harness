"""Narrow port for current Issue/Spec and PR facts."""

from __future__ import annotations

from typing import Any, Protocol


class ProjectFactsSource(Protocol):
    def get_work_item(self, work: str) -> dict[str, Any]: ...

    def get_current_pull_request(self) -> dict[str, Any]: ...


def unavailable_fact(reason: str) -> dict[str, str]:
    return {"availability": "unavailable", "reason": reason}

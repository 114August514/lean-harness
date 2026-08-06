"""Fact-only context reconstruction for a replacement agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from .errors import RecoveryError
from .events import WorkEvents
from .git_facts import git_snapshot
from .recovery import RecoveryLog


class ProjectFactsSource(Protocol):
    def get_work_item(self, work: str) -> dict[str, Any]: ...

    def get_current_pull_request(self) -> dict[str, Any]: ...


class ContextReconstructor:
    """Combine shared project facts, Git facts, and matching local recovery facts."""

    def __init__(
        self,
        repo: Path,
        work_events: WorkEvents,
        recovery: RecoveryLog | None,
        project_facts: ProjectFactsSource | None = None,
    ):
        self.repo = Path(repo).resolve()
        self.work_events = work_events
        self.recovery = recovery
        self.project_facts = project_facts

    def load(
        self,
        work: str | None = None,
        cycle_id: str | None = None,
        *,
        shared_only: bool = False,
    ) -> dict[str, Any]:
        if shared_only:
            if work is None:
                raise RecoveryError("shared-only resume requires an explicit work")
            recovery_status = None
            binding = None
        else:
            if self.recovery is None:
                raise RecoveryError("local resume requires a RecoveryLog")
            recovery_status = self.recovery.status()
            binding = recovery_status["binding"]
        binding_is_local_input = bool(
            binding and binding.get("status") in {"active", "paused"}
        )
        requested_work = work or (
            binding.get("work") if binding_is_local_input else None
        )
        requested_cycle = cycle_id or (
            binding.get("cycle_id") if binding_is_local_input else None
        )

        if binding_is_local_input and not shared_only:
            if work is not None and work != binding.get("work"):
                raise RecoveryError(
                    "requested work does not match local recovery binding; "
                    "use shared_only to omit local recovery"
                )
            if cycle_id is not None and cycle_id != binding.get("cycle_id"):
                raise RecoveryError(
                    "requested cycle does not match local recovery binding; "
                    "use shared_only to omit local recovery"
                )

        git = git_snapshot(self.repo)
        result: dict[str, Any] = {
            "work": requested_work,
            "cycle_id": requested_cycle,
            "issue_or_spec": None,
            "pull_request": None,
            "git": git,
            "latest_checkpoint": None,
            "shared_events_since_checkpoint": [],
            "earlier_unresolved_shared_events": [],
            "local_recovery": None,
        }

        if requested_work is not None:
            if self.project_facts is not None:
                result["issue_or_spec"] = self.project_facts.get_work_item(
                    requested_work
                )
                result["pull_request"] = self.project_facts.get_current_pull_request()
            checkpoint = self.work_events.latest_checkpoint(
                requested_work,
                at_commit=git["head"],
                cycle_id=requested_cycle,
            )
            result["latest_checkpoint"] = checkpoint
            if checkpoint is None:
                result["shared_events_since_checkpoint"] = self.work_events.events(
                    requested_work, cycle_id=requested_cycle
                )
            else:
                result["shared_events_since_checkpoint"] = (
                    self.work_events.events_since_checkpoint(
                        requested_work,
                        checkpoint["event_id"],
                        cycle_id=requested_cycle,
                    )
                )
                all_events = self.work_events.events(requested_work)
                anchor = next(
                    index
                    for index, event in enumerate(all_events)
                    if event["event_id"] == checkpoint["event_id"]
                )
                positions = {
                    event["event_id"]: index for index, event in enumerate(all_events)
                }
                result["earlier_unresolved_shared_events"] = [
                    event
                    for event in self.work_events.unresolved_events(requested_work)
                    if positions[event["event_id"]] <= anchor
                ]

        if binding_is_local_input and not shared_only:
            assert recovery_status is not None
            assert self.recovery is not None
            result["local_recovery"] = {
                "binding": binding,
                "latest_intent": recovery_status["latest_intent"],
                "open_begins": recovery_status["open_begins"],
                "unexplained_open_begins": recovery_status["unexplained_open_begins"],
                "pending_handoffs": self.recovery.pending_handoffs(
                    work=requested_work, cycle_id=requested_cycle
                ),
            }
        return result

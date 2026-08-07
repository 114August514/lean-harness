"""Fact-only context reconstruction for a replacement agent."""

from __future__ import annotations

from typing import Any

from .artifacts import ProjectFactsSource, git_snapshot, unavailable_fact
from .errors import BindingMismatchError, RecoveryError
from .recovery import RecoveryLog
from .worklog import WorkEventReader


class ContextReconstructor:
    """Combine authoritative, shared, Git, and matching local facts."""

    def __init__(
        self,
        reader: WorkEventReader,
        *,
        project_facts: ProjectFactsSource | None = None,
        recovery: RecoveryLog | None = None,
    ):
        if recovery is not None and recovery.repo != reader.repo:
            raise RecoveryError(
                "context reader and recovery use different repositories"
            )
        self.reader = reader
        self.project_facts = project_facts
        self.recovery = recovery

    def load(
        self,
        work: str | None = None,
        cycle_id: str | None = None,
    ) -> dict[str, Any]:
        recovery_status = self.recovery.status() if self.recovery is not None else None
        binding = recovery_status["binding"] if recovery_status is not None else None
        binding_is_local = bool(binding and binding["status"] in {"active", "paused"})
        local_work = binding["work"] if binding_is_local else None
        local_cycle = binding["cycle_id"] if binding_is_local else None
        requested_work = local_work if work is None else work
        requested_cycle = local_cycle if cycle_id is None else cycle_id

        if self.recovery is None and requested_work is None:
            raise RecoveryError("shared-only resume requires an explicit work")
        if binding_is_local:
            if work is not None and work != binding["work"]:
                raise BindingMismatchError(
                    "requested work does not match local recovery binding; "
                    "omit RecoveryLog for shared-only context"
                )
            if cycle_id is not None and cycle_id != binding["cycle_id"]:
                raise BindingMismatchError(
                    "requested cycle does not match local recovery binding; "
                    "omit RecoveryLog for shared-only context"
                )

        git = git_snapshot(self.reader.repo)
        result: dict[str, Any] = {
            "work": requested_work,
            "cycle_id": requested_cycle,
            "issue_or_spec": unavailable_fact("work is not known"),
            "pull_request": unavailable_fact("work is not known"),
            "git": git,
            "latest_checkpoint": None,
            "shared_events_since_checkpoint": [],
            "earlier_unresolved_shared_events": [],
            "local_recovery": None,
        }
        if requested_work is not None:
            if self.project_facts is None:
                result["issue_or_spec"] = unavailable_fact(
                    "project facts source is not configured"
                )
                result["pull_request"] = unavailable_fact(
                    "project facts source is not configured"
                )
            else:
                result["issue_or_spec"] = self.project_facts.get_work_item(
                    requested_work
                )
                result["pull_request"] = self.project_facts.get_current_pull_request()
            result.update(
                self.reader.reconstruction_facts(
                    requested_work,
                    at_commit=git["head"],
                    cycle_id=requested_cycle,
                )
            )

        if binding_is_local:
            assert recovery_status is not None
            result["local_recovery"] = {
                "binding": binding,
                "latest_intent": recovery_status["latest_intent"],
                "open_begins": recovery_status["open_begins"],
                "unexplained_open_begins": recovery_status["unexplained_open_begins"],
                "pending_handoffs": [
                    handoff
                    for handoff in recovery_status["pending_handoffs"]
                    if handoff["work"] == requested_work
                    and handoff["cycle_id"] == requested_cycle
                ],
            }
        return result

"""Read and derive facts from one project-shared work log."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..artifacts import commit_exists, is_ancestor
from ..errors import CheckpointConflictError, CheckpointError
from .events import SharedWorkLogStore


def _filter(
    events: list[dict[str, Any]],
    *,
    cycle_id: str | None = None,
    kind: str | None = None,
    pr: int | None = None,
) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if (cycle_id is None or event.get("cycle_id") == cycle_id)
        and (kind is None or event.get("kind") == kind)
        and (pr is None or event.get("pr") == pr)
    ]


def _unresolved(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resolved = {event_id for event in events for event_id in event.get("resolves", [])}
    return [
        event
        for event in events
        if event.get("unresolved") and event["event_id"] not in resolved
    ]


def _resolve_checkpoint(
    checkpoint: dict[str, Any], events: list[dict[str, Any]]
) -> str:
    current = checkpoint["commit"]
    seen = {current}
    while True:
        # Shared comments are cross-collaborator input: the publisher-side cycle
        # check is not enough, the reader must enforce the same invariant.
        replacements = {
            event["new_commit"]
            for event in events
            if event.get("kind") == "checkpoint-remapped"
            and event.get("checkpoint_event_id") == checkpoint["event_id"]
            and event.get("cycle_id") == checkpoint["cycle_id"]
            and event.get("old_commit") == current
        }
        if not replacements:
            return current
        if len(replacements) != 1:
            raise CheckpointConflictError(
                f"checkpoint remap conflict from {current}: "
                f"{', '.join(sorted(replacements))}"
            )
        replacement = replacements.pop()
        if replacement in seen:
            raise CheckpointConflictError(
                f"checkpoint remap cycle detected at {replacement}"
            )
        seen.add(replacement)
        current = replacement


class WorkEventReader:
    """Read one logical event snapshot and derive checkpoint/context facts."""

    def __init__(self, repo: Path, shared: SharedWorkLogStore):
        self.repo = Path(repo).resolve()
        self.shared = shared

    def events(
        self,
        work: str,
        *,
        cycle_id: str | None = None,
        kind: str | None = None,
        pr: int | None = None,
    ) -> list[dict[str, Any]]:
        return _filter(
            self.shared.list_events(work), cycle_id=cycle_id, kind=kind, pr=pr
        )

    def find_event(self, work: str, event_id: str) -> dict[str, Any] | None:
        return self.shared.find_event(work, event_id)

    def unresolved_events(self, work: str) -> list[dict[str, Any]]:
        return _unresolved(self.events(work))

    def resolve_checkpoint_event(self, checkpoint: dict[str, Any]) -> str:
        if checkpoint["kind"] != "checkpoint-created":
            raise CheckpointError("event is not a checkpoint-created event")
        return _resolve_checkpoint(checkpoint, self.events(checkpoint["work"]))

    def latest_checkpoint(
        self,
        work: str,
        *,
        at_commit: str | None = None,
        cycle_id: str | None = None,
    ) -> dict[str, Any] | None:
        return self._latest_checkpoint(
            self.events(work), at_commit=at_commit, cycle_id=cycle_id
        )

    def reconstruction_facts(
        self,
        work: str,
        *,
        at_commit: str | None,
        cycle_id: str | None,
    ) -> dict[str, Any]:
        events = self.events(work)
        checkpoint = self._latest_checkpoint(
            events, at_commit=at_commit, cycle_id=cycle_id
        )
        if checkpoint is None:
            # No anchor yet (e.g. a reopened cycle without a checkpoint): every
            # unresolved shared event still belongs to the recovery context.
            since_checkpoint = _filter(events, cycle_id=cycle_id)
            earlier_unresolved = _unresolved(events)
        else:
            positions = {event["event_id"]: index for index, event in enumerate(events)}
            anchor = positions[checkpoint["event_id"]]
            since_checkpoint = _filter(events[anchor + 1 :], cycle_id=cycle_id)
            earlier_unresolved = [
                event
                for event in _unresolved(events)
                if positions[event["event_id"]] <= anchor
            ]
        return {
            "latest_checkpoint": checkpoint,
            "shared_events_since_checkpoint": since_checkpoint,
            "earlier_unresolved_shared_events": earlier_unresolved,
        }

    def _latest_checkpoint(
        self,
        events: list[dict[str, Any]],
        *,
        at_commit: str | None,
        cycle_id: str | None,
    ) -> dict[str, Any] | None:
        for checkpoint in reversed(
            _filter(events, cycle_id=cycle_id, kind="checkpoint-created")
        ):
            resolved = _resolve_checkpoint(checkpoint, events)
            if not commit_exists(self.repo, resolved):
                continue
            if at_commit is not None and not is_ancestor(
                self.repo, resolved, at_commit
            ):
                continue
            return {**checkpoint, "resolved_commit": resolved}
        return None

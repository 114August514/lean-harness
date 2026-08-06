"""Typed shared work-event operations and response-loss reconciliation."""

from __future__ import annotations

import copy
import uuid
from pathlib import Path
from typing import Any

from .errors import EventValidationError, RecoveryError, SharedStoreError
from .git_facts import commit_exists, is_ancestor, resolve_commit
from .recovery import RecoveryLog, utc_now
from .shared import (
    SIGNIFICANT_KINDS,
    SharedWorkLogStore,
    validate_event,
)


class WorkEvents:
    """Read shared facts and publish them through local begin/end protection."""

    def __init__(
        self,
        repo: Path,
        shared: SharedWorkLogStore,
        recovery: RecoveryLog | None = None,
    ):
        self.repo = Path(repo).resolve()
        self.shared = shared
        self.recovery = recovery

    def events(
        self,
        work: str,
        *,
        cycle_id: str | None = None,
        kind: str | None = None,
        pr: int | None = None,
    ) -> list[dict[str, Any]]:
        output = []
        for event in self.shared.list_events(work):
            validate_event(event, expected_work=work)
            if cycle_id is not None and event.get("cycle_id") != cycle_id:
                continue
            if kind is not None and event.get("kind") != kind:
                continue
            if pr is not None and event.get("pr") != pr:
                continue
            output.append(event)
        return output

    def find_event(self, work: str, event_id: str) -> dict[str, Any] | None:
        event = self.shared.find_event(work, event_id)
        if event is not None:
            validate_event(event, expected_work=work)
        return event

    def append_significant(
        self,
        work: str,
        cycle_id: str,
        kind: str,
        producer: str,
        *,
        summary: str | None = None,
        observation: dict[str, Any] | None = None,
        references: list[str] | None = None,
        unresolved: bool = False,
        artifact: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        """Publish an ordinary durable fact; structural kinds have dedicated APIs."""

        if kind not in SIGNIFICANT_KINDS:
            raise EventValidationError(
                f"{kind} is not an ordinary significant event; use its domain operation"
            )
        event = self._base_event(
            work,
            cycle_id,
            kind,
            producer,
            summary=summary,
            observation=observation,
            references=references,
            event_id=event_id,
        )
        if unresolved:
            event["unresolved"] = True
        if artifact:
            event["artifact"] = copy.deepcopy(artifact)
        if details:
            protected = {
                "event_id",
                "kind",
                "work",
                "cycle_id",
                "producer",
                "created_at",
                "resolves",
                "remote",
            }
            overlap = protected.intersection(details)
            if overlap:
                raise EventValidationError(
                    f"details cannot replace structural fields: {', '.join(sorted(overlap))}"
                )
            event.update(copy.deepcopy(details))
        return self._publish(event)

    def create_checkpoint(
        self,
        work: str,
        cycle_id: str,
        commit: str,
        producer: str,
        *,
        summary: str | None = None,
        references: list[str] | None = None,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        resolved = resolve_commit(self.repo, commit)
        event = self._base_event(
            work,
            cycle_id,
            "checkpoint-created",
            producer,
            summary=summary or f"Coherent checkpoint at {resolved[:12]}",
            references=references,
            event_id=event_id,
        )
        event["commit"] = resolved
        return self._publish(event)

    def remap_checkpoint(
        self,
        work: str,
        cycle_id: str,
        checkpoint_event_id: str,
        new_commit: str,
        reason: str,
        producer: str,
        *,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        checkpoint = self.find_event(work, checkpoint_event_id)
        if checkpoint is None or checkpoint.get("kind") != "checkpoint-created":
            raise EventValidationError(
                "checkpoint remap requires an existing shared checkpoint-created event"
            )
        if checkpoint.get("cycle_id") != cycle_id:
            raise EventValidationError(
                "checkpoint remap cycle does not match checkpoint"
            )
        old_commit = self.resolve_checkpoint_event(checkpoint)
        resolved_new = resolve_commit(self.repo, new_commit)
        event = self._base_event(
            work,
            cycle_id,
            "checkpoint-remapped",
            producer,
            summary=f"Remapped checkpoint {old_commit[:12]} to {resolved_new[:12]}",
            references=[checkpoint_event_id],
            event_id=event_id,
        )
        event.update(
            {
                "checkpoint_event_id": checkpoint_event_id,
                "old_commit": old_commit,
                "new_commit": resolved_new,
                "reason": reason,
            }
        )
        return self._publish(event)

    def reopen_work(
        self,
        work: str,
        new_cycle_id: str,
        producer: str,
        summary: str,
        *,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        event = self._base_event(
            work,
            new_cycle_id,
            "work-reopened",
            producer,
            summary=summary,
            event_id=event_id,
        )
        return self._publish(event)

    def resolve_event(
        self,
        work: str,
        cycle_id: str,
        target_event_id: str,
        producer: str,
        summary: str,
        *,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        if self.find_event(work, target_event_id) is None:
            raise EventValidationError(
                f"cannot resolve missing event: {target_event_id}"
            )
        event = self._base_event(
            work,
            cycle_id,
            "event-resolved",
            producer,
            summary=summary,
            resolves=[target_event_id],
            references=[target_event_id],
            event_id=event_id,
        )
        return self._publish(event)

    def record_verification(
        self,
        work: str,
        cycle_id: str,
        subject_commit: str,
        observation: dict[str, Any],
        producer: str,
        *,
        summary: str | None = None,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        commit = resolve_commit(self.repo, subject_commit)
        event = self._base_event(
            work,
            cycle_id,
            "verification-observed",
            producer,
            summary=summary,
            observation=observation,
            event_id=event_id,
        )
        event["subject_commit"] = commit
        return self._publish(event)

    def unresolved_events(self, work: str) -> list[dict[str, Any]]:
        events = self.events(work)
        resolved = {
            event_id for event in events for event_id in event.get("resolves", [])
        }
        return [
            event
            for event in events
            if event.get("unresolved") and event["event_id"] not in resolved
        ]

    def resolve_checkpoint_event(self, checkpoint: dict[str, Any]) -> str:
        validate_event(checkpoint)
        if checkpoint.get("kind") != "checkpoint-created":
            raise EventValidationError("event is not a checkpoint-created event")
        current = checkpoint["commit"]
        seen = {current}
        while True:
            replacement = next(
                (
                    event["new_commit"]
                    for event in reversed(self.events(checkpoint["work"]))
                    if event.get("kind") == "checkpoint-remapped"
                    and event.get("checkpoint_event_id") == checkpoint["event_id"]
                    and event.get("old_commit") == current
                ),
                None,
            )
            if replacement is None:
                return current
            if replacement in seen:
                raise SharedStoreError(
                    f"checkpoint remap cycle detected at {replacement}"
                )
            seen.add(replacement)
            current = replacement

    def latest_checkpoint(
        self,
        work: str,
        *,
        at_commit: str | None = None,
        cycle_id: str | None = None,
    ) -> dict[str, Any] | None:
        checkpoints = self.events(work, cycle_id=cycle_id, kind="checkpoint-created")
        for checkpoint in reversed(checkpoints):
            resolved = self.resolve_checkpoint_event(checkpoint)
            if not commit_exists(self.repo, resolved):
                continue
            if at_commit is not None and not is_ancestor(
                self.repo, resolved, at_commit
            ):
                continue
            return {**checkpoint, "resolved_commit": resolved}
        return None

    def events_since_checkpoint(
        self,
        work: str,
        checkpoint_event_id: str,
        *,
        cycle_id: str | None = None,
        kind: str | None = None,
        pr: int | None = None,
    ) -> list[dict[str, Any]]:
        events = self.events(work)
        anchor = next(
            (
                position
                for position, event in enumerate(events)
                if event["event_id"] == checkpoint_event_id
                and event["kind"] == "checkpoint-created"
            ),
            None,
        )
        if anchor is None:
            raise EventValidationError(
                f"shared checkpoint event not found: {checkpoint_event_id}"
            )
        output = []
        for event in events[anchor + 1 :]:
            if cycle_id is not None and event.get("cycle_id") != cycle_id:
                continue
            if kind is not None and event.get("kind") != kind:
                continue
            if pr is not None and event.get("pr") != pr:
                continue
            output.append(event)
        return output

    def reconcile_pending_shared_events(
        self, *, retry_missing: bool = False
    ) -> list[dict[str, Any]]:
        """Confirm by event_id first; retry only when explicitly requested and absent."""

        recovery = self._require_recovery()
        results = []
        for begin in recovery.open_begins():
            target = begin.get("target", {})
            if target.get("kind") != "shared-work-event":
                continue
            work = target.get("work")
            event_id = target.get("event_id")
            event = begin.get("expected_change", {}).get("event")
            if not isinstance(work, str) or not isinstance(event_id, str):
                raise RecoveryError("pending shared-event begin lacks work/event_id")
            if not isinstance(event, dict):
                raise RecoveryError(
                    "pending shared-event begin lacks the durable event"
                )
            validate_event(event, expected_work=work)
            if event["event_id"] != event_id:
                raise RecoveryError(
                    "pending shared-event target and payload event_id differ"
                )
            found = self.shared.find_event(work, event_id)
            retried = False
            if found is None and retry_missing:
                retried = True
                self.shared.append_event(work, event)
                found = self.shared.find_event(work, event_id)
            if found is None:
                results.append(
                    {
                        "action_id": begin["action_id"],
                        "event_id": event_id,
                        "status": "absent",
                    }
                )
                continue
            recovery.end(
                begin["action_id"],
                {
                    "shared_event_confirmed": True,
                    "event_id": event_id,
                    "response_was_unknown": True,
                    "retried_after_absence": retried,
                },
            )
            results.append(
                {
                    "action_id": begin["action_id"],
                    "event_id": event_id,
                    "status": "confirmed",
                    "retried": retried,
                }
            )
        return results

    def _base_event(
        self,
        work: str,
        cycle_id: str,
        kind: str,
        producer: str,
        *,
        summary: str | None = None,
        observation: dict[str, Any] | None = None,
        references: list[str] | None = None,
        resolves: list[str] | None = None,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        event: dict[str, Any] = {
            "event_id": event_id or f"evt-{uuid.uuid4().hex}",
            "kind": kind,
            "work": work,
            "cycle_id": cycle_id,
            "producer": producer,
            "created_at": utc_now(),
        }
        if summary is not None:
            event["summary"] = summary
        if observation is not None:
            event["observation"] = copy.deepcopy(observation)
        if references:
            event["references"] = list(references)
        if resolves:
            event["resolves"] = list(resolves)
        return event

    def _publish(self, event: dict[str, Any]) -> dict[str, Any]:
        validate_event(event)
        recovery = self._require_recovery()
        recovery.assert_active_binding(event["work"], event["cycle_id"])
        action_id = f"publish-{event['event_id']}"
        recovery.intent(
            f"Publish shared {event['kind']} event {event['event_id']}",
            action_id=action_id,
            scope=[event["work"]],
        )
        recovery.begin(
            action_id,
            target={
                "kind": "shared-work-event",
                "work": event["work"],
                "event_id": event["event_id"],
            },
            expected_change={"event": copy.deepcopy(event)},
            recovery_check={"find_by_event_id_before_retry": True},
        )
        self.shared.append_event(event["work"], event)
        confirmed = self.shared.find_event(event["work"], event["event_id"])
        if confirmed is None:
            raise SharedStoreError(
                f"shared append returned but event is not observable: {event['event_id']}"
            )
        recovery.end(
            action_id,
            {
                "shared_event_confirmed": True,
                "event_id": event["event_id"],
                "response_was_unknown": False,
            },
        )
        return confirmed

    def _require_recovery(self) -> RecoveryLog:
        if self.recovery is None:
            raise RecoveryError(
                "publishing shared events requires a local recovery binding"
            )
        return self.recovery

"""Protected publication of project-shared work events."""

from __future__ import annotations

from typing import Any

from ..artifacts import resolve_commit
from ..errors import (
    CheckpointError,
    EventValidationError,
    RecoveryError,
    SharedStoreError,
)
from ..recovery import RecoveryLog
from .events import STRUCTURAL_KINDS, assert_same_event, new_event, prepare_event
from .reader import WorkEventReader

_PROTECTED_DETAIL_FIELDS = {
    "event_id",
    "kind",
    "work",
    "cycle_id",
    "producer",
    "created_at",
    "resolves",
    "remote",
}


class WorkEventPublisher:
    """Dedicated event operations plus begin/end-protected remote writes."""

    def __init__(self, reader: WorkEventReader, recovery: RecoveryLog):
        if reader.repo != recovery.repo:
            raise RecoveryError(
                "publisher reader and recovery use different repositories"
            )
        self.reader = reader
        self.recovery = recovery

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
        if kind in STRUCTURAL_KINDS:
            raise EventValidationError(
                f"{kind} is not an ordinary significant event; use its domain operation"
            )
        event = new_event(
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
            event["artifact"] = artifact
        if details:
            overlap = _PROTECTED_DETAIL_FIELDS.intersection(details)
            if overlap:
                raise EventValidationError(
                    f"details cannot replace structural fields: {', '.join(sorted(overlap))}"
                )
            event.update(details)
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
        resolved = resolve_commit(self.reader.repo, commit)
        event = new_event(
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
        checkpoint = self.reader.find_event(work, checkpoint_event_id)
        if checkpoint is None or checkpoint.get("kind") != "checkpoint-created":
            raise CheckpointError(
                "checkpoint remap requires an existing shared checkpoint-created event"
            )
        if checkpoint.get("cycle_id") != cycle_id:
            raise CheckpointError("checkpoint remap cycle does not match checkpoint")
        old_commit = self.reader.resolve_checkpoint_event(checkpoint)
        new_commit = resolve_commit(self.reader.repo, new_commit)
        event = new_event(
            work,
            cycle_id,
            "checkpoint-remapped",
            producer,
            summary=f"Remapped checkpoint {old_commit[:12]} to {new_commit[:12]}",
            references=[checkpoint_event_id],
            event_id=event_id,
        )
        event.update(
            {
                "checkpoint_event_id": checkpoint_event_id,
                "old_commit": old_commit,
                "new_commit": new_commit,
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
        return self._publish(
            new_event(
                work,
                new_cycle_id,
                "work-reopened",
                producer,
                summary=summary,
                event_id=event_id,
            )
        )

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
        if self.reader.find_event(work, target_event_id) is None:
            raise EventValidationError(
                f"cannot resolve missing event: {target_event_id}"
            )
        return self._publish(
            new_event(
                work,
                cycle_id,
                "event-resolved",
                producer,
                summary=summary,
                resolves=[target_event_id],
                references=[target_event_id],
                event_id=event_id,
            )
        )

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
        event = new_event(
            work,
            cycle_id,
            "verification-observed",
            producer,
            summary=summary,
            observation=observation,
            event_id=event_id,
        )
        event["subject_commit"] = resolve_commit(self.reader.repo, subject_commit)
        return self._publish(event)

    def reconcile_pending_shared_events(
        self, *, retry_missing: bool = False
    ) -> list[dict[str, Any]]:
        """Query first; retry only after an explicit absence decision."""

        results = []
        for begin in self.recovery.open_begins():
            target = begin.get("target", {})
            if target.get("kind") != "shared-work-event":
                continue
            event = self._event_from_begin(begin)
            found = self.reader.find_event(event["work"], event["event_id"])
            retried = False
            if found is None and retry_missing:
                retried = True
                self.reader.shared.append_event(event["work"], event)
                found = self.reader.find_event(event["work"], event["event_id"])
            if found is None:
                results.append(
                    {
                        "action_id": begin["action_id"],
                        "event_id": event["event_id"],
                        "status": "absent",
                    }
                )
                continue
            self._finish_confirmation(
                begin["action_id"],
                event,
                found,
                response_was_unknown=True,
                retried=retried,
            )
            results.append(
                {
                    "action_id": begin["action_id"],
                    "event_id": event["event_id"],
                    "status": "confirmed",
                    "retried": retried,
                }
            )
        return results

    def _publish(self, raw_event: dict[str, Any]) -> dict[str, Any]:
        event = prepare_event(raw_event)
        self.recovery.assert_active_binding(event["work"], event["cycle_id"])
        action_id = f"publish-{event['event_id']}"
        existing = self.reader.find_event(event["work"], event["event_id"])
        if existing is not None:
            assert_same_event(event, existing)
            pending = next(
                (
                    begin
                    for begin in self.recovery.open_begins()
                    if begin.get("action_id") == action_id
                ),
                None,
            )
            if pending is not None:
                expected = self._event_from_begin(pending)
                self._finish_confirmation(
                    action_id,
                    expected,
                    existing,
                    response_was_unknown=True,
                )
            return existing

        self.recovery.intent(
            f"Publish shared {event['kind']} event {event['event_id']}",
            action_id=action_id,
            scope=[event["work"]],
        )
        self.recovery.begin(
            action_id,
            target={
                "kind": "shared-work-event",
                "work": event["work"],
                "event_id": event["event_id"],
            },
            expected_change={"event": event},
            recovery_check={"find_by_event_id_before_retry": True},
        )
        self.reader.shared.append_event(event["work"], event)
        confirmed = self.reader.find_event(event["work"], event["event_id"])
        if confirmed is None:
            raise SharedStoreError(
                f"shared append returned but event is not observable: {event['event_id']}"
            )
        self._finish_confirmation(
            action_id,
            event,
            confirmed,
            response_was_unknown=False,
        )
        return confirmed

    def _event_from_begin(self, begin: dict[str, Any]) -> dict[str, Any]:
        target = begin.get("target", {})
        event = begin.get("expected_change", {}).get("event")
        work = target.get("work")
        event_id = target.get("event_id")
        if not isinstance(event, dict) or not isinstance(work, str):
            raise RecoveryError("pending shared-event begin lacks work/event payload")
        event = prepare_event(event, expected_work=work)
        if event["event_id"] != event_id:
            raise RecoveryError(
                "pending shared-event target and payload event_id differ"
            )
        return event

    def _finish_confirmation(
        self,
        action_id: str,
        expected: dict[str, Any],
        observed: dict[str, Any],
        *,
        response_was_unknown: bool,
        retried: bool = False,
    ) -> None:
        assert_same_event(expected, observed)
        self.recovery.end(
            action_id,
            {
                "shared_event_confirmed": True,
                "event_id": expected["event_id"],
                "response_was_unknown": response_was_unknown,
                "retried_after_absence": retried,
            },
        )

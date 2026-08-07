"""Thin coordinator for advancing a local Recovery checkpoint boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..artifacts import commit_exists, head_commit, is_ancestor, structured_status
from ..errors import CheckpointError, RecoveryError
from .log import RecoveryLog

if TYPE_CHECKING:
    from ..worklog import WorkEventReader


def rotate_recovery(
    recovery: RecoveryLog,
    reader: WorkEventReader,
    checkpoint_event_id: str,
    *,
    durable_events_acknowledged: bool,
    next_intent: str,
    local_changes_handling: str | None = None,
) -> dict[str, Any]:
    """Validate shared/Git facts, then persist the local boundary change."""

    if recovery.repo != reader.repo:
        raise RecoveryError("rotation reader and recovery use different repositories")
    binding = recovery._require_current()
    checkpoint = reader.find_event(binding["work"], checkpoint_event_id)
    if checkpoint is None or checkpoint.get("kind") != "checkpoint-created":
        raise CheckpointError(
            "cannot rotate: checkpoint must be a real shared checkpoint-created event"
        )
    if checkpoint.get("cycle_id") != binding["cycle_id"]:
        raise CheckpointError(
            "cannot rotate: checkpoint does not belong to the active work/cycle"
        )

    commit = reader.resolve_checkpoint_event(checkpoint)
    head = head_commit(recovery.repo)
    if head is None or not commit_exists(recovery.repo, commit):
        raise CheckpointError("cannot rotate: checkpoint commit is absent locally")
    if not is_ancestor(recovery.repo, commit, head):
        raise CheckpointError(
            "cannot rotate: checkpoint commit is not on the current artifact path"
        )
    if structured_status(recovery.repo) and not (local_changes_handling or "").strip():
        raise RecoveryError(
            "cannot rotate: local changes are not absorbed or explicitly handled"
        )
    return recovery._advance_boundary(
        checkpoint_event_id=checkpoint_event_id,
        checkpoint_commit=commit,
        head_at_rotation=head,
        durable_events_acknowledged=durable_events_acknowledged,
        next_intent=next_intent,
        local_changes_handling=local_changes_handling,
        expected_binding_id=binding["binding_id"],
    )

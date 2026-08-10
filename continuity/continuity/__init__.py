"""Lean Harness work-continuity reference implementation."""

from .artifacts import ProjectFactsSource
from .context import ContextReconstructor
from .errors import (
    BindingMismatchError,
    CheckpointConflictError,
    CheckpointError,
    ContinuityError,
    DamagedJournalError,
    DamagedStateError,
    EventIdentityConflict,
    EventValidationError,
    GitFactError,
    RecoveryError,
    SharedStoreError,
)
from .github import GitHubWorkState
from .recovery import RecoveryLog, rotate_recovery
from .worklog import SharedWorkLogStore, WorkEventPublisher, WorkEventReader

__all__ = [
    "BindingMismatchError",
    "CheckpointConflictError",
    "CheckpointError",
    "ContextReconstructor",
    "ContinuityError",
    "DamagedJournalError",
    "DamagedStateError",
    "EventIdentityConflict",
    "EventValidationError",
    "GitFactError",
    "GitHubWorkState",
    "ProjectFactsSource",
    "RecoveryError",
    "RecoveryLog",
    "SharedStoreError",
    "SharedWorkLogStore",
    "WorkEventPublisher",
    "WorkEventReader",
    "rotate_recovery",
]

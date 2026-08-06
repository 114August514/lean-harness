"""Domain errors exposed by the continuity reference implementation."""


class ContinuityError(Exception):
    """Base class for expected, diagnosable continuity failures."""

    code = "continuity_error"


class GitFactError(ContinuityError):
    """Git could not provide a required repository fact."""

    code = "git_fact_error"


class RecoveryError(ContinuityError):
    """A local recovery invariant or recovery record is invalid."""

    code = "recovery_error"


class BindingMismatchError(RecoveryError):
    """Requested work does not match the active local binding."""

    code = "binding_mismatch"


class DamagedStateError(RecoveryError):
    """A durable local state file is present but cannot be decoded safely."""

    code = "damaged_recovery_state"


class DamagedJournalError(RecoveryError):
    """A durable recovery journal contains an invalid complete record."""

    code = "damaged_recovery_journal"


class SharedStoreError(ContinuityError):
    """A shared work-log read or write failed."""

    code = "shared_store_error"


class EventIdentityConflict(SharedStoreError):
    """One stable event identity refers to different canonical payloads."""

    code = "event_identity_conflict"


class EventValidationError(ContinuityError):
    """A shared work event is incomplete or structurally invalid."""

    code = "event_validation_error"


class CheckpointError(ContinuityError):
    """A checkpoint request conflicts with observed shared or Git facts."""

    code = "checkpoint_error"


class CheckpointConflictError(CheckpointError):
    """Shared remap events give one checkpoint incompatible successors."""

    code = "checkpoint_conflict"

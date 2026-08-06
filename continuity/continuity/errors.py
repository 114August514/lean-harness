"""Domain errors exposed by the continuity reference implementation."""


class ContinuityError(Exception):
    """Base class for expected, diagnosable continuity failures."""


class GitFactError(ContinuityError):
    """Git could not provide a required repository fact."""


class RecoveryError(ContinuityError):
    """A local recovery invariant or recovery record is invalid."""


class DamagedStateError(RecoveryError):
    """A durable local state file is present but cannot be decoded safely."""


class SharedStoreError(ContinuityError):
    """A shared work-log read or write failed."""


class EventValidationError(ContinuityError):
    """A shared work event is incomplete or structurally invalid."""

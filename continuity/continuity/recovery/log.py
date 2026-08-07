"""Per-worktree, per-binding-generation recovery journal."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import Any

from ..artifacts import current_branch, git_common_dir, git_dir, head_commit
from ..errors import BindingMismatchError, DamagedStateError, RecoveryError
from .records import open_begins, pending_handoffs, unexplained_begins
from .schema import validate_record, validate_state
from .storage import append_jsonl, atomic_write_json, file_lock, read_json, read_jsonl

_WORKTREE_ID = re.compile(r"^wt-[0-9a-f]{32}$")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _persisted_worktree_id(repo: Path) -> str:
    metadata = git_dir(repo) / "lean-harness"
    path = metadata / "worktree.json"
    with file_lock(metadata / "worktree.lock"):
        state = read_json(path)
        if state is not None:
            identity = state.get("worktree_id")
            if (
                state.get("schema_version") != 1
                or not isinstance(identity, str)
                or not _WORKTREE_ID.fullmatch(identity)
            ):
                raise DamagedStateError(
                    f"damaged worktree identity at {path}: invalid schema"
                )
            return identity

        identity = _new_id("wt")
        atomic_write_json(path, {"schema_version": 1, "worktree_id": identity})
        return identity


def _synchronized(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with file_lock(self.lock_path):
            return method(self, *args, **kwargs)

    return wrapped


class RecoveryLog:
    """Local safety net for one Git worktree."""

    def __init__(self, repo: Path):
        self.repo = Path(repo).resolve()
        self.lock_path = git_dir(self.repo) / "lean-harness" / "recovery.lock"
        self.worktree_id = _persisted_worktree_id(self.repo)
        self.root = (
            git_common_dir(self.repo) / "lean-harness" / "recovery" / self.worktree_id
        )

    @property
    def state_path(self) -> Path:
        return self.root / "current-binding.json"

    def _binding_log_path(self, binding_id: str) -> Path:
        return self.root / "bindings" / binding_id / "recovery.jsonl"

    @property
    def log_path(self) -> Path:
        state = self._state()
        return (
            self._binding_log_path(state["binding_id"])
            if state is not None
            else self.root / "no-binding.jsonl"
        )

    @_synchronized
    def bind(
        self,
        work: str,
        cycle_id: str,
        base_checkpoint_event_id: str | None = None,
    ) -> dict[str, Any]:
        if not work.strip() or not cycle_id.strip():
            raise RecoveryError("binding requires non-empty work and cycle_id")
        current = self._state()
        if current is not None:
            if current["status"] == "active":
                raise RecoveryError(
                    "worktree already has an active binding; pause or release it first"
                )
            self._assert_no_unexplained(current, "rebind")

        state: dict[str, Any] = {
            "schema_version": 1,
            "worktree_id": self.worktree_id,
            "binding_id": _new_id("bind"),
            "work": work,
            "cycle_id": cycle_id,
            "status": "active",
            "branch": current_branch(self.repo),
            "head_at_bind": head_commit(self.repo),
            "base_checkpoint_event_id": base_checkpoint_event_id,
            "bound_at": _utc_now(),
        }
        self._append_for(
            state,
            {
                "type": "bound",
                "base_checkpoint_event_id": base_checkpoint_event_id,
                "branch": state["branch"],
                "head_at_bind": state["head_at_bind"],
            },
        )
        self._write_state(state)
        return state

    @_synchronized
    def pause(self) -> dict[str, Any]:
        state = self._require_current()
        self._append_for(state, {"type": "paused"})
        updated = {**state, "status": "paused", "paused_at": _utc_now()}
        self._write_state(updated)
        return updated

    @_synchronized
    def release(self) -> dict[str, Any]:
        state = self._require_current(allow_paused=True)
        self._assert_no_unexplained(state, "release")
        self._append_for(state, {"type": "released"})
        updated = {**state, "status": "released", "released_at": _utc_now()}
        self._write_state(updated)
        return updated

    @_synchronized
    def intent(
        self,
        action: str,
        action_id: str | None = None,
        scope: list[str] | None = None,
    ) -> dict[str, Any]:
        if not action.strip():
            raise RecoveryError("intent action cannot be empty")
        state = self._require_current()
        return self._append_for(
            state,
            {
                "type": "intent",
                "action_id": action_id or _new_id("act"),
                "action": action,
                "scope": list(scope or []),
                "base_checkpoint_event_id": state.get("base_checkpoint_event_id"),
                "head_at_record": head_commit(self.repo),
            },
        )

    @_synchronized
    def begin(
        self,
        action_id: str,
        target: dict[str, Any],
        expected_change: dict[str, Any] | None = None,
        recovery_check: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = self._require_current()
        records = self._records_for(state)
        if any(
            record["type"] == "begin" and record.get("action_id") == action_id
            for record in records
        ):
            raise RecoveryError(f"duplicate begin for action_id: {action_id}")
        return self._append_for(
            state,
            {
                "type": "begin",
                "action_id": action_id,
                "target": target,
                "expected_change": expected_change or {},
                "recovery_check": recovery_check or {},
                "head_at_record": head_commit(self.repo),
            },
        )

    @_synchronized
    def end(self, action_id: str, observation: dict[str, Any]) -> dict[str, Any]:
        state = self._require_current(allow_paused=True)
        records = self._records_for(state)
        begins = {
            record.get("action_id") for record in records if record["type"] == "begin"
        }
        ended = {
            record.get("action_id") for record in records if record["type"] == "end"
        }
        if action_id not in begins:
            raise RecoveryError(f"end without begin for action_id: {action_id}")
        if action_id in ended:
            raise RecoveryError(f"duplicate end for action_id: {action_id}")
        return self._append_for(
            state,
            {
                "type": "end",
                "action_id": action_id,
                "observation": observation,
                "head_at_record": head_commit(self.repo),
            },
        )

    @_synchronized
    def handoff_open_operation(
        self,
        action_id: str,
        summary: str,
        recovery_instructions: str,
    ) -> dict[str, Any]:
        state = self._require_current(allow_paused=True)
        records = self._records_for(state)
        if action_id not in {record["action_id"] for record in open_begins(records)}:
            raise RecoveryError(f"cannot hand off non-open action_id: {action_id}")
        if not summary.strip() or not recovery_instructions.strip():
            raise RecoveryError("recoverable handoff requires summary and instructions")
        if any(
            record["type"] == "operation-handoff"
            and record.get("action_id") == action_id
            for record in records
        ):
            raise RecoveryError(f"duplicate handoff for action_id: {action_id}")
        return self._append_for(
            state,
            {
                "type": "operation-handoff",
                "handoff_id": _new_id("handoff"),
                "action_id": action_id,
                "summary": summary,
                "recovery_instructions": recovery_instructions,
            },
        )

    @_synchronized
    def resolve_handoff(
        self, handoff_id: str, observation: dict[str, Any]
    ) -> dict[str, Any]:
        handoff = next(
            (
                item
                for item in self._pending_handoffs()
                if item["handoff_id"] == handoff_id
            ),
            None,
        )
        if handoff is None:
            raise RecoveryError(f"pending handoff not found: {handoff_id}")
        archived_binding = {
            field: handoff[field] for field in ("binding_id", "work", "cycle_id")
        }
        return self._append_for(
            archived_binding,
            {
                "type": "end",
                "action_id": handoff["action_id"],
                "observation": observation,
                "resolved_from_handoff_id": handoff_id,
                "head_at_record": head_commit(self.repo),
            },
        )

    @_synchronized
    def records(self) -> list[dict[str, Any]]:
        _, records = self._current_records()
        return records

    @_synchronized
    def open_begins(self) -> list[dict[str, Any]]:
        _, records = self._current_records()
        return open_begins(records)

    @_synchronized
    def status(self) -> dict[str, Any]:
        state, records = self._current_records()
        open_records = open_begins(records)
        return {
            "binding": state,
            "latest_intent": next(
                (record for record in reversed(records) if record["type"] == "intent"),
                None,
            ),
            "open_begins": open_records,
            "unexplained_open_begins": unexplained_begins(records, open_records),
            "pending_handoffs": self._pending_handoffs(),
            "record_count": len(records),
            "recovery_root": str(self.root),
        }

    @_synchronized
    def assert_active_binding(self, work: str, cycle_id: str) -> None:
        state = self._require_current()
        if state["work"] != work or state["cycle_id"] != cycle_id:
            raise BindingMismatchError(
                "shared event does not match the active recovery binding: "
                f"bound to {state['work']}/{state['cycle_id']}, requested "
                f"{work}/{cycle_id}"
            )

    @_synchronized
    def _advance_boundary(
        self,
        *,
        checkpoint_event_id: str,
        checkpoint_commit: str,
        head_at_rotation: str,
        durable_events_acknowledged: bool,
        next_intent: str,
        local_changes_handling: str | None,
        expected_binding_id: str,
    ) -> dict[str, Any]:
        """Persist a rotation after external facts have been checked."""

        state = self._require_current()
        if state["binding_id"] != expected_binding_id:
            raise BindingMismatchError(
                "cannot rotate: recovery binding changed during validation"
            )
        self._assert_no_unexplained(state, "rotate")
        if not durable_events_acknowledged:
            raise RecoveryError(
                "cannot rotate: durable event promotion has not been acknowledged"
            )
        if not next_intent.strip():
            raise RecoveryError("cannot rotate: next intent is not explicit")
        record = self._append_for(
            state,
            {
                "type": "rotated",
                "checkpoint_event_id": checkpoint_event_id,
                "checkpoint_commit": checkpoint_commit,
                "head_at_rotation": head_at_rotation,
                "local_changes_handling": local_changes_handling,
                "durable_events_acknowledged": True,
                "next_intent": next_intent,
            },
        )
        intent = self._append_for(
            state,
            {
                "type": "intent",
                "action_id": _new_id("act"),
                "action": next_intent,
                "scope": [],
                "base_checkpoint_event_id": checkpoint_event_id,
                "head_at_record": head_at_rotation,
            },
        )
        updated = {
            **state,
            "base_checkpoint_event_id": checkpoint_event_id,
            "base_checkpoint_commit": checkpoint_commit,
            "rotated_at": _utc_now(),
            "next_intent": next_intent,
        }
        self._write_state(updated)
        return {"binding": updated, "rotation": record, "intent": intent}

    def _state(self) -> dict[str, Any] | None:
        state = read_json(self.state_path)
        if state is not None:
            validate_state(
                state, self.state_path, expected_worktree_id=self.worktree_id
            )
        return state

    def _write_state(self, state: dict[str, Any]) -> None:
        validate_state(state, self.state_path, expected_worktree_id=self.worktree_id)
        atomic_write_json(self.state_path, state)

    def _all_binding_records(self) -> list[dict[str, Any]]:
        bindings = self.root / "bindings"
        if not bindings.exists():
            return []
        records: list[dict[str, Any]] = []
        for path in sorted(bindings.glob("*/recovery.jsonl")):
            records.extend(self._read_records(path, binding_id=path.parent.name))
        return records

    def _pending_handoffs(self) -> list[dict[str, Any]]:
        return pending_handoffs(self._all_binding_records())

    def _current_records(self) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        state = self._state()
        records = self._records_for(state) if state is not None else []
        return state, records

    def _records_for(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        path = self._binding_log_path(state["binding_id"])
        return self._read_records(
            path,
            binding_id=state["binding_id"],
            work=state["work"],
            cycle_id=state["cycle_id"],
        )

    @staticmethod
    def _read_records(
        path: Path,
        *,
        binding_id: str,
        work: str | None = None,
        cycle_id: str | None = None,
    ) -> list[dict[str, Any]]:
        records = read_jsonl(path)
        for record in records:
            validate_record(
                record,
                path,
                expected_binding_id=binding_id,
                expected_work=work,
                expected_cycle_id=cycle_id,
            )
        return records

    def _require_current(self, *, allow_paused: bool = False) -> dict[str, Any]:
        state = self._state()
        if state is None:
            raise RecoveryError("worktree has no recovery binding")
        allowed = {"active", "paused"} if allow_paused else {"active"}
        if state["status"] not in allowed:
            raise RecoveryError(f"binding is {state['status']}, not usable")
        return state

    def _assert_no_unexplained(self, state: dict[str, Any], operation: str) -> None:
        if unexplained_begins(self._records_for(state)):
            raise RecoveryError(
                f"cannot {operation}: unexplained begin record(s) remain"
            )

    def _append_for(
        self, state: dict[str, Any], record: dict[str, Any]
    ) -> dict[str, Any]:
        enriched = {
            "schema_version": 1,
            "record_id": _new_id("rec"),
            "recorded_at": _utc_now(),
            "binding_id": state["binding_id"],
            "work": state["work"],
            "cycle_id": state["cycle_id"],
            **record,
        }
        path = self._binding_log_path(state["binding_id"])
        validate_record(
            enriched,
            path,
            expected_binding_id=state["binding_id"],
            expected_work=state["work"],
            expected_cycle_id=state["cycle_id"],
        )
        append_jsonl(path, enriched)
        return enriched

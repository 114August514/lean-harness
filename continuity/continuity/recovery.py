"""Clone-local, per-worktree, per-binding-generation recovery journal."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .errors import RecoveryError
from .git_facts import (
    commit_exists,
    current_branch,
    git_common_dir,
    head_commit,
    is_ancestor,
    structured_status,
    worktree_id,
)
from .storage import append_jsonl, atomic_write_json, read_json, read_jsonl

if TYPE_CHECKING:
    from .events import WorkEvents


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class RecoveryLog:
    """The local safety net for one Git worktree.

    State lives outside every checkout at::

        <git-common-dir>/lean-harness/recovery/<stable-worktree-id>/

    Every bind creates a fresh ``binding_id`` and a separate append-only journal.
    """

    def __init__(self, repo: Path):
        self.repo = Path(repo).resolve()
        self.worktree_id = worktree_id(self.repo)
        self.root = (
            git_common_dir(self.repo) / "lean-harness" / "recovery" / self.worktree_id
        )

    @property
    def state_path(self) -> Path:
        return self.root / "current-binding.json"

    def binding_log_path(self, binding_id: str) -> Path:
        return self.root / "bindings" / binding_id / "recovery.jsonl"

    @property
    def log_path(self) -> Path:
        state = self._state()
        if state is None:
            return self.root / "no-binding.jsonl"
        return self.binding_log_path(state["binding_id"])

    def bind(
        self,
        work: str,
        cycle_id: str,
        base_checkpoint_event_id: str | None = None,
    ) -> dict[str, Any]:
        current = self._state()
        if current is not None:
            if current.get("status") == "active":
                raise RecoveryError(
                    "worktree already has an active binding; pause or release it first"
                )
            unexplained = self.unexplained_open_begins()
            if unexplained:
                raise RecoveryError(
                    "cannot rebind: current binding has begin record(s) without end "
                    "or recoverable handoff"
                )

        binding_id = f"bind-{uuid.uuid4().hex}"
        state: dict[str, Any] = {
            "schema_version": 1,
            "worktree_id": self.worktree_id,
            "binding_id": binding_id,
            "work": work,
            "cycle_id": cycle_id,
            "status": "active",
            "branch": current_branch(self.repo),
            "head_at_bind": head_commit(self.repo),
            "base_checkpoint_event_id": base_checkpoint_event_id,
            "bound_at": utc_now(),
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
        atomic_write_json(self.state_path, state)
        return state

    def pause(self) -> dict[str, Any]:
        state = self._require_active()
        self._append({"type": "paused"})
        updated = {**state, "status": "paused", "paused_at": utc_now()}
        atomic_write_json(self.state_path, updated)
        return updated

    def release(self) -> dict[str, Any]:
        state = self._require_current(allow_paused=True)
        unexplained = self.unexplained_open_begins()
        if unexplained:
            raise RecoveryError(
                "cannot release: begin record(s) lack end or recoverable handoff"
            )
        self._append({"type": "released"})
        updated = {**state, "status": "released", "released_at": utc_now()}
        atomic_write_json(self.state_path, updated)
        return updated

    def intent(
        self,
        action: str,
        action_id: str | None = None,
        scope: list[str] | None = None,
    ) -> dict[str, Any]:
        self._require_active()
        return self._append(
            {
                "type": "intent",
                "action_id": action_id or f"act-{uuid.uuid4().hex}",
                "action": action,
                "scope": list(scope or []),
                "base_checkpoint_event_id": self._state().get(
                    "base_checkpoint_event_id"
                ),
                "head_at_record": head_commit(self.repo),
            }
        )

    def begin(
        self,
        action_id: str,
        target: dict[str, Any],
        expected_change: dict[str, Any] | None = None,
        recovery_check: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._require_active()
        if any(
            record.get("type") == "begin" and record.get("action_id") == action_id
            for record in self.records()
        ):
            raise RecoveryError(f"duplicate begin for action_id: {action_id}")
        return self._append(
            {
                "type": "begin",
                "action_id": action_id,
                "target": target,
                "expected_change": expected_change or {},
                "recovery_check": recovery_check or {},
                "head_at_record": head_commit(self.repo),
            }
        )

    def end(self, action_id: str, observation: dict[str, Any]) -> dict[str, Any]:
        self._require_current(allow_paused=True)
        records = self.records()
        if not any(
            record.get("type") == "begin" and record.get("action_id") == action_id
            for record in records
        ):
            raise RecoveryError(f"end without begin for action_id: {action_id}")
        if any(
            record.get("type") == "end" and record.get("action_id") == action_id
            for record in records
        ):
            raise RecoveryError(f"duplicate end for action_id: {action_id}")
        return self._append(
            {
                "type": "end",
                "action_id": action_id,
                "observation": observation,
                "head_at_record": head_commit(self.repo),
            }
        )

    def handoff_open_operation(
        self,
        action_id: str,
        summary: str,
        recovery_instructions: str,
    ) -> dict[str, Any]:
        """Explain an open operation so release/rebind can remain recoverable."""

        self._require_current(allow_paused=True)
        if action_id not in {item["action_id"] for item in self.open_begins()}:
            raise RecoveryError(f"cannot hand off non-open action_id: {action_id}")
        if not summary.strip() or not recovery_instructions.strip():
            raise RecoveryError("recoverable handoff requires summary and instructions")
        return self._append(
            {
                "type": "operation-handoff",
                "action_id": action_id,
                "summary": summary,
                "recovery_instructions": recovery_instructions,
            }
        )

    def records(self) -> list[dict[str, Any]]:
        state = self._state()
        if state is None:
            return []
        return read_jsonl(self.binding_log_path(state["binding_id"]))

    def open_begins(self) -> list[dict[str, Any]]:
        begins: dict[str, dict[str, Any]] = {}
        ended: set[str] = set()
        for record in self.records():
            action_id = record.get("action_id")
            if record.get("type") == "begin" and isinstance(action_id, str):
                begins[action_id] = record
            elif record.get("type") == "end" and isinstance(action_id, str):
                ended.add(action_id)
        return [begin for key, begin in begins.items() if key not in ended]

    def unexplained_open_begins(self) -> list[dict[str, Any]]:
        handed_off = {
            record["action_id"]
            for record in self.records()
            if record.get("type") == "operation-handoff"
        }
        return [
            begin
            for begin in self.open_begins()
            if begin["action_id"] not in handed_off
        ]

    def status(self) -> dict[str, Any]:
        state = self._state()
        records = self.records()
        latest_intent = next(
            (record for record in reversed(records) if record.get("type") == "intent"),
            None,
        )
        return {
            "binding": state,
            "latest_intent": latest_intent,
            "open_begins": self.open_begins(),
            "unexplained_open_begins": self.unexplained_open_begins(),
            "record_count": len(records),
            "recovery_root": str(self.root),
        }

    def assert_active_binding(self, work: str, cycle_id: str) -> dict[str, Any]:
        state = self._require_active()
        if state["work"] != work or state["cycle_id"] != cycle_id:
            raise RecoveryError(
                "shared event does not match the active recovery binding: "
                f"bound to {state['work']}/{state['cycle_id']}, requested "
                f"{work}/{cycle_id}"
            )
        return state

    def rotate(
        self,
        checkpoint_event_id: str,
        work_events: WorkEvents,
        *,
        durable_events_confirmed: bool,
        next_phase: str,
        local_changes_handling: str | None = None,
    ) -> dict[str, Any]:
        """Advance the recovery boundary only after validating a shared checkpoint."""

        state = self._require_active()
        if self.unexplained_open_begins():
            raise RecoveryError("cannot rotate: unexplained begin record(s) remain")
        checkpoint = work_events.find_event(state["work"], checkpoint_event_id)
        if checkpoint is None or checkpoint.get("kind") != "checkpoint-created":
            raise RecoveryError(
                "cannot rotate: checkpoint must be a real shared checkpoint-created event"
            )
        if (
            checkpoint.get("work") != state["work"]
            or checkpoint.get("cycle_id") != state["cycle_id"]
        ):
            raise RecoveryError(
                "cannot rotate: checkpoint does not belong to the active work/cycle"
            )
        commit = work_events.resolve_checkpoint_event(checkpoint)
        head = head_commit(self.repo)
        if head is None or not commit_exists(self.repo, commit):
            raise RecoveryError("cannot rotate: checkpoint commit is absent locally")
        if not is_ancestor(self.repo, commit, head):
            raise RecoveryError(
                "cannot rotate: checkpoint commit is not on the current artifact path"
            )
        changes = structured_status(self.repo)
        if changes and not (local_changes_handling or "").strip():
            raise RecoveryError(
                "cannot rotate: local changes are not absorbed or explicitly handled"
            )
        if not durable_events_confirmed:
            raise RecoveryError(
                "cannot rotate: durable shared events have not been confirmed published"
            )
        if not next_phase.strip():
            raise RecoveryError("cannot rotate: next phase is not explicit")

        record = self._append(
            {
                "type": "rotated",
                "checkpoint_event_id": checkpoint_event_id,
                "checkpoint_commit": commit,
                "head_at_rotation": head,
                "local_changes_handling": local_changes_handling,
                "next_phase": next_phase,
            }
        )
        updated = {
            **state,
            "base_checkpoint_event_id": checkpoint_event_id,
            "base_checkpoint_commit": commit,
            "rotated_at": utc_now(),
            "next_phase": next_phase,
        }
        atomic_write_json(self.state_path, updated)
        return {"binding": updated, "rotation": record}

    def _state(self) -> dict[str, Any] | None:
        return read_json(self.state_path)

    def _require_current(self, *, allow_paused: bool = False) -> dict[str, Any]:
        state = self._state()
        if state is None:
            raise RecoveryError("worktree has no recovery binding")
        allowed = {"active", "paused"} if allow_paused else {"active"}
        if state.get("status") not in allowed:
            raise RecoveryError(f"binding is {state.get('status')}, not usable")
        return state

    def _require_active(self) -> dict[str, Any]:
        return self._require_current()

    def _append(self, record: dict[str, Any]) -> dict[str, Any]:
        return self._append_for(self._require_current(allow_paused=True), record)

    def _append_for(
        self, state: dict[str, Any], record: dict[str, Any]
    ) -> dict[str, Any]:
        enriched = {
            "record_id": f"rec-{uuid.uuid4().hex}",
            "recorded_at": utc_now(),
            "binding_id": state["binding_id"],
            "work": state["work"],
            "cycle_id": state["cycle_id"],
            **record,
        }
        append_jsonl(self.binding_log_path(state["binding_id"]), enriched)
        return enriched

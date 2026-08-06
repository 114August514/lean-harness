"""每个活跃 worktree 的恢复日志。

恢复日志保护最近检查点之后尚未稳定的执行现场：

- ``intent``：当前已经确定准备做什么（普通本地工作只需要它）；
- ``begin`` / ``end``：结果不透明或不能安全重复的操作（远端写等）；

恢复判断规则：

- 只有 intent        → 行动已经确定，但未确认开始；
- 有 begin，没有 end  → 操作已经发起，结果未知；
- 存在 end            → 操作已经返回，按 observation 和当前状态判断下一步。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .store import JsonlStore, StoreError, current_branch, head_commit, now_iso

LOG_NAME = "log.jsonl"
STATE_NAME = "state.json"

# 合法状态：active / paused / released
_ACTIVE = "active"


@dataclass
class RecoveryLog:
    store: JsonlStore

    @property
    def log_path(self) -> Path:
        return self.store.recovery_dir / LOG_NAME

    @property
    def state_path(self) -> Path:
        return self.store.recovery_dir / STATE_NAME

    # --- 绑定 ---

    def bind(self, work: str, cycle_id: str, base_checkpoint: str | None) -> dict:
        """把当前 worktree 绑定到某个 work unit，创建或接续恢复日志。"""
        if self._state() and self._state().get("status") == _ACTIVE:
            raise StoreError(
                "worktree already has an active binding; "
                "use 'recovery pause' or 'recovery release' first"
            )
        head = head_commit(self.store.repo)
        state = {
            "work": work,
            "cycle_id": cycle_id,
            "branch": current_branch(self.store.repo),
            "base_checkpoint": base_checkpoint,
            "bound_at": now_iso(),
            "head_at_bind": head,
            "status": _ACTIVE,
        }
        import json

        self.store.recovery_dir.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._append(
            {
                "type": "bound",
                "work": work,
                "cycle_id": cycle_id,
                "branch": state["branch"],
                "base_checkpoint": base_checkpoint,
                "head_at_bind": head,
            }
        )
        return state

    def pause(self) -> dict:
        state = self._require_active()
        state["status"] = "paused"
        state["paused_at"] = now_iso()
        self._write_state(state)
        self._append({"type": "paused"})
        return state

    def release(self) -> dict:
        """解除绑定。调用方应已确认没有未解释的 begin 无 end。"""
        state = self._require()
        state["status"] = "released"
        state["released_at"] = now_iso()
        self._write_state(state)
        self._append({"type": "released"})
        return state

    # --- 记录 ---

    def intent(
        self,
        action: str,
        action_id: str | None = None,
        scope: list[str] | None = None,
    ) -> dict:
        state = self._require_active()
        record = {
            "type": "intent",
            "work": state["work"],
            "cycle_id": state["cycle_id"],
            "action_id": action_id or self._next_action_id("intent"),
            "action": action,
            "scope": scope or [],
            "worktree": self.store.repo.name,
            "base_checkpoint": state.get("base_checkpoint"),
            "head_at_record": head_commit(self.store.repo),
        }
        return self._append(record)

    def begin(
        self,
        action_id: str,
        target: dict,
        expected_change: dict | None = None,
        recovery_check: dict | None = None,
    ) -> dict:
        """在副作用发生前持久化。"""
        state = self._require_active()
        record = {
            "type": "begin",
            "work": state["work"],
            "cycle_id": state["cycle_id"],
            "action_id": action_id,
            "target": target,
            "expected_change": expected_change or {},
            "recovery_check": recovery_check or {},
            "head_at_record": head_commit(self.store.repo),
        }
        return self._append(record)

    def end(self, action_id: str, observation: dict) -> dict:
        """操作返回并获得可靠观察后记录。

        end 只表示操作已经返回、观察结果已经记录，
        不表示目标、Claim 或验收已经满足。
        """
        self._require_active()
        if not any(
            r.get("type") == "begin" and r.get("action_id") == action_id
            for r in self.records()
        ):
            raise StoreError(f"end without begin for action_id: {action_id}")
        record = {
            "type": "end",
            "action_id": action_id,
            "observation": observation,
            "head_at_record": head_commit(self.store.repo),
        }
        return self._append(record)

    # --- 读取 ---

    def records(self) -> list[dict]:
        return self.store.read(self.log_path)

    def status(self) -> dict:
        state = self._state() or {}
        records = self.records()
        latest_intent = next(
            (r for r in reversed(records) if r.get("type") == "intent"), None
        )
        return {
            "binding": state,
            "latest_intent": latest_intent,
            "open_begins": self.open_begins(),
            "record_count": len(records),
        }

    def open_begins(self) -> list[dict]:
        """有 begin 但尚未有 end 的操作：结果未知。"""
        begins: dict[str, dict] = {}
        ended: set[str] = set()
        for r in self.records():
            if r.get("type") == "begin":
                begins[r["action_id"]] = r
            elif r.get("type") == "end":
                ended.add(r["action_id"])
        return [b for aid, b in begins.items() if aid not in ended]

    # --- 轮转 ---

    def rotate(self, new_checkpoint: str, force: bool = False) -> dict:
        """把已被新检查点吸收的记录移入 archive，只保留仍需保护的现场。

        轮转条件（除非 force）：

        - 不存在未解释的 begin 无 end；
        - 新 checkpoint 是当前 HEAD 的祖先（本地修改已被吸收）；
        - 调用方已另行确认长期事件提升与下一步明确（CLI 用 --force 表达）。
        """
        from .store import is_ancestor

        state = self._require_active()
        records = self.records()
        open_begins = self.open_begins()
        if open_begins and not force:
            raise StoreError(
                f"cannot rotate: {len(open_begins)} begin record(s) without end; "
                "confirm the external operations first or pass --force"
            )
        head = head_commit(self.store.repo)
        absorbed = head is not None and is_ancestor(
            self.store.repo, new_checkpoint, head
        )
        if not absorbed and not force:
            raise StoreError(
                f"cannot rotate: {new_checkpoint} is not an ancestor of HEAD; "
                "local changes are not absorbed by this checkpoint"
            )

        kept = [
            r
            for r in records
            if r.get("type") in ("begin", "end") and r.get("action_id")
            and r["action_id"] not in self._ended_action_ids(records)
        ]
        if force:
            kept = [
                r
                for r in records
                if r.get("type") in ("begin", "end")
                and r.get("action_id") in {b["action_id"] for b in self.open_begins()}
            ]
        archive_name = f"archive-{new_checkpoint}.jsonl"
        archived = [r for r in records if r not in kept]
        if archived:
            archive_path = self.store.recovery_dir / archive_name
            for r in archived:
                self.store.append(archive_path, r)

        self.store.rewrite(self.log_path, kept)
        state["base_checkpoint"] = new_checkpoint
        state["rotated_at"] = now_iso()
        self._write_state(state)
        self._append({"type": "rotated", "new_checkpoint": new_checkpoint})
        return {
            "archived": len(archived),
            "kept": len(kept),
            "base_checkpoint": new_checkpoint,
        }

    # --- 内部 ---

    def _append(self, record: dict) -> dict:
        record = {"ts": now_iso(), **record}
        return self.store.append(self.log_path, record)

    def _state(self) -> dict | None:
        import json

        if not self.state_path.exists():
            return None
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _require(self) -> dict:
        state = self._state()
        if state is None:
            raise StoreError(
                "worktree is not bound to any work unit; run 'recovery bind' first"
            )
        return state

    def _require_active(self) -> dict:
        state = self._require()
        if state.get("status") != _ACTIVE:
            raise StoreError(f"binding is {state.get('status')}, not active")
        return state

    def _write_state(self, state: dict) -> None:
        import json

        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _next_action_id(self, prefix: str) -> str:
        n = sum(1 for r in self.records() if r.get("type") == prefix) + 1
        return f"{prefix}-{n}"

    @staticmethod
    def _ended_action_ids(records: list[dict]) -> set[str]:
        return {r["action_id"] for r in records if r.get("type") == "end"}

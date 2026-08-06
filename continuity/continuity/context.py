"""上下文恢复：把各来源组合成 replacement agent 的恢复输入。

组合规则见 ``contract.md`` 第七节。本模块只收集和整理事实，
不判断目标是否达成，也不决定下一步——那是 Skills 的职责。
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from .recovery import RecoveryLog
from .store import JsonlStore, current_branch, head_commit
from .worklog import WorkLog


@dataclass
class ResumeContext:
    store: JsonlStore
    worklog: WorkLog
    recovery: RecoveryLog

    def _git_status(self) -> dict:
        def run(*args: str) -> str:
            out = subprocess.run(
                ["git", "-C", str(self.store.repo), *args],
                capture_output=True,
                text=True,
                check=False,
            )
            return out.stdout

        return {
            "head": head_commit(self.store.repo),
            "branch": current_branch(self.store.repo),
            # porcelain v1 每行是两位状态码 + 空格 + 路径；重命名为 "old -> new"。
            # 不能用 strip() 处理整行：前导空格本身是未暂存修改的状态列。
            "dirty_files": [
                line[3:].split(" -> ", 1)[-1].strip().strip('"')
                for line in run("status", "--porcelain").splitlines()
                if line
            ],
        }

    def load(self, work: str | None = None, cycle_id: str | None = None) -> dict:
        """加载恢复输入。

        未显式给出 ``work`` 时，使用当前 worktree 绑定的工作。
        """
        binding = self.recovery._state() or {}
        work = work or binding.get("work")
        git = self._git_status()

        result: dict = {
            "work": work,
            "cycle_id": cycle_id or binding.get("cycle_id"),
            "binding": binding or None,
            "git": git,
            "latest_checkpoint": None,
            "work_events_since_checkpoint": [],
            "unresolved_work_events": [],
            "recovery_log": None,
        }

        if work is not None:
            checkpoint = self.worklog.latest_checkpoint(work, at_commit=git["head"])
            result["latest_checkpoint"] = checkpoint
            if checkpoint is not None:
                result["work_events_since_checkpoint"] = self.worklog.events_since(
                    work,
                    checkpoint["commit"],
                    at_commit=git["head"],
                )
            else:
                result["work_events_since_checkpoint"] = self.worklog.events(work)
            result["unresolved_work_events"] = self.worklog.unresolved_events(work)

        if binding:
            result["recovery_log"] = {
                "latest_intent": next(
                    (
                        r
                        for r in reversed(self.recovery.records())
                        if r.get("type") == "intent"
                    ),
                    None,
                ),
                "open_begins": self.recovery.open_begins(),
            }

        return result

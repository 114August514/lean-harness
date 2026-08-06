"""Project 范围、按 Issue / Work Unit 分区的工作日志。

只记录会长期影响理解、判断或恢复的重要事件。判断标准：

    未来恢复或调查这个 Issue 时，这条事件是否会改变
    对当前方向、风险或历史原因的理解？

每个分区（一个 Issue / Work Unit）一个 JSONL 文件，事件带分区内
单调序号 ``seq`` 表达追加顺序；时间戳用于阅读，不单独承担因果排序。
"""

from __future__ import annotations

from dataclasses import dataclass

from .store import (
    JsonlStore,
    StoreError,
    commit_exists,
    is_ancestor,
    now_iso,
    resolve_commit,
)

# 具有长期价值的事件类型
EVENT_KINDS = {
    "work-started",  # Issue 开始处理
    "work-reopened",  # Issue 重新打开（沿用原分区，新建 cycle）
    "finding",  # 关键调查结论 / 关键新事实
    "hypothesis-resolved",  # 重要假设被支持或排除
    "direction-changed",  # 重要方向调整 / 原方案被排除
    "scope-changed",  # 实质范围变化
    "checkpoint-created",  # 显式确认一个 coherent commit 为连续性检查点
    "checkpoint-remapped",  # rebase / cherry-pick / squash 后的 commit 映射
    "verification-observed",  # Evidence 针对某个 commit 产生
    "evidence-staled",  # 后续变化使旧 Evidence 失效
    "review-finding",  # Review Finding 被提出
    "review-finding-resolved",  # Review Finding 被解决
    "remediation-completed",  # remediation 完成
    "worker-result-absorbed",  # worker 结果被主 Agent 吸收
    "handoff",  # HANDOFF
    "pr-opened",
    "pr-closed",
    "pr-merged",
    "cycle-finished",  # 当前周期达到最终状态
    "work-finished",  # Issue 达到最终状态
}


@dataclass
class WorkLog:
    store: JsonlStore

    def append(
        self,
        work: str,
        kind: str,
        cycle_id: str | None = None,
        summary: str | None = None,
        unresolved: bool = False,
        resolves: list[int] | None = None,
        fields: dict | None = None,
    ) -> dict:
        """追加一条工作事件。

        ``fields`` 按事件类型携带必要的最小字段，例如
        ``commit`` / ``subject_commit`` / ``pr`` / ``observation`` /
        ``old_commit`` / ``new_commit`` / ``reason``。
        """
        if kind not in EVENT_KINDS:
            raise StoreError(f"unknown event kind: {kind}")
        path = self.store.work_log_path(work)
        seq = len(self.store.read(path)) + 1
        record = {
            "seq": seq,
            "kind": kind,
            "work": work,
            "ts": now_iso(),
            **(fields or {}),
        }
        if cycle_id is not None:
            record["cycle_id"] = cycle_id
        if summary is not None:
            record["summary"] = summary
        if unresolved:
            record["unresolved"] = True
        if resolves:
            record["resolves"] = list(resolves)
        return self.store.append(path, record)

    def reopen(self, work: str, new_cycle_id: str, summary: str | None = None) -> dict:
        """Issue 重新打开：沿用原分区，追加 work-reopened，创建新周期。"""
        return self.append(
            work,
            "work-reopened",
            cycle_id=new_cycle_id,
            summary=summary,
        )

    def checkpoint(self, work: str, cycle_id: str, commit: str, **extra) -> dict:
        """显式确认一个 coherent commit 为连续性检查点。"""
        commit = resolve_commit(self.store.repo, commit)
        if not commit_exists(self.store.repo, commit):
            raise StoreError(f"not a commit in this repository: {commit}")
        return self.append(
            work,
            "checkpoint-created",
            cycle_id=cycle_id,
            fields={"commit": commit, **extra},
        )

    def remap_checkpoint(
        self, work: str, cycle_id: str, old_commit: str, new_commit: str, reason: str
    ) -> dict:
        """历史改写（rebase / cherry-pick / squash）后追加映射，不修改旧事件。"""
        old_commit = resolve_commit(self.store.repo, old_commit)
        new_commit = resolve_commit(self.store.repo, new_commit)
        return self.append(
            work,
            "checkpoint-remapped",
            cycle_id=cycle_id,
            fields={
                "old_commit": old_commit,
                "new_commit": new_commit,
                "reason": reason,
            },
        )

    def events(
        self,
        work: str,
        cycle_id: str | None = None,
        kind: str | None = None,
        pr: int | None = None,
    ) -> list[dict]:
        records = self.store.read(self.store.work_log_path(work))
        out = []
        for r in records:
            if cycle_id is not None and r.get("cycle_id") != cycle_id:
                continue
            if kind is not None and r.get("kind") != kind:
                continue
            if pr is not None and r.get("pr") != pr:
                continue
            out.append(r)
        return out

    # --- 检查点定位与增量读取 ---

    def resolve_commit(self, work: str, commit: str) -> str:
        """沿 checkpoint-remapped 映射链把旧 commit 解析为当前等效 commit。"""
        seen = set()
        current = commit
        while True:
            if current in seen:
                raise StoreError(f"remap cycle detected at {current}")
            seen.add(current)
            nxt = next(
                (
                    r["new_commit"]
                    for r in self.events(work, kind="checkpoint-remapped")
                    if r.get("old_commit") == current
                ),
                None,
            )
            if nxt is None:
                return current
            current = nxt

    def latest_checkpoint(self, work: str, at_commit: str | None = None) -> dict | None:
        """定位当前工作路径上最近的相关检查点。

        ``at_commit`` 给定时，只考虑是该 commit 祖先的检查点
        （remap 后的 new_commit 也参与祖先判断）。
        """
        checkpoints = self.events(work, kind="checkpoint-created")
        for cp in reversed(checkpoints):
            resolved = self.resolve_commit(work, cp["commit"])
            if at_commit is None:
                return {**cp, "resolved_commit": resolved}
            if is_ancestor(self.store.repo, resolved, at_commit):
                return {**cp, "resolved_commit": resolved}
        return None

    def _effective_commit(self, work: str, event: dict) -> str | None:
        """事件关联的 commit（考虑 remap 后的映射）。"""
        for key in ("commit", "subject_commit", "result_commit", "head_at_event"):
            if event.get(key):
                return self.resolve_commit(work, event[key])
        return None

    def events_since(
        self,
        work: str,
        checkpoint_commit: str,
        at_commit: str | None = None,
        cycle_id: str | None = None,
        kind: str | None = None,
        pr: int | None = None,
    ) -> list[dict]:
        """读取检查点之后的相关工作事件。

        "之后" 按追加顺序（分区内单调 seq）定义，不是按时间戳。
        """
        checkpoint_commit = self.resolve_commit(work, checkpoint_commit)
        anchor = None
        for r in self.events(work):
            if r.get("kind") == "checkpoint-created" and (
                self.resolve_commit(work, r["commit"]) == checkpoint_commit
            ):
                anchor = r["seq"]
        out = []
        for r in self.events(work, cycle_id=cycle_id, kind=kind, pr=pr):
            if anchor is not None and r["seq"] <= anchor:
                continue
            eff = self._effective_commit(work, r)
            if (
                eff is not None
                and at_commit is not None
                and not is_ancestor(self.store.repo, eff, at_commit)
            ):
                continue
            out.append(r)
        return out

    def unresolved_events(self, work: str) -> list[dict]:
        """仍被明确标记为未解决或继续相关的事件。"""
        resolved: set[int] = set()
        for r in self.events(work):
            for seq in r.get("resolves", []):
                resolved.add(seq)
        return [
            r
            for r in self.events(work)
            if r.get("unresolved") and r["seq"] not in resolved
        ]

    def cycle_events(self, work: str, cycle_id: str) -> list[dict]:
        return self.events(work, cycle_id=cycle_id)

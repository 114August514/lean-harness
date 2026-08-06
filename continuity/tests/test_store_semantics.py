"""存储层与工作日志语义的单元测试。"""

from __future__ import annotations

import subprocess

import pytest

from continuity import JsonlStore, StoreError, WorkLog

from .conftest import commit_file, git


def test_work_log_survives_worktree_removal(repo, parts, tmp_path):
    """工作日志不依赖单个 worktree 生命周期。"""
    _, _, worklog, _ = parts
    worklog.append("issue-5", "work-started", cycle_id="cycle-1")
    wt = tmp_path / "wt"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-q", str(wt), "-b", "feat/t"],
        check=True,
    )
    # worktree 中的 worklog 指向同一分区
    worklog_wt = WorkLog(JsonlStore(wt))
    assert len(worklog_wt.events("issue-5")) == 1
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "remove", "--force", str(wt)],
        check=True,
    )
    assert len(worklog.events("issue-5")) == 1


def test_recovery_log_not_tracked_by_git(repo, parts):
    """恢复日志不被 Git 跟踪，也不进入 PR diff（由 .gitignore 排除）。"""
    _, recovery, _, _ = parts
    (repo / ".gitignore").write_text("docs/journal/recovery/\n", encoding="utf-8")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-qm", "gitignore")
    recovery.bind("issue-5", "cycle-1", base_checkpoint=None)
    recovery.intent("x")
    rel = recovery.log_path.relative_to(repo)
    assert str(rel).startswith("docs/journal/recovery/")
    out = git(repo, "status", "--porcelain", "--", str(rel))
    assert out == ""  # 被 .gitignore 排除


def test_seq_monotonic_within_partition(repo, parts):
    """分区内单调序号表达追加顺序。"""
    _, _, worklog, _ = parts
    e1 = worklog.append("issue-5", "work-started", cycle_id="cycle-1")
    e2 = worklog.append("issue-5", "finding", cycle_id="cycle-1")
    assert (e1["seq"], e2["seq"]) == (1, 2)
    # 不同分区序号独立
    other = worklog.append("issue-8", "work-started", cycle_id="cycle-1")
    assert other["seq"] == 1


def test_checkpoint_requires_existing_commit(repo, parts):
    """不能给不存在的 commit 创建检查点。"""
    _, _, worklog, _ = parts
    with pytest.raises(StoreError):
        worklog.checkpoint("issue-5", "cycle-1", "0" * 40)


def test_end_without_begin_rejected(repo, parts):
    _, recovery, _, _ = parts
    recovery.bind("issue-5", "cycle-1", base_checkpoint=None)
    with pytest.raises(StoreError, match="end without begin"):
        recovery.end("nope", observation={})


def test_rotate_moves_absorbed_records(repo, parts):
    """轮转自恢复日志移出已被吸收的记录，保留 begin 无 end 的操作。"""
    _, recovery, worklog, _ = parts
    recovery.bind("issue-5", "cycle-1", base_checkpoint=None)
    recovery.intent("旧 intent")
    recovery.begin("pending-op", target={"kind": "github-issue", "id": 5})
    new_commit = commit_file(repo, "a.py", "x=1\n", "work")
    worklog.checkpoint("issue-5", "cycle-1", new_commit)
    result = recovery.rotate(new_commit, force=True)
    assert result["archived"] >= 2  # bound + intent 被移出
    assert result["kept"] == 1  # pending-op 的 begin 保留
    assert recovery.status()["open_begins"][0]["action_id"] == "pending-op"


def test_bind_twice_rejected(repo, parts):
    _, recovery, _, _ = parts
    recovery.bind("issue-5", "cycle-1", base_checkpoint=None)
    with pytest.raises(StoreError, match="already has an active binding"):
        recovery.bind("issue-9", "cycle-1", base_checkpoint=None)


def test_pause_and_release(repo, parts):
    _, recovery, _, _ = parts
    recovery.bind("issue-5", "cycle-1", base_checkpoint=None)
    recovery.pause()
    with pytest.raises(StoreError, match="not active"):
        recovery.intent("x")
    recovery.release()
    # release 后可重新绑定
    recovery.bind("issue-9", "cycle-1", base_checkpoint=None)
    assert recovery.status()["binding"]["work"] == "issue-9"

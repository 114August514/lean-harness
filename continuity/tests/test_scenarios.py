"""场景测试：覆盖 issue 第十节列出的中断与恢复场景。

每个测试对应 issue 中至少一个验收场景，使用真实 Git 仓库和真实文件写入，
不依赖 Agent 按提示词模拟。
"""

from __future__ import annotations

import subprocess

import pytest

from continuity import JsonlStore, RecoveryLog, StoreError

from .conftest import commit_file, git

# --- 本地中断 ---


def test_local_interruption_resume_and_new_checkpoint(repo, parts):
    """写入 intent → 修改文件 → 中断 → replacement 读取恢复日志和
    dirty working tree → 正确继续 → 形成新检查点。"""
    _, recovery, worklog, resume = parts
    base = git(repo, "rev-parse", "HEAD")

    recovery.bind("issue-5", "cycle-1", base_checkpoint=base)
    recovery.intent("实现恢复日志轮转")
    (repo / "new.py").write_text("# uncommitted work\n", encoding="utf-8")
    # session 中断：没有 commit，没有 end

    # replacement agent
    ctx = resume.load()
    assert ctx["recovery_log"]["latest_intent"]["action"] == "实现恢复日志轮转"
    assert "new.py" in ctx["git"]["dirty_files"]

    new_commit = commit_file(repo, "new.py", "# uncommitted work\n", "add new")
    worklog.checkpoint("issue-5", "cycle-1", new_commit)
    cp = worklog.latest_checkpoint("issue-5", at_commit=new_commit)
    assert cp["resolved_commit"] == new_commit


def test_intent_written_then_immediate_interruption(repo, parts):
    """intent 写入后立即中断：只有 intent，行动已确定但未确认开始。"""
    _, recovery, _, resume = parts
    recovery.bind("issue-5", "cycle-1", base_checkpoint=None)
    recovery.intent("下一步运行定向测试")
    ctx = resume.load()
    assert ctx["recovery_log"]["latest_intent"]["action"] == "下一步运行定向测试"
    assert ctx["recovery_log"]["open_begins"] == []


def test_local_changes_not_yet_committed(repo, parts):
    """本地修改尚未 commit：恢复上下文应包含 dirty working tree。"""
    _, recovery, _, resume = parts
    recovery.bind("issue-5", "cycle-1", base_checkpoint=None)
    recovery.intent("修改契约文档")
    (repo / "README.md").write_text("# changed\n", encoding="utf-8")
    ctx = resume.load()
    assert "README.md" in ctx["git"]["dirty_files"]


def test_dirty_files_exact_paths(repo, parts):
    """dirty_files 必须是精确路径，不含 porcelain 状态前缀或前导空格。"""
    _, recovery, _, resume = parts
    recovery.bind("issue-5", "cycle-1", base_checkpoint=None)
    (repo / "x.py").write_text("x=1\n", encoding="utf-8")
    (repo / "README.md").write_text("# m\n", encoding="utf-8")
    ctx = resume.load()
    assert "x.py" in ctx["git"]["dirty_files"]
    assert "README.md" in ctx["git"]["dirty_files"]
    for f in ctx["git"]["dirty_files"]:
        assert f == f.strip(), f"path has surrounding whitespace: {f!r}"
        # porcelain 状态列已被剥离，路径不应以状态码 + 空格开头
        assert not f.startswith(("M ", "A ", "D ", "R ", "?? ")), f"status prefix: {f!r}"


# --- begin/end 语义 ---


def test_end_records_failure_exit_code_without_declaring_goal_failed(repo, parts):
    """end 记录非零退出码，但不声明目标失败。"""
    _, recovery, _, _ = parts
    recovery.bind("issue-5", "cycle-1", base_checkpoint=None)
    recovery.begin("run-check", target={"kind": "command", "cmd": "pytest"})
    recovery.end("run-check", observation={"exit_code": 1, "response_received": True})
    status = recovery.status()
    assert status["open_begins"] == []


def test_cannot_rotate_with_unconfirmed_external_op(repo, parts):
    """commit 已形成，但存在未确认外部操作，不能清理恢复日志。"""
    _, recovery, worklog, _ = parts
    recovery.bind("issue-5", "cycle-1", base_checkpoint=None)
    recovery.begin(
        "update-issue", target={"kind": "github-issue", "id": 5}
    )
    new_commit = commit_file(repo, "a.py", "x=1\n", "work")
    worklog.checkpoint("issue-5", "cycle-1", new_commit)
    with pytest.raises(StoreError, match="begin"):
        recovery.rotate(new_commit)


def test_normal_checkout_does_not_start_binding(repo):
    """普通只读 checkout 不启动工作绑定。"""
    store = JsonlStore(repo)
    recovery = RecoveryLog(store)
    # 只读操作：checkout main / 查看旧版本，不调用 bind
    git(repo, "checkout", "-q", "main")
    assert recovery.status()["binding"] == {}
    assert not recovery.log_path.exists()


def test_two_workers_use_independent_worktrees_and_logs(repo, parts, tmp_path):
    """两个 worker 使用独立 worktree 和独立恢复日志。"""
    git(repo, "checkout", "-q", "-b", "feat/a")
    git(repo, "checkout", "-q", "main")
    wt_b = tmp_path / "wt-b"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-q", str(wt_b), "-b", "feat/b"],
        check=True,
    )

    _, recovery_a, _, _ = parts
    recovery_a.bind("issue-5", "cycle-1", base_checkpoint=None)
    recovery_a.intent("worker A 的任务")

    store_b = JsonlStore(wt_b)
    recovery_b = RecoveryLog(store_b)
    recovery_b.bind("issue-5", "cycle-1", base_checkpoint=None)
    recovery_b.intent("worker B 的任务")

    assert recovery_a.log_path != recovery_b.log_path
    assert recovery_a.status()["latest_intent"]["action"] == "worker A 的任务"
    assert recovery_b.status()["latest_intent"]["action"] == "worker B 的任务"


def test_worker_candidate_events_absorbed_by_main_agent(repo, parts):
    """worker 候选事件由主 Agent 检查后追加，worker 不直接写工作日志。"""
    _, _, worklog, _ = parts
    # worker 在自己的上下文里形成候选事件（此处直接由主 Agent 追加）
    worklog.append(
        "issue-5",
        "finding",
        cycle_id="cycle-1",
        summary="worker 发现旧假设不成立",
        fields={"head_at_event": git(repo, "rev-parse", "HEAD")},
    )
    events = worklog.events("issue-5")
    assert len(events) == 1
    assert events[0]["kind"] == "finding"


# --- 工作日志生命周期 ---


def test_issue_reopened_creates_new_cycle(repo, parts):
    """Issue 重新打开：沿用原分区，追加 work-reopened，创建新 cycle_id。"""
    _, _, worklog, _ = parts
    worklog.append("issue-5", "work-started", cycle_id="cycle-1")
    worklog.append("issue-5", "work-finished", cycle_id="cycle-1")
    worklog.reopen("issue-5", "cycle-2", summary="review 后发现遗漏")
    cycle1 = worklog.events("issue-5", cycle_id="cycle-1")
    cycle2 = worklog.events("issue-5", cycle_id="cycle-2")
    assert [e["kind"] for e in cycle1] == ["work-started", "work-finished"]
    assert [e["kind"] for e in cycle2] == ["work-reopened"]
    assert worklog.events("issue-5")[-1]["cycle_id"] == "cycle-2"


def test_issue_spans_multiple_prs(repo, parts):
    """一个 Issue 关联多个 PR，事件可按 PR 过滤。"""
    _, _, worklog, _ = parts
    worklog.append("issue-5", "pr-opened", cycle_id="cycle-1", fields={"pr": 4})
    worklog.append("issue-5", "pr-merged", cycle_id="cycle-1", fields={"pr": 4})
    worklog.append("issue-5", "pr-opened", cycle_id="cycle-1", fields={"pr": 6})
    pr4 = worklog.events("issue-5", pr=4)
    pr6 = worklog.events("issue-5", pr=6)
    assert [e["kind"] for e in pr4] == ["pr-opened", "pr-merged"]
    assert [e["kind"] for e in pr6] == ["pr-opened"]


# --- Evidence 与检查点 ---


def test_evidence_staled_by_later_change(repo, parts):
    """Evidence 对应旧 commit，后续变化使其失效。"""
    _, _, worklog, _ = parts
    old = commit_file(repo, "a.py", "x=1\n", "old")
    worklog.append(
        "issue-5",
        "verification-observed",
        cycle_id="cycle-1",
        fields={"subject_commit": old, "observation": {"check": "pytest", "exit_code": 0}},
    )
    new = commit_file(repo, "a.py", "x=2\n", "change")
    cp_event = worklog.checkpoint("issue-5", "cycle-1", new)
    stale = worklog.append(
        "issue-5",
        "evidence-staled",
        cycle_id="cycle-1",
        summary="a.py 变化使旧验证失效",
        fields={"subject_commit": old},
        resolves=[1],
    )
    assert stale["resolves"] == [1]
    since = worklog.events_since("issue-5", cp_event["commit"])
    assert any(e["kind"] == "evidence-staled" for e in since)


def test_checkpoint_remapped_after_rebase(repo, parts):
    """checkpoint 经 rebase 后追加映射，旧事件不修改。"""
    _, _, worklog, _ = parts
    old = git(repo, "rev-parse", "HEAD")
    worklog.checkpoint("issue-5", "cycle-1", old)
    new = commit_file(repo, "a.py", "x=1\n", "rebased work")
    worklog.remap_checkpoint("issue-5", "cycle-1", old, new, reason="rebase")
    assert worklog.resolve_commit("issue-5", old) == new
    cp = worklog.latest_checkpoint("issue-5", at_commit=new)
    assert cp["resolved_commit"] == new


def test_squash_merge_locates_final_commit(repo, parts):
    """squash merge 后能够定位最终 commit。"""
    _, _, worklog, _ = parts
    git(repo, "checkout", "-q", "-b", "feat/x")
    commit_file(repo, "x.py", "x=1\n", "x1")
    src_head = commit_file(repo, "x.py", "x=2\n", "x2")
    worklog.checkpoint("issue-5", "cycle-1", src_head)
    git(repo, "checkout", "-q", "main")
    subprocess.run(
        ["git", "-C", str(repo), "merge", "--squash", "-q", "feat/x"], check=True
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "squashed"], check=True
    )
    merge_commit = git(repo, "rev-parse", "HEAD")
    worklog.remap_checkpoint(
        "issue-5", "cycle-1", src_head, merge_commit, reason="squash merge"
    )
    assert worklog.resolve_commit("issue-5", src_head) == merge_commit


# --- 恢复与一致性 ---


def test_reconstruct_changes_between_log_and_current_state(repo, parts):
    """当前状态与历史日志不同，但能够重建变化。"""
    _, recovery, worklog, resume = parts
    base = git(repo, "rev-parse", "HEAD")
    recovery.bind("issue-5", "cycle-1", base_checkpoint=base)
    worklog.checkpoint("issue-5", "cycle-1", base)
    worklog.append(
        "issue-5",
        "verification-observed",
        cycle_id="cycle-1",
        fields={"subject_commit": base},
    )
    commit_file(repo, "b.py", "y=1\n", "later work")
    ctx = resume.load()
    assert ctx["latest_checkpoint"]["resolved_commit"] == base
    assert ctx["git"]["head"] != base
    assert len(ctx["work_events_since_checkpoint"]) == 1


def test_corrupt_trailing_line_does_not_break_prior_records(repo, parts):
    """损坏或不完整的恢复日志尾部不会破坏此前记录。"""
    _, recovery, _, _ = parts
    recovery.bind("issue-5", "cycle-1", base_checkpoint=None)
    recovery.intent("第一条")
    log_path = recovery.log_path
    with open(log_path, "ab") as f:
        f.write(b'{"type":"intent","action":"corru')  # 不完整尾部
    status = recovery.status()
    assert status["latest_intent"]["action"] == "第一条"
    # 截断后文件以完整行结尾
    assert log_path.read_bytes().endswith(b"\n")


# --- 工作日志增量恢复 ---


def test_work_log_incremental_recovery(repo, parts):
    """多检查点 + PR 的 Issue：定位最近检查点，读取增量，保留未解决旧事件。"""
    _, _, worklog, _ = parts
    c1 = commit_file(repo, "a.py", "x=1\n", "c1")
    worklog.checkpoint("issue-5", "cycle-1", c1)
    worklog.append(
        "issue-5",
        "finding",
        cycle_id="cycle-1",
        summary="旧发现",
        unresolved=True,
        fields={"subject_commit": c1},
    )
    c2 = commit_file(repo, "b.py", "y=1\n", "c2")
    worklog.checkpoint("issue-5", "cycle-1", c2)
    worklog.append(
        "issue-5",
        "pr-opened",
        cycle_id="cycle-1",
        fields={"pr": 7},
    )

    cp = worklog.latest_checkpoint("issue-5", at_commit=c2)
    assert cp["resolved_commit"] == c2
    since = worklog.events_since("issue-5", cp["commit"], at_commit=c2)
    assert [e["kind"] for e in since] == ["pr-opened"]
    unresolved = worklog.unresolved_events("issue-5")
    assert len(unresolved) == 1 and unresolved[0]["summary"] == "旧发现"

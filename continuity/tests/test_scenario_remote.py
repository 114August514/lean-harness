"""场景测试：外部操作结果未知（契约第三节 / issue 第十节）。

写入 begin → fake remote 接受写入 → 模拟响应丢失（不写 end）→
replacement agent 发现 begin 无 end → 查询远端状态 → 不重复写入 →
补充 end。
"""

from __future__ import annotations

from continuity import RecoveryLog

from .fake_remote import FakeRemote


def test_unknown_remote_result_not_retried(repo, parts, tmp_path):
    _, recovery, _, resume = parts
    remote = FakeRemote(tmp_path / "remote.json")

    recovery.bind("issue-5", "cycle-1", base_checkpoint=None)
    recovery.intent("更新 issue-5 描述")
    recovery.begin(
        "update-issue-5",
        target={"kind": "github-issue", "id": 5},
        expected_change={"body_contains": "Git 检查点"},
        recovery_check={"read_target_before_retry": True},
    )
    # 副作用真实发生，但响应丢失：没有写入 end
    remote.write("issue-5-body", "... Git 检查点 ...")
    assert remote.write_count == 1

    # replacement agent：发现 begin 无 end，先查真实状态，不盲目重试
    status = RecoveryLog(resume.store).status()
    assert len(status["open_begins"]) == 1
    assert status["open_begins"][0]["action_id"] == "update-issue-5"

    observed = remote.read("issue-5-body")
    assert observed is not None and "Git 检查点" in observed
    # 关键断言：没有第二次写入
    assert remote.write_count == 1

    recovery.end(
        "update-issue-5",
        observation={"response_received": False, "remote_observed": True},
    )
    assert RecoveryLog(resume.store).status()["open_begins"] == []

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import threading

import continuity.storage as local_storage
import pytest
from continuity.git_facts import git_common_dir, structured_status
from continuity.storage import read_jsonl

from continuity import DamagedStateError, RecoveryError, RecoveryLog

from .conftest import commit_file, git


def test_recovery_is_git_metadata_local_and_per_worktree(repo, system, tmp_path):
    _, recovery, _, _ = system
    recovery.bind("issue-5", "cycle-1")
    assert recovery.root.is_relative_to(git_common_dir(repo))
    assert git(repo, "status", "--porcelain") == ""

    linked = tmp_path / "linked"
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "worktree",
            "add",
            "-q",
            "-b",
            "linked-work",
            str(linked),
        ],
        check=True,
    )
    linked_recovery = RecoveryLog(linked)
    linked_recovery.bind("issue-5", "cycle-1")
    assert linked_recovery.worktree_id != recovery.worktree_id
    assert linked_recovery.root != recovery.root
    assert RecoveryLog(linked).worktree_id == linked_recovery.worktree_id


def test_binding_generation_isolation(repo, system):
    _, recovery, _, _ = system
    first = recovery.bind("issue-5", "cycle-1")
    recovery.intent("Implement issue five")
    first_log = recovery.log_path
    recovery.release()

    second = recovery.bind("issue-9", "cycle-1")
    status = recovery.status()
    assert first["binding_id"] != second["binding_id"]
    assert recovery.log_path != first_log
    assert status["latest_intent"] is None
    assert status["open_begins"] == []
    assert all(record["work"] == "issue-9" for record in recovery.records())
    assert first_log.exists()


def test_open_begin_requires_end_or_cross_generation_handoff(repo, system):
    _, recovery, _, context = system
    recovery.bind("issue-5", "cycle-1")
    recovery.begin(
        "publish-unknown",
        target={"kind": "shared-work-event", "event_id": "evt-x"},
    )
    with pytest.raises(RecoveryError, match="cannot release"):
        recovery.release()
    recovery.pause()
    with pytest.raises(RecoveryError, match="cannot rebind"):
        recovery.bind("issue-9", "cycle-1")
    handoff = recovery.handoff_open_operation(
        "publish-unknown",
        "Remote result is unknown",
        "Query issue 5 before any retry",
    )
    released = recovery.release()
    assert released["status"] == "released"
    recovery.bind("issue-9", "cycle-1")
    assert recovery.status()["open_begins"] == []
    pending = recovery.status()["pending_handoffs"]
    assert [item["handoff_id"] for item in pending] == [handoff["handoff_id"]]
    assert pending[0]["work"] == "issue-5"
    assert context.load()["local_recovery"]["pending_handoffs"] == []

    recovery.resolve_handoff(
        handoff["handoff_id"], {"remote_exists": True, "comment_id": 41}
    )
    assert recovery.status()["pending_handoffs"] == []


def test_state_updates_are_atomic_and_damage_is_diagnostic(repo, system, monkeypatch):
    _, recovery, _, _ = system
    original = recovery.bind("issue-5", "cycle-1")

    def interrupted_replace(source, destination):
        raise OSError("simulated interruption before atomic replace")

    monkeypatch.setattr(local_storage.os, "replace", interrupted_replace)
    with pytest.raises(OSError, match="simulated interruption"):
        recovery.pause()

    decoded = json.loads(recovery.state_path.read_text(encoding="utf-8"))
    assert decoded == original
    assert recovery.status()["binding"]["status"] == "active"

    recovery.state_path.write_text('{"binding_id":', encoding="utf-8")
    with pytest.raises(DamagedStateError, match="damaged recovery state"):
        recovery.status()


def test_jsonl_repair_rechecks_tail_after_waiting_for_writer(tmp_path, monkeypatch):
    path = tmp_path / "recovery.jsonl"
    writer = path.open("wb")
    fcntl.flock(writer.fileno(), fcntl.LOCK_EX)
    writer.write(b'{"record_id":"rec-1"')
    writer.flush()
    os.fsync(writer.fileno())

    reader_waiting = threading.Event()
    original_lock = local_storage._lock

    def announcing_lock(fd):
        reader_waiting.set()
        original_lock(fd)

    monkeypatch.setattr(local_storage, "_lock", announcing_lock)
    result = {}

    def read_records():
        result["records"] = read_jsonl(path)

    reader = threading.Thread(target=read_records)
    try:
        reader.start()
        assert reader_waiting.wait(timeout=2)
        writer.write(b',"value":1}\n')
        writer.flush()
        os.fsync(writer.fileno())
    finally:
        fcntl.flock(writer.fileno(), fcntl.LOCK_UN)
        writer.close()
    reader.join(timeout=2)

    assert not reader.is_alive()
    assert result["records"] == [{"record_id": "rec-1", "value": 1}]
    assert path.read_bytes().endswith(b"\n")


def test_structured_git_status_preserves_index_worktree_rename_and_conflict(repo):
    commit_file(repo, "old.txt", "old\n", "add old path")
    commit_file(repo, "conflict.txt", "base\n", "add conflict target")
    git(repo, "checkout", "-qb", "other")
    commit_file(repo, "conflict.txt", "other\n", "other side")
    git(repo, "checkout", "-q", "main")
    commit_file(repo, "conflict.txt", "main\n", "main side")
    result = subprocess.run(
        ["git", "-C", str(repo), "merge", "other"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0

    (repo / "README.md").write_text("unstaged\n", encoding="utf-8")
    (repo / "added.py").write_text("staged = True\n", encoding="utf-8")
    git(repo, "add", "added.py")
    git(repo, "mv", "old.txt", "new.txt")

    by_path = {change["path"]: change for change in structured_status(repo)}
    assert by_path["README.md"] == {
        "index_status": " ",
        "worktree_status": "M",
        "path": "README.md",
        "conflict": False,
    }
    assert by_path["added.py"]["index_status"] == "A"
    assert by_path["added.py"]["worktree_status"] == " "
    assert by_path["new.txt"]["index_status"] == "R"
    assert by_path["new.txt"]["original_path"] == "old.txt"
    conflict = by_path["conflict.txt"]
    assert conflict["index_status"] == "U"
    assert conflict["worktree_status"] == "U"
    assert conflict["conflict"] is True


def test_rotation_enforces_shared_checkpoint_local_and_remote_facts(repo, system):
    _, recovery, events, _ = system
    recovery.bind("issue-5", "cycle-1")
    finding = events.append_significant(
        "issue-5",
        "cycle-1",
        "finding",
        "agent:test",
        summary="Not a checkpoint",
    )
    with pytest.raises(RecoveryError, match="real shared checkpoint"):
        recovery.rotate(
            finding["event_id"],
            events,
            durable_events_acknowledged=True,
            next_intent="continue",
        )
    checkpoint_commit = commit_file(repo, "work.py", "done = True\n", "coherent")
    checkpoint = events.create_checkpoint(
        "issue-5", "cycle-1", checkpoint_commit, "agent:test"
    )
    (repo / "scratch.txt").write_text("next phase\n", encoding="utf-8")

    with pytest.raises(RecoveryError, match="local changes"):
        recovery.rotate(
            checkpoint["event_id"],
            events,
            durable_events_acknowledged=True,
            next_intent="verification",
        )

    recovery.begin("unknown-write", target={"kind": "github", "id": 5})
    with pytest.raises(RecoveryError, match="unexplained begin"):
        recovery.rotate(
            checkpoint["event_id"],
            events,
            durable_events_acknowledged=True,
            next_intent="verification",
            local_changes_handling="scratch.txt belongs to the next phase",
        )
    recovery.end("unknown-write", {"remote_exists": False})

    result = recovery.rotate(
        checkpoint["event_id"],
        events,
        durable_events_acknowledged=True,
        next_intent="verification",
        local_changes_handling="scratch.txt belongs to the next phase",
    )
    assert result["binding"]["base_checkpoint_event_id"] == checkpoint["event_id"]
    assert result["rotation"]["checkpoint_commit"] == checkpoint_commit

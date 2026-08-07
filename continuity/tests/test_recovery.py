from __future__ import annotations

import subprocess
import threading

import pytest
from continuity.artifacts import git_common_dir

from continuity import (
    CheckpointError,
    RecoveryError,
    RecoveryLog,
    rotate_recovery,
)

from .conftest import commit_file, git


def test_recovery_is_git_metadata_local_and_per_worktree(repo, recovery, tmp_path):
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


def test_binding_generation_isolation(recovery):
    first = recovery.bind("issue-5", "cycle-1")
    recovery.intent("Implement issue five")
    recovery.begin("completed-write", target={"kind": "remote"})
    recovery.end("completed-write", {"remote_exists": True})
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


def test_open_begin_requires_end_or_cross_generation_handoff(recovery, context):
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


def test_recovery_transition_lock_prevents_release_begin_race(
    repo, recovery, monkeypatch
):
    release_log = recovery
    release_log.bind("issue-5", "cycle-1")
    begin_log = RecoveryLog(repo)
    release_checked = threading.Event()
    continue_release = threading.Event()
    begin_started = threading.Event()
    begin_done = threading.Event()
    outcomes = {}
    original_records_for = release_log._records_for

    def pause_after_release_check(state):
        records = original_records_for(state)
        if threading.current_thread().name == "release-worker":
            release_checked.set()
            assert continue_release.wait(timeout=2)
        return records

    def release_worker():
        outcomes["release"] = release_log.release()

    def begin_worker():
        begin_started.set()
        try:
            outcomes["begin"] = begin_log.begin(
                "concurrent-write", target={"kind": "remote"}
            )
        except RecoveryError as error:
            outcomes["begin_error"] = error
        finally:
            begin_done.set()

    monkeypatch.setattr(release_log, "_records_for", pause_after_release_check)
    release_thread = threading.Thread(target=release_worker, name="release-worker")
    release_thread.start()
    assert release_checked.wait(timeout=2)

    begin_thread = threading.Thread(target=begin_worker)
    begin_thread.start()
    assert begin_started.wait(timeout=2)
    assert not begin_done.wait(timeout=0.1)
    continue_release.set()
    release_thread.join(timeout=2)
    begin_thread.join(timeout=2)

    assert outcomes["release"]["status"] == "released"
    assert "released" in str(outcomes["begin_error"])
    assert release_log.open_begins() == []


def test_rotation_enforces_shared_checkpoint_local_and_remote_facts(
    repo, recovery, reader, publisher
):
    recovery.bind("issue-5", "cycle-1")
    finding = publisher.append_significant(
        "issue-5",
        "cycle-1",
        "finding",
        "agent:test",
        summary="Not a checkpoint",
    )
    with pytest.raises(CheckpointError, match="real shared checkpoint"):
        rotate_recovery(
            recovery,
            reader,
            finding["event_id"],
            durable_events_acknowledged=True,
            next_intent="continue",
        )
    checkpoint_commit = commit_file(repo, "work.py", "done = True\n", "coherent")
    checkpoint = publisher.create_checkpoint(
        "issue-5", "cycle-1", checkpoint_commit, "agent:test"
    )
    (repo / "scratch.txt").write_text("next phase\n", encoding="utf-8")

    with pytest.raises(RecoveryError, match="local changes"):
        rotate_recovery(
            recovery,
            reader,
            checkpoint["event_id"],
            durable_events_acknowledged=True,
            next_intent="verification",
        )

    recovery.begin("unknown-write", target={"kind": "github", "id": 5})
    with pytest.raises(RecoveryError, match="unexplained begin"):
        rotate_recovery(
            recovery,
            reader,
            checkpoint["event_id"],
            durable_events_acknowledged=True,
            next_intent="verification",
            local_changes_handling="scratch.txt belongs to the next phase",
        )
    recovery.end("unknown-write", {"remote_exists": False})

    result = rotate_recovery(
        recovery,
        reader,
        checkpoint["event_id"],
        durable_events_acknowledged=True,
        next_intent="verification",
        local_changes_handling="scratch.txt belongs to the next phase",
    )
    assert result["binding"]["base_checkpoint_event_id"] == checkpoint["event_id"]
    assert result["rotation"]["checkpoint_commit"] == checkpoint_commit


def test_rotation_next_intent_becomes_the_latest_intent(
    repo, recovery, reader, publisher, context
):
    recovery.bind("issue-5", "cycle-1")
    recovery.intent("Implement the shared publisher")
    checkpoint_commit = commit_file(repo, "work.py", "done = True\n", "coherent")
    checkpoint = publisher.create_checkpoint(
        "issue-5", "cycle-1", checkpoint_commit, "agent:test"
    )

    result = rotate_recovery(
        recovery,
        reader,
        checkpoint["event_id"],
        durable_events_acknowledged=True,
        next_intent="verification",
    )

    assert result["intent"]["action"] == "verification"
    assert result["intent"]["base_checkpoint_event_id"] == checkpoint["event_id"]
    status = recovery.status()
    assert status["latest_intent"]["record_id"] == result["intent"]["record_id"]
    assert context.load()["local_recovery"]["latest_intent"]["action"] == "verification"

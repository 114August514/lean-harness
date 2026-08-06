from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from continuity.git_facts import git_common_dir, git_dir

from continuity import ContextReconstructor, RecoveryError, RecoveryLog, WorkEvents

from .conftest import commit_file, configure_user, git
from .fakes import FakeSharedStore


def test_local_interruption_reconstructs_intent_and_structured_git(repo, system):
    _, recovery, _, context = system
    recovery.bind("issue-5", "cycle-1")
    recovery.intent("Implement the shared publisher", scope=["continuity/events.py"])
    (repo / "continuity.py").write_text("unfinished = True\n", encoding="utf-8")

    replacement = context.load()
    assert replacement["local_recovery"]["latest_intent"]["action"] == (
        "Implement the shared publisher"
    )
    change = next(
        item
        for item in replacement["git"]["changes"]
        if item["path"] == "continuity.py"
    )
    assert change["index_status"] == "?"
    assert change["worktree_status"] == "?"
    assert replacement["issue_or_spec"]["number"] == 5


def test_explicit_resume_never_mixes_a_different_binding(repo, system):
    _, recovery, _, context = system
    recovery.bind("issue-5", "cycle-1")
    recovery.intent("Issue five local state")

    with pytest.raises(RecoveryError, match="does not match local recovery"):
        context.load("issue-9", "cycle-1")


def test_shared_only_resume_does_not_create_worktree_identity(repo):
    shared = FakeSharedStore()
    events = WorkEvents(repo, shared)
    identity_path = git_dir(repo) / "lean-harness" / "worktree.json"
    assert not identity_path.exists()

    context = ContextReconstructor(
        repo, events, recovery=None, project_facts=shared
    ).load("issue-5", "cycle-1", shared_only=True)

    assert context["work"] == "issue-5"
    assert context["local_recovery"] is None
    assert not identity_path.exists()


def _independent_clones(tmp_path: Path) -> tuple[Path, Path, Path]:
    seed = tmp_path / "seed"
    seed.mkdir()
    git(seed, "init", "-q", "-b", "main")
    configure_user(seed)
    (seed / "README.md").write_text("# shared project\n", encoding="utf-8")
    git(seed, "add", "README.md")
    git(seed, "commit", "-qm", "initial")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(seed), str(remote)], check=True)
    clone_a = tmp_path / "clone-a"
    clone_b = tmp_path / "clone-b"
    subprocess.run(["git", "clone", "-q", str(remote), str(clone_a)], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(clone_b)], check=True)
    configure_user(clone_a)
    configure_user(clone_b)
    return remote, clone_a, clone_b


def test_fresh_clone_recovers_shared_direction_evidence_and_handoff(tmp_path):
    _, clone_a, clone_b = _independent_clones(tmp_path)
    shared = FakeSharedStore()

    recovery_a = RecoveryLog(clone_a)
    recovery_a.bind("issue-5", "cycle-1")
    events_a = WorkEvents(clone_a, shared, recovery_a)
    old_unresolved = events_a.append_significant(
        "issue-5",
        "cycle-1",
        "finding",
        "collaborator:a",
        summary="Migration risk still needs an owner",
        unresolved=True,
        event_id="evt-old-risk",
    )
    checkpoint_commit = commit_file(
        clone_a, "continuity.py", "shared = True\n", "shared continuity"
    )
    git(clone_a, "push", "-q", "origin", "main")
    checkpoint = events_a.create_checkpoint(
        "issue-5",
        "cycle-1",
        checkpoint_commit,
        "collaborator:a",
        event_id="evt-shared-checkpoint",
    )
    events_a.append_significant(
        "issue-5",
        "cycle-1",
        "direction-changed",
        "collaborator:a",
        summary="Use GitHub Issue comments instead of tracked JSONL",
        event_id="evt-direction",
    )
    events_a.record_verification(
        "issue-5",
        "cycle-1",
        checkpoint_commit,
        {"command": "pytest", "exit_code": 0},
        "collaborator:a",
        summary="Continuity tests passed",
        event_id="evt-evidence",
    )
    events_a.append_significant(
        "issue-5",
        "cycle-1",
        "handoff",
        "collaborator:a",
        summary="Continue with checkpoint rotation validation",
        event_id="evt-handoff",
    )

    git(clone_b, "pull", "-q", "--ff-only")
    recovery_b = RecoveryLog(clone_b)
    events_b = WorkEvents(clone_b, shared, recovery_b)
    context_b = ContextReconstructor(
        clone_b, events_b, recovery_b, project_facts=shared
    ).load("issue-5", "cycle-1")

    assert git_common_dir(clone_a) != git_common_dir(clone_b)
    assert not recovery_b.state_path.exists()
    assert context_b["local_recovery"] is None
    assert context_b["latest_checkpoint"]["event_id"] == checkpoint["event_id"]
    assert [event["kind"] for event in context_b["shared_events_since_checkpoint"]] == [
        "direction-changed",
        "verification-observed",
        "handoff",
    ]
    assert context_b["earlier_unresolved_shared_events"] == [old_unresolved]
    assert context_b["issue_or_spec"]["body"] == "Acceptance and scope facts"
    assert context_b["pull_request"]["number"] == 6

    recovery_b.bind(
        "issue-5", "cycle-1", base_checkpoint_event_id=checkpoint["event_id"]
    )
    next_commit = commit_file(clone_b, "next.py", "continued = True\n", "continue")
    next_checkpoint = events_b.create_checkpoint(
        "issue-5",
        "cycle-1",
        next_commit,
        "collaborator:b",
        event_id="evt-next-checkpoint",
    )
    assert next_checkpoint["producer"] == "collaborator:b"
    assert len(events_b.events("issue-5", kind="checkpoint-created")) == 2


def test_checkpoint_remap_is_readable_from_a_fresh_clone(repo, system, tmp_path):
    shared, recovery, events, _ = system
    recovery.bind("issue-5", "cycle-1")
    git(repo, "checkout", "-qb", "feature")
    old_commit = commit_file(repo, "feature.py", "value = 1\n", "feature commit")
    checkpoint = events.create_checkpoint(
        "issue-5",
        "cycle-1",
        old_commit,
        "collaborator:a",
        event_id="evt-pre-squash",
    )
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "--squash", "feature")
    git(repo, "commit", "-qm", "squashed feature")
    new_commit = git(repo, "rev-parse", "HEAD")
    assert (
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "merge-base",
                "--is-ancestor",
                old_commit,
                new_commit,
            ],
            check=False,
        ).returncode
        != 0
    )
    events.remap_checkpoint(
        "issue-5",
        "cycle-1",
        checkpoint["event_id"],
        new_commit,
        "squash merge",
        "collaborator:a",
        event_id="evt-squash-remap",
    )
    assert events.find_event("issue-5", checkpoint["event_id"])["commit"] == old_commit

    remote = tmp_path / "history.git"
    clone_b = tmp_path / "fresh-clone"
    subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(remote)], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(clone_b)], check=True)
    configure_user(clone_b)
    recovery_b = RecoveryLog(clone_b)
    events_b = WorkEvents(clone_b, shared, recovery_b)
    context = ContextReconstructor(clone_b, events_b, recovery_b).load(
        "issue-5", "cycle-1"
    )

    assert context["latest_checkpoint"]["event_id"] == "evt-pre-squash"
    assert context["latest_checkpoint"]["resolved_commit"] == new_commit
    assert context["shared_events_since_checkpoint"][0]["event_id"] == (
        "evt-squash-remap"
    )

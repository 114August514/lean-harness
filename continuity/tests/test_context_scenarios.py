from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from continuity.artifacts import git_common_dir, git_dir
from continuity.worklog.events import prepare_event

from continuity import (
    BindingMismatchError,
    ContextReconstructor,
    RecoveryLog,
    WorkEventPublisher,
    WorkEventReader,
)

from .conftest import commit_file, configure_user, git
from .fakes import FakeProjectFacts, FakeSharedStore


def test_local_interruption_reconstructs_intent_and_structured_git(
    repo, recovery, context
):
    recovery.bind("issue-5", "cycle-1")
    recovery.intent(
        "Implement the shared publisher",
        scope=["continuity/worklog/publication.py"],
    )
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


def test_explicit_resume_never_mixes_a_different_binding(recovery, context):
    recovery.bind("issue-5", "cycle-1")

    with pytest.raises(
        BindingMismatchError, match="does not match local recovery"
    ) as failure:
        context.load("issue-9", "cycle-1")
    assert failure.value.code == "binding_mismatch"


def test_shared_only_resume_does_not_create_worktree_identity(
    repo, shared, project_facts
):
    reader = WorkEventReader(repo, shared)
    identity_path = git_dir(repo) / "lean-harness" / "worktree.json"
    assert not identity_path.exists()

    context = ContextReconstructor(reader, project_facts=project_facts).load(
        "issue-5", "cycle-1"
    )

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
    facts = FakeProjectFacts()

    recovery_a = RecoveryLog(clone_a)
    recovery_a.bind("issue-5", "cycle-1")
    reader_a = WorkEventReader(clone_a, shared)
    publisher_a = WorkEventPublisher(reader_a, recovery_a)
    old_unresolved = publisher_a.append_significant(
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
    checkpoint = publisher_a.create_checkpoint(
        "issue-5",
        "cycle-1",
        checkpoint_commit,
        "collaborator:a",
        event_id="evt-shared-checkpoint",
    )
    publisher_a.append_significant(
        "issue-5",
        "cycle-1",
        "direction-changed",
        "collaborator:a",
        summary="Use GitHub Issue comments instead of tracked JSONL",
        event_id="evt-direction",
    )
    publisher_a.record_verification(
        "issue-5",
        "cycle-1",
        checkpoint_commit,
        {"command": "pytest", "exit_code": 0},
        "collaborator:a",
        summary="Continuity tests passed",
        event_id="evt-evidence",
    )
    publisher_a.append_significant(
        "issue-5",
        "cycle-1",
        "handoff",
        "collaborator:a",
        summary="Continue with checkpoint rotation validation",
        event_id="evt-handoff",
    )

    git(clone_b, "pull", "-q", "--ff-only")
    recovery_b = RecoveryLog(clone_b)
    reader_b = WorkEventReader(clone_b, shared)
    context_b = ContextReconstructor(
        reader_b, project_facts=facts, recovery=recovery_b
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
    publisher_b = WorkEventPublisher(reader_b, recovery_b)
    next_commit = commit_file(clone_b, "next.py", "continued = True\n", "continue")
    next_checkpoint = publisher_b.create_checkpoint(
        "issue-5",
        "cycle-1",
        next_commit,
        "collaborator:b",
        event_id="evt-next-checkpoint",
    )
    assert next_checkpoint["producer"] == "collaborator:b"
    assert len(reader_b.events("issue-5", kind="checkpoint-created")) == 2


def test_reopened_cycle_without_checkpoint_keeps_earlier_unresolved_events(
    repo, recovery, context, reader, publisher, project_facts
):
    recovery.bind("issue-5", "cycle-1")
    old_unresolved = publisher.append_significant(
        "issue-5",
        "cycle-1",
        "finding",
        "collaborator:a",
        summary="Migration risk still needs an owner",
        unresolved=True,
        event_id="evt-old-risk",
    )
    recovery.pause()
    # The reopen event is published by the new cycle's binding.
    recovery.bind("issue-5", "cycle-2")
    publisher.reopen_work(
        "issue-5",
        "cycle-2",
        "collaborator:a",
        "Reopen to finish the migration",
        event_id="evt-reopen",
    )

    resumed = context.load()
    assert resumed["cycle_id"] == "cycle-2"
    assert resumed["latest_checkpoint"] is None
    assert [
        event["event_id"] for event in resumed["shared_events_since_checkpoint"]
    ] == ["evt-reopen"]
    assert resumed["earlier_unresolved_shared_events"] == [old_unresolved]

    shared_only = ContextReconstructor(reader, project_facts=project_facts).load(
        "issue-5", "cycle-2"
    )
    assert shared_only["earlier_unresolved_shared_events"] == [old_unresolved]


def test_checkpoint_remap_is_readable_from_a_fresh_clone(
    repo, tmp_path, shared, recovery, reader, publisher
):
    recovery.bind("issue-5", "cycle-1")
    git(repo, "checkout", "-qb", "feature")
    old_commit = commit_file(repo, "feature.py", "value = 1\n", "feature commit")
    checkpoint = publisher.create_checkpoint(
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
    publisher.remap_checkpoint(
        "issue-5",
        "cycle-1",
        checkpoint["event_id"],
        new_commit,
        "squash merge",
        "collaborator:a",
        event_id="evt-squash-remap",
    )
    assert reader.find_event("issue-5", checkpoint["event_id"])["commit"] == old_commit

    remote = tmp_path / "history.git"
    clone_b = tmp_path / "fresh-clone"
    subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(remote)], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(clone_b)], check=True)
    configure_user(clone_b)
    recovery_b = RecoveryLog(clone_b)
    reader_b = WorkEventReader(clone_b, shared)
    context = ContextReconstructor(reader_b, recovery=recovery_b).load(
        "issue-5", "cycle-1"
    )

    assert context["latest_checkpoint"]["event_id"] == "evt-pre-squash"
    assert context["latest_checkpoint"]["resolved_commit"] == new_commit
    assert context["shared_events_since_checkpoint"][0]["event_id"] == (
        "evt-squash-remap"
    )


def test_reader_ignores_cycle_mismatched_checkpoint_remap(
    repo, tmp_path, shared, recovery, publisher
):
    recovery.bind("issue-5", "cycle-1")
    git(repo, "checkout", "-qb", "feature")
    old_commit = commit_file(repo, "feature.py", "value = 1\n", "feature commit")
    checkpoint = publisher.create_checkpoint(
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
    foreign = prepare_event(
        {
            "event_id": "evt-foreign-remap",
            "kind": "checkpoint-remapped",
            "work": "issue-5",
            "cycle_id": "cycle-2",
            "producer": "agent:other",
            "created_at": "2026-08-07T00:00:00Z",
            "summary": "Remap recorded under a different cycle",
            "checkpoint_event_id": checkpoint["event_id"],
            "old_commit": old_commit,
            "new_commit": new_commit,
            "reason": "cross-cycle input must not resolve this checkpoint",
        }
    )
    shared.append_event("issue-5", foreign)

    remote = tmp_path / "history.git"
    clone_b = tmp_path / "fresh-clone"
    subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(remote)], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(clone_b)], check=True)
    configure_user(clone_b)
    reader_b = WorkEventReader(clone_b, shared)
    context = ContextReconstructor(reader_b, recovery=RecoveryLog(clone_b)).load(
        "issue-5", "cycle-1"
    )

    assert context["latest_checkpoint"] is None

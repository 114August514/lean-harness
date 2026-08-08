"""Tests for git_facts.py — structured Git fact reading.

Tests parser correctness, state classification, and edge cases.
"""

from __future__ import annotations

from pathlib import Path

from git_mcp.git_exec import GitRunner
from git_mcp.git_facts import (
    HeadState,
    OperationState,
    is_ancestor,
    read_commit,
    read_head,
    read_repository,
    read_status,
    read_worktrees,
)

from .conftest import run_git


class TestRepository:
    def test_read_repository(self, git: GitRunner, repo: Path):
        info = read_repository(git)
        assert info.worktree_root == str(repo)
        assert info.is_bare is False
        assert ".git" in info.git_dir

    def test_not_a_repo(self, tmp_path: Path):
        g = GitRunner(tmp_path)
        result = g.run(["rev-parse", "--is-inside-work-tree"], check=False)
        assert not result.ok


class TestHead:
    def test_branch_head(self, git: GitRunner):
        head = read_head(git)
        assert head.state == HeadState.BRANCH
        assert head.branch is not None
        assert head.commit is not None

    def test_detached_head(self, git: GitRunner, repo: Path):
        commit = git.run_text(["rev-parse", "HEAD"])
        run_git(["checkout", commit], repo)
        head = read_head(git)
        assert head.state == HeadState.DETACHED
        assert head.commit == commit
        assert head.branch is None

    def test_unborn_head(self, tmp_path: Path):
        r = tmp_path / "empty"
        r.mkdir()
        run_git(["init"], r)
        g = GitRunner(r)
        head = read_head(g)
        assert head.state == HeadState.UNBORN
        assert head.commit is None


class TestStatus:
    def test_clean(self, git: GitRunner):
        status = read_status(git)
        assert len(status.staged) == 0
        assert len(status.unstaged) == 0
        assert len(status.untracked) == 0
        assert status.operation == OperationState.NONE

    def test_staged(self, git: GitRunner, repo: Path):
        (repo / "new.txt").write_text("new\n")
        run_git(["add", "new.txt"], repo)
        status = read_status(git)
        assert len(status.staged) == 1
        assert status.staged[0].path == "new.txt"

    def test_unstaged(self, git: GitRunner, repo: Path):
        (repo / "file.txt").write_text("modified\n")
        status = read_status(git)
        assert len(status.unstaged) == 1
        assert status.unstaged[0].path == "file.txt"

    def test_untracked(self, git: GitRunner, repo: Path):
        (repo / "untracked.txt").write_text("untracked\n")
        status = read_status(git)
        assert len(status.untracked) == 1

    def test_ignored(self, git: GitRunner, repo: Path):
        (repo / ".gitignore").write_text("ignored.txt\n")
        run_git(["add", ".gitignore"], repo)
        run_git(["commit", "-m", "add gitignore"], repo)
        (repo / "ignored.txt").write_text("ignored\n")
        status = read_status(git, include_ignored=True)
        assert len(status.ignored) == 1
        assert status.ignored[0].path == "ignored.txt"

    def test_conflict(self, git: GitRunner, repo: Path):
        # Create a branch and make conflicting changes
        run_git(["checkout", "-b", "feature"], repo)
        (repo / "file.txt").write_text("feature\n")
        run_git(["commit", "-am", "feature change"], repo)
        run_git(["checkout", "-"], repo)
        (repo / "file.txt").write_text("main\n")
        run_git(["commit", "-am", "main change"], repo)
        run_git(["merge", "feature"], repo)

        status = read_status(git)
        assert len(status.conflicted) == 1
        assert status.conflicted[0].path == "file.txt"
        assert status.operation == OperationState.MERGE


class TestWorktrees:
    def test_single_worktree(self, git: GitRunner):
        wts = read_worktrees(git)
        assert len(wts) == 1
        assert wts[0].is_main

    def test_linked_worktree(self, git: GitRunner, repo: Path, tmp_path: Path):
        wt_path = tmp_path / "linked"
        run_git(["worktree", "add", str(wt_path)], repo)
        wts = read_worktrees(git)
        assert len(wts) == 2
        linked = [w for w in wts if not w.is_main]
        assert len(linked) == 1
        assert linked[0].path == str(wt_path)


class TestCommits:
    def test_read_head_commit(self, git: GitRunner):
        commit = read_commit(git, "HEAD")
        assert commit is not None
        assert commit.object_type == "commit"
        assert len(commit.parents) == 0  # initial commit

    def test_nonexistent(self, git: GitRunner):
        commit = read_commit(git, "0000000000000000000000000000000000000000")
        assert commit is None

    def test_ancestry(self, git: GitRunner, repo: Path):
        first = git.run_text(["rev-parse", "HEAD"])
        (repo / "second.txt").write_text("second\n")
        run_git(["add", "second.txt"], repo)
        run_git(["commit", "-m", "second"], repo)
        second = git.run_text(["rev-parse", "HEAD"])

        assert is_ancestor(git, first, second)
        assert not is_ancestor(git, second, first)

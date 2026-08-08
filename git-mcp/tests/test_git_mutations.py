"""Behavior tests for bounded Git mutations and uncertain outcomes."""

from __future__ import annotations

from pathlib import Path

from git_mcp import git_mutations
from git_mcp.git_exec import GitResult, GitRunner
from git_mcp.git_facts import read_head, read_worktrees


def _report_timeout_after(
    monkeypatch, git: GitRunner, command_prefix: list[str]
) -> None:
    original_run = git.run
    reported = False

    def run_then_report_timeout(args, **kwargs):
        nonlocal reported
        result = original_run(args, **kwargs)
        if not reported and args[: len(command_prefix)] == command_prefix:
            reported = True
            return GitResult(
                returncode=-1,
                stdout=b"",
                stderr=b"simulated timeout after command execution",
                timed_out=True,
            )
        return result

    monkeypatch.setattr(git, "run", run_then_report_timeout)


def _report_timeout_before(
    monkeypatch, git: GitRunner, command_prefix: list[str]
) -> None:
    original_run = git.run

    def report_timeout(args, **kwargs):
        if args[: len(command_prefix)] == command_prefix:
            return GitResult(
                returncode=-1,
                stdout=b"",
                stderr=b"simulated timeout before command execution",
                timed_out=True,
            )
        return original_run(args, **kwargs)

    monkeypatch.setattr(git, "run", report_timeout)


class TestTimeoutObservation:
    def test_branch_create_timeout_returns_observed_ref(
        self, git: GitRunner, monkeypatch
    ):
        _report_timeout_after(monkeypatch, git, ["branch", "--"])

        result = git_mutations.branch_create(git, "timeout-branch")

        assert result["created"] == "timeout-branch"
        assert result["tip"] == git.run_text(["rev-parse", "refs/heads/timeout-branch"])
        assert "timeout" in result["command_error"]

    def test_branch_delete_timeout_returns_observed_absence(
        self, git: GitRunner, monkeypatch
    ):
        created = git_mutations.branch_create(git, "timeout-branch")
        assert created["created"] == "timeout-branch"
        _report_timeout_after(monkeypatch, git, ["update-ref", "-d"])

        result = git_mutations.branch_delete(git, "timeout-branch")

        assert result["deleted"] == "timeout-branch"
        assert result["verified_gone"] is True
        assert "timeout" in result["command_error"]
        assert not git.run(
            ["show-ref", "--verify", "--quiet", "refs/heads/timeout-branch"],
            check=False,
        ).ok

    def test_stage_timeout_after_mutation_returns_error_and_observed_index(
        self, repo: Path, git: GitRunner, monkeypatch
    ):
        (repo / "timeout.txt").write_text("timeout\n")
        _report_timeout_after(monkeypatch, git, ["add", "--"])

        result = git_mutations.stage(git, ["timeout.txt"])

        assert "timeout" in result["error"]
        assert result["status"]["staged"] == [
            {"path": "timeout.txt", "index_status": "A"}
        ]
        assert result["status"]["unstaged"] == []

    def test_stage_timeout_before_mutation_returns_error_and_observed_worktree(
        self, repo: Path, git: GitRunner, monkeypatch
    ):
        (repo / "not-staged.txt").write_text("not staged\n")
        _report_timeout_before(monkeypatch, git, ["add", "--"])

        result = git_mutations.stage(git, ["not-staged.txt"])

        assert "timeout" in result["error"]
        assert result["status"]["staged"] == []
        assert result["status"]["untracked"] == [{"path": "not-staged.txt"}]

    def test_commit_timeout_returns_observed_commit(
        self, repo: Path, git: GitRunner, monkeypatch
    ):
        (repo / "timeout.txt").write_text("timeout\n")
        staged = git_mutations.stage(git, ["timeout.txt"])
        assert staged["staged"] == [{"path": "timeout.txt", "index_status": "A"}]
        before = read_head(git).commit
        _report_timeout_after(monkeypatch, git, ["commit", "-m"])

        result = git_mutations.commit(git, "timeout commit")

        assert result["commit"] != before
        assert read_head(git).commit == result["commit"]
        assert result["staged"] == []
        assert "timeout" in result["command_error"]

    def test_worktree_create_timeout_returns_observed_registration(
        self, git: GitRunner, tmp_path: Path, monkeypatch
    ):
        target = tmp_path / "timeout-worktree"
        _report_timeout_after(monkeypatch, git, ["worktree", "add"])

        result = git_mutations.worktree_create(
            git, str(target), branch="timeout-worktree"
        )

        assert result["created"] == str(target)
        assert result["registration"]["path"] == str(target)
        assert result["path_exists"] is True
        assert "timeout" in result["command_error"]
        assert any(Path(worktree.path) == target for worktree in read_worktrees(git))

        removed = git_mutations.worktree_remove(git, str(target))
        assert removed["removed"] == str(target)

    def test_worktree_remove_timeout_returns_observed_absence(
        self, git: GitRunner, tmp_path: Path, monkeypatch
    ):
        target = tmp_path / "timeout-worktree"
        created = git_mutations.worktree_create(
            git, str(target), branch="timeout-worktree"
        )
        assert created["created"] == str(target)
        _report_timeout_after(monkeypatch, git, ["worktree", "remove"])

        result = git_mutations.worktree_remove(git, str(target))

        assert result["removed"] == str(target)
        assert result["registration"] is None
        assert result["path_exists"] is False
        assert "timeout" in result["command_error"]
        assert not target.exists()
        assert all(Path(worktree.path) != target for worktree in read_worktrees(git))


class TestWorktreePath:
    def test_create_rejects_relative_path_without_side_effects(
        self, git: GitRunner, tmp_path: Path
    ):
        target = tmp_path / "relative-create"

        result = git_mutations.worktree_create(git, "../relative-create")

        assert "must be absolute" in result["error"]
        assert not target.exists()
        assert all(Path(worktree.path) != target for worktree in read_worktrees(git))

    def test_remove_rejects_relative_path_without_side_effects(
        self, git: GitRunner, tmp_path: Path
    ):
        target = tmp_path / "relative-remove"
        created = git_mutations.worktree_create(
            git, str(target), branch="relative-remove"
        )
        assert created["created"] == str(target)

        result = git_mutations.worktree_remove(git, "../relative-remove")

        assert "must be absolute" in result["error"]
        assert target.exists()
        assert any(Path(worktree.path) == target for worktree in read_worktrees(git))

        removed = git_mutations.worktree_remove(git, str(target))
        assert removed["removed"] == str(target)

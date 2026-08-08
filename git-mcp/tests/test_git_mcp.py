"""Tests for Local Git MCP capability.

Uses real Git repositories (tmp_path fixtures) to verify
Git Contract semantics. No fake Git substitutes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

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


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(cwd),
            "LC_ALL": "C",
            "GIT_TERMINAL_PROMPT": "0",
        },
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """Create a minimal Git repository with one commit."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(["init"], r)
    _git(["config", "user.name", "Test"], r)
    _git(["config", "user.email", "test@test"], r)
    (r / "file.txt").write_text("hello\n")
    _git(["add", "file.txt"], r)
    _git(["commit", "-m", "initial"], r)
    return r


@pytest.fixture()
def git(repo: Path) -> GitRunner:
    return GitRunner(repo)


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
        _git(["checkout", commit], repo)
        head = read_head(git)
        assert head.state == HeadState.DETACHED
        assert head.commit == commit
        assert head.branch is None

    def test_unborn_head(self, tmp_path: Path):
        r = tmp_path / "empty"
        r.mkdir()
        _git(["init"], r)
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
        _git(["add", "new.txt"], repo)
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
        _git(["add", ".gitignore"], repo)
        _git(["commit", "-m", "add gitignore"], repo)
        (repo / "ignored.txt").write_text("ignored\n")
        status = read_status(git, include_ignored=True)
        assert len(status.ignored) == 1
        assert status.ignored[0].path == "ignored.txt"

    def test_conflict(self, git: GitRunner, repo: Path):
        # Create a branch and make conflicting changes
        _git(["checkout", "-b", "feature"], repo)
        (repo / "file.txt").write_text("feature\n")
        _git(["commit", "-am", "feature change"], repo)
        _git(["checkout", "-"], repo)
        (repo / "file.txt").write_text("main\n")
        _git(["commit", "-am", "main change"], repo)
        _git(["merge", "feature"], repo)

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
        _git(["worktree", "add", str(wt_path)], repo)
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
        _git(["add", "second.txt"], repo)
        _git(["commit", "-m", "second"], repo)
        second = git.run_text(["rev-parse", "HEAD"])

        assert is_ancestor(git, first, second)
        assert not is_ancestor(git, second, first)


class TestServer:
    """Test MCP server tool calls through the server object directly."""

    def _make_server(self, repo_path: Path):
        from git_mcp.server import create_server

        return create_server(str(repo_path))

    async def _call(self, mcp, tool: str, args: dict | None = None) -> dict:
        result = await mcp.call_tool(tool, args or {})
        return result.structured_content

    @pytest.mark.asyncio()
    async def test_read_context(self, repo: Path):
        mcp = self._make_server(repo)
        data = await self._call(mcp, "git_read_context")
        assert data["head"]["state"] == "branch"
        assert data["head"]["branch"] is not None
        assert data["repository"]["worktree_root"] == str(repo)

    @pytest.mark.asyncio()
    async def test_read_context_redacts_credentials(self, repo: Path):
        """Remote URLs with embedded credentials are redacted in Agent output."""
        mcp = self._make_server(repo)
        _git(
            ["remote", "add", "origin", "https://user:secret123@example.com/repo.git"],
            repo,
        )
        data = await self._call(mcp, "git_read_context")
        remotes = data["repository"]["remotes"]
        assert "origin" in remotes
        assert "secret123" not in remotes["origin"]["fetch_url"]
        assert "user" not in remotes["origin"]["fetch_url"]
        assert "example.com" in remotes["origin"]["fetch_url"]

    @pytest.mark.asyncio()
    async def test_read_status_clean(self, repo: Path):
        mcp = self._make_server(repo)
        data = await self._call(mcp, "git_read_status")
        assert data["staged"] == []
        assert data["unstaged"] == []
        assert data["untracked"] == []
        assert data["operation"] == "none"

    @pytest.mark.asyncio()
    async def test_branch_create_and_delete(self, repo: Path):
        mcp = self._make_server(repo)

        # Create
        data = await self._call(
            mcp, "git_branch_create", {"name": "test-branch", "start_point": "HEAD"}
        )
        assert data["created"] == "test-branch"

        # Delete with correct expected_tip
        tip = data["tip"]
        data = await self._call(
            mcp, "git_branch_delete", {"name": "test-branch", "expected_tip": tip}
        )
        assert data["deleted"] == "test-branch"
        assert data["verified_gone"] is True

    @pytest.mark.asyncio()
    async def test_branch_delete_stale_tip(self, repo: Path):
        mcp = self._make_server(repo)
        await self._call(mcp, "git_branch_create", {"name": "stale-test"})

        data = await self._call(
            mcp,
            "git_branch_delete",
            {"name": "stale-test", "expected_tip": "0000000000000000000000000000000000000000"},
        )
        assert "stale precondition" in data["error"]

        # Cleanup
        await self._call(mcp, "git_branch_delete", {"name": "stale-test"})

    @pytest.mark.asyncio()
    async def test_branch_delete_checked_out(self, repo: Path, git: GitRunner):
        mcp = self._make_server(repo)
        head = read_head(git)
        assert head.branch is not None
        data = await self._call(
            mcp, "git_branch_delete", {"name": head.branch}
        )
        assert "checked out" in data["error"]

    @pytest.mark.asyncio()
    async def test_stage_and_commit(self, repo: Path):
        mcp = self._make_server(repo)
        (repo / "stage-me.txt").write_text("staged\n")

        data = await self._call(mcp, "git_stage", {"paths": ["stage-me.txt"]})
        assert len(data["staged"]) == 1

        data = await self._call(mcp, "git_commit", {"message": "add stage-me"})
        assert data["commit"] is not None
        assert data["state"] == "branch"

    @pytest.mark.asyncio()
    async def test_stage_path_with_spaces(self, repo: Path):
        mcp = self._make_server(repo)
        (repo / "my file.txt").write_text("spaced\n")

        data = await self._call(mcp, "git_stage", {"paths": ["my file.txt"]})
        assert len(data["staged"]) == 1
        assert data["staged"][0]["path"] == "my file.txt"

    @pytest.mark.asyncio()
    async def test_branch_delete_with_retained_refs(self, repo: Path, git: GitRunner):
        mcp = self._make_server(repo)
        default_branch = read_head(git).branch
        assert default_branch is not None

        # Create a branch at HEAD (reachable from default branch)
        await self._call(mcp, "git_branch_create", {"name": "safe-delete"})
        tip = git.run_text(["rev-parse", "refs/heads/safe-delete"])

        # Delete with retained_refs pointing at default branch (which contains tip)
        data = await self._call(
            mcp,
            "git_branch_delete",
            {
                "name": "safe-delete",
                "expected_tip": tip,
                "retained_refs": [default_branch],
            },
        )
        assert data["deleted"] == "safe-delete"
        assert data["verified_gone"] is True

    @pytest.mark.asyncio()
    async def test_branch_delete_unreachable_from_retained(self, repo: Path, git: GitRunner):
        mcp = self._make_server(repo)
        default_branch = read_head(git).branch
        assert default_branch is not None

        # Create a branch and add a commit not on default branch
        await self._call(mcp, "git_branch_create", {"name": "diverged"})
        _git(["checkout", "diverged"], repo)
        (repo / "diverged.txt").write_text("diverged\n")
        await self._call(mcp, "git_stage", {"paths": ["diverged.txt"]})
        await self._call(mcp, "git_commit", {"message": "diverged commit"})
        tip = git.run_text(["rev-parse", "refs/heads/diverged"])

        # Switch back
        _git(["checkout", default_branch], repo)

        # Try to delete with retained_refs=default_branch — diverged tip is NOT reachable
        data = await self._call(
            mcp,
            "git_branch_delete",
            {
                "name": "diverged",
                "expected_tip": tip,
                "retained_refs": [default_branch],
            },
        )
        assert "not reachable" in data["error"]

        # Cleanup
        await self._call(mcp, "git_branch_delete", {"name": "diverged"})

    @pytest.mark.asyncio()
    async def test_commit_empty_staging(self, repo: Path):
        mcp = self._make_server(repo)
        data = await self._call(mcp, "git_commit", {"message": "empty"})
        assert "no staged changes" in data["error"]

    @pytest.mark.asyncio()
    async def test_commit_stale_head(self, repo: Path):
        mcp = self._make_server(repo)
        (repo / "file.txt").write_text("changed\n")
        await self._call(mcp, "git_stage", {"paths": ["file.txt"]})

        data = await self._call(
            mcp,
            "git_commit",
            {
                "message": "test",
                "expected_head": "0000000000000000000000000000000000000000",
            },
        )
        assert "stale precondition" in data["error"]

    @pytest.mark.asyncio()
    async def test_worktree_create_and_remove(self, repo: Path, tmp_path: Path):
        mcp = self._make_server(repo)
        wt_path = str(tmp_path / "new-worktree")

        data = await self._call(
            mcp, "git_worktree_create", {"path": wt_path, "branch": "wt-branch"}
        )
        assert data["created"] == wt_path

        data = await self._call(mcp, "git_worktree_remove", {"path": wt_path})
        assert data["removed"] == wt_path

    @pytest.mark.asyncio()
    async def test_worktree_remove_dirty(self, repo: Path, tmp_path: Path):
        mcp = self._make_server(repo)
        wt_path = str(tmp_path / "dirty-worktree")

        await self._call(
            mcp, "git_worktree_create", {"path": wt_path, "branch": "dirty-branch"}
        )
        # Make the worktree dirty
        (Path(wt_path) / "dirty.txt").write_text("untracked\n")

        data = await self._call(mcp, "git_worktree_remove", {"path": wt_path})
        assert "loss surface not empty" in data["error"]
        assert "untracked" in data["loss_surface"]

        # Cleanup
        (Path(wt_path) / "dirty.txt").unlink()
        await self._call(mcp, "git_worktree_remove", {"path": wt_path})

    @pytest.mark.asyncio()
    async def test_merge_conflict(self, repo: Path, git: GitRunner):
        mcp = self._make_server(repo)
        default_branch = read_head(git).branch
        assert default_branch is not None

        # Create conflicting branches
        await self._call(mcp, "git_branch_create", {"name": "conflict-branch"})
        (repo / "file.txt").write_text("main version\n")
        await self._call(mcp, "git_stage", {"paths": ["file.txt"]})
        await self._call(mcp, "git_commit", {"message": "main change"})

        # Switch to conflict-branch and make conflicting change
        subprocess.run(
            ["git", "checkout", "conflict-branch"],
            cwd=repo,
            capture_output=True,
        )
        (repo / "file.txt").write_text("branch version\n")
        await self._call(mcp, "git_stage", {"paths": ["file.txt"]})
        await self._call(mcp, "git_commit", {"message": "branch change"})

        # Switch back and try to merge
        subprocess.run(
            ["git", "checkout", default_branch],
            cwd=repo,
            capture_output=True,
        )
        data = await self._call(
            mcp, "git_integrate", {"operation": "merge", "source": "conflict-branch"}
        )
        assert data["success"] is False
        assert "conflicted_files" in data
        assert "file.txt" in data["conflicted_files"]
        assert data.get("in_progress") == "merge"

        # Abort
        data = await self._call(mcp, "git_integrate_continue", {"action": "abort"})
        assert data["success"] is True
        assert data["remaining_operation"] == "none"

    @pytest.mark.asyncio()
    async def test_read_refs(self, repo: Path):
        mcp = self._make_server(repo)
        data = await self._call(mcp, "git_read_refs")
        assert len(data["refs"]) > 0
        assert len(data["worktrees"]) == 1
        assert data["worktrees"][0]["is_main"] is True

    @pytest.mark.asyncio()
    async def test_read_commits(self, repo: Path):
        mcp = self._make_server(repo)
        data = await self._call(mcp, "git_read_commits", {"revision": "HEAD"})
        assert data["commit"] is not None
        assert data["commit"]["object_type"] == "commit"

    @pytest.mark.asyncio()
    async def test_read_diff_bounded(self, repo: Path):
        mcp = self._make_server(repo)
        # Create a large diff
        lines = [f"line {i}\n" for i in range(1000)]
        (repo / "file.txt").write_text("".join(lines))

        data = await self._call(mcp, "git_read_diff", {"max_lines": 10})
        assert data["truncated"] is True
        assert data["total_lines"] > 10

    @pytest.mark.asyncio()
    async def test_merge_ignored_collision(self, repo: Path, git: GitRunner):
        """Merge refuses when ignored local file would be overwritten."""
        mcp = self._make_server(repo)
        default_branch = read_head(git).branch
        assert default_branch is not None

        # Create a branch that adds a file
        await self._call(mcp, "git_branch_create", {"name": "adds-file"})
        _git(["checkout", "adds-file"], repo)
        (repo / "collision.txt").write_text("from branch\n")
        await self._call(mcp, "git_stage", {"paths": ["collision.txt"]})
        await self._call(mcp, "git_commit", {"message": "add collision.txt"})

        # Go back, ignore the file, create local version
        _git(["checkout", default_branch], repo)
        (repo / ".gitignore").write_text("collision.txt\n")
        await self._call(mcp, "git_stage", {"paths": [".gitignore"]})
        await self._call(mcp, "git_commit", {"message": "ignore collision.txt"})
        (repo / "collision.txt").write_text("local ignored content\n")

        # Merge should refuse due to ignored collision
        data = await self._call(
            mcp, "git_integrate", {"operation": "merge", "source": "adds-file"}
        )
        assert "collision" in data["error"].lower() or "untracked" in data["error"].lower()
        assert "colliding_paths" in data or "collision.txt" in str(data)

    @pytest.mark.asyncio()
    async def test_option_injection_rejected(self, repo: Path):
        """Revisions starting with '-' are rejected by Git's --end-of-options."""
        mcp = self._make_server(repo)
        # Try to inject --output option via base parameter
        data = await self._call(
            mcp, "git_read_diff", {"base": "--output=/tmp/evil.txt"}
        )
        assert "error" in data
        # Git should reject this as invalid option/revision

    @pytest.mark.asyncio()
    async def test_both_added_conflict(self, repo: Path, git: GitRunner):
        """AA (both added) conflict is correctly classified."""
        mcp = self._make_server(repo)
        default_branch = read_head(git).branch
        assert default_branch is not None

        # Create a branch that adds a file
        await self._call(mcp, "git_branch_create", {"name": "branch-a"})
        _git(["checkout", "branch-a"], repo)
        (repo / "new.txt").write_text("from branch-a\n")
        await self._call(mcp, "git_stage", {"paths": ["new.txt"]})
        await self._call(mcp, "git_commit", {"message": "branch-a adds new.txt"})

        # Go back and add same file with different content
        _git(["checkout", default_branch], repo)
        (repo / "new.txt").write_text("from main\n")
        await self._call(mcp, "git_stage", {"paths": ["new.txt"]})
        await self._call(mcp, "git_commit", {"message": "main adds new.txt"})

        # Merge should produce AA conflict
        data = await self._call(
            mcp, "git_integrate", {"operation": "merge", "source": "branch-a"}
        )
        assert data["success"] is False
        assert "conflicted_files" in data
        assert "new.txt" in data["conflicted_files"]

"""Tests for MCP server tool surface.

Tests tool behavior, mutation semantics, and safety checks
through the MCP server interface.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from git_mcp.git_exec import GitRunner
from git_mcp.git_facts import read_head

from .conftest import run_git


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
        run_git(
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
        run_git(["checkout", "diverged"], repo)
        (repo / "diverged.txt").write_text("diverged\n")
        await self._call(mcp, "git_stage", {"paths": ["diverged.txt"]})
        await self._call(mcp, "git_commit", {"message": "diverged commit"})
        tip = git.run_text(["rev-parse", "refs/heads/diverged"])

        # Switch back
        run_git(["checkout", default_branch], repo)

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
    async def test_merge_ignored_file_overwritten(self, repo: Path, git: GitRunner):
        """Git merge silently overwrites ignored files (documented behavior)."""
        mcp = self._make_server(repo)
        default_branch = read_head(git).branch
        assert default_branch is not None

        # Create a branch that adds a file
        await self._call(mcp, "git_branch_create", {"name": "adds-file"})
        run_git(["checkout", "adds-file"], repo)
        (repo / "collision.txt").write_text("from branch\n")
        await self._call(mcp, "git_stage", {"paths": ["collision.txt"]})
        await self._call(mcp, "git_commit", {"message": "add collision.txt"})

        # Go back, ignore the file, create local version
        run_git(["checkout", default_branch], repo)
        (repo / ".gitignore").write_text("collision.txt\n")
        await self._call(mcp, "git_stage", {"paths": [".gitignore"]})
        await self._call(mcp, "git_commit", {"message": "ignore collision.txt"})
        (repo / "collision.txt").write_text("local ignored content\n")

        # Merge succeeds; ignored file is silently overwritten (Git native behavior)
        data = await self._call(
            mcp, "git_integrate", {"operation": "merge", "source": "adds-file"}
        )
        assert data["success"] is True
        # The ignored local file was overwritten by the merge
        assert (repo / "collision.txt").read_text() == "from branch\n"

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
        run_git(["checkout", "branch-a"], repo)
        (repo / "new.txt").write_text("from branch-a\n")
        await self._call(mcp, "git_stage", {"paths": ["new.txt"]})
        await self._call(mcp, "git_commit", {"message": "branch-a adds new.txt"})

        # Go back and add same file with different content
        run_git(["checkout", default_branch], repo)
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

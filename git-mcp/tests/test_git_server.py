"""Tests for MCP server tool surface.

Tests tool behavior, mutation semantics, and safety checks
through the MCP server interface.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from git_mcp import git_mutations
from git_mcp.git_exec import GitResult, GitRunner
from git_mcp.git_facts import read_head, read_worktrees

from .conftest import run_git


class TestServer:
    """Test MCP server tool calls through the server object directly."""

    def _make_server(self, repo_path: Path):
        from git_mcp.server import create_server

        return create_server(str(repo_path))

    async def _call(self, mcp, tool: str, args: dict | None = None) -> dict:
        result = await mcp.call_tool(tool, args or {})
        return result.structured_content

    def _report_timeout_after(
        self, monkeypatch, git: GitRunner, command_prefix: list[str]
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
        self, monkeypatch, git: GitRunner, command_prefix: list[str]
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

    def test_branch_timeouts_reobserve_refs(
        self, repo: Path, git: GitRunner, monkeypatch
    ):
        with monkeypatch.context() as patch:
            self._report_timeout_after(patch, git, ["branch", "--"])
            created = git_mutations.branch_create(git, "timeout-branch")

        assert created["created"] == "timeout-branch"
        assert created["tip"] == git.run_text(
            ["rev-parse", "refs/heads/timeout-branch"]
        )
        assert "timeout" in created["command_error"]

        with monkeypatch.context() as patch:
            self._report_timeout_after(patch, git, ["update-ref", "-d"])
            deleted = git_mutations.branch_delete(git, "timeout-branch")

        assert deleted["deleted"] == "timeout-branch"
        assert deleted["verified_gone"] is True
        assert "timeout" in deleted["command_error"]

    def test_stage_and_commit_timeouts_reobserve_index_and_head(
        self, repo: Path, git: GitRunner, monkeypatch
    ):
        (repo / "timeout.txt").write_text("timeout\n")
        with monkeypatch.context() as patch:
            self._report_timeout_after(patch, git, ["add", "--"])
            staged = git_mutations.stage(git, ["timeout.txt"])

        assert staged["status"]["staged"] == [
            {"path": "timeout.txt", "index_status": "A"}
        ]
        assert "timeout" in staged["error"]

        before = read_head(git).commit
        with monkeypatch.context() as patch:
            self._report_timeout_after(patch, git, ["commit", "-m"])
            committed = git_mutations.commit(git, "timeout commit")

        assert committed["commit"] != before
        assert committed["staged"] == []
        assert "timeout" in committed["command_error"]

    def test_stage_timeout_before_mutation_remains_uncertain(
        self, repo: Path, git: GitRunner, monkeypatch
    ):
        (repo / "not-staged.txt").write_text("not staged\n")
        self._report_timeout_before(monkeypatch, git, ["add", "--"])

        result = git_mutations.stage(git, ["not-staged.txt"])

        assert "timeout" in result["error"]
        assert result["status"]["staged"] == []
        assert result["status"]["untracked"] == [{"path": "not-staged.txt"}]

    def test_worktree_timeouts_reobserve_registration_and_path(
        self, repo: Path, git: GitRunner, tmp_path: Path, monkeypatch
    ):
        wt_path = tmp_path / "timeout-worktree"
        with monkeypatch.context() as patch:
            self._report_timeout_after(patch, git, ["worktree", "add"])
            created = git_mutations.worktree_create(
                git, str(wt_path), branch="timeout-worktree"
            )

        assert created["created"] == str(wt_path)
        assert created["registration"]["path"] == str(wt_path)
        assert created["path_exists"] is True
        assert "timeout" in created["command_error"]

        with monkeypatch.context() as patch:
            self._report_timeout_after(patch, git, ["worktree", "remove"])
            removed = git_mutations.worktree_remove(git, str(wt_path))

        assert removed["removed"] == str(wt_path)
        assert removed["registration"] is None
        assert removed["path_exists"] is False
        assert "timeout" in removed["command_error"]

    def test_worktree_create_rejects_relative_path(
        self, repo: Path, git: GitRunner, tmp_path: Path
    ):
        target = tmp_path / "relative-create"

        result = git_mutations.worktree_create(git, "../relative-create")

        assert "must be absolute" in result["error"]
        assert not target.exists()
        assert all(Path(worktree.path) != target for worktree in read_worktrees(git))

    def test_worktree_remove_rejects_relative_path(
        self, repo: Path, git: GitRunner, tmp_path: Path
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
            {
                "name": "stale-test",
                "expected_tip": "0000000000000000000000000000000000000000",
            },
        )
        assert "stale precondition" in data["error"]

        # Cleanup
        await self._call(mcp, "git_branch_delete", {"name": "stale-test"})

    @pytest.mark.asyncio()
    async def test_branch_delete_checked_out(self, repo: Path, git: GitRunner):
        mcp = self._make_server(repo)
        head = read_head(git)
        assert head.branch is not None
        data = await self._call(mcp, "git_branch_delete", {"name": head.branch})
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
    async def test_branch_delete_unreachable_from_retained(
        self, repo: Path, git: GitRunner
    ):
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
    async def test_read_commits_object_kinds(self, repo: Path):
        """非 commit 对象返回其真实类型；无法解析的 revision 返回错误。"""
        mcp = self._make_server(repo)
        # HEAD^{tree} 存在但非 commit → 报告真实类型
        data = await self._call(mcp, "git_read_commits", {"revision": "HEAD^{tree}"})
        assert data["commit"] is None
        assert data["object_type"] == "tree"
        # 无法解析的 revision → 报错
        data = await self._call(
            mcp, "git_read_commits", {"revision": "nonexistent-ref-xyz"}
        )
        assert data["commit"] is None
        assert "error" in data

    @pytest.mark.asyncio()
    async def test_read_commits_ancestry(self, repo: Path):
        """ancestry 真/假都可判定；无法解析的 revision 报错而非判为假。"""
        mcp = self._make_server(repo)
        run_git(["checkout", "-q", "-b", "anc-test"], repo)
        (repo / "anc.txt").write_text("a\n")
        run_git(["add", "anc.txt"], repo)
        run_git(["commit", "-qm", "anc"], repo)
        c1 = run_git(["rev-parse", "HEAD"], repo).stdout.strip()
        (repo / "anc.txt").write_text("b\n")
        run_git(["commit", "-qam", "anc2"], repo)
        c2 = run_git(["rev-parse", "HEAD"], repo).stdout.strip()

        # c1 是 c2 的祖先；c2 不是 c1 的祖先
        data = await self._call(
            mcp, "git_read_commits", {"ancestor": c1, "descendant": c2}
        )
        assert data["is_ancestor"] is True
        data = await self._call(
            mcp, "git_read_commits", {"ancestor": c2, "descendant": c1}
        )
        assert data["is_ancestor"] is False
        # 无法解析的 revision → 报错而非判为假
        data = await self._call(
            mcp, "git_read_commits", {"ancestor": "bad-rev", "descendant": c1}
        )
        assert data["is_ancestor"] is None
        assert "ancestry_error" in data

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
    async def test_read_diff_cached(self, repo: Path):
        """cached diff 只包含已暂存的改动，不含工作区未暂存的改动。"""
        mcp = self._make_server(repo)
        (repo / "file.txt").write_text("staged change\n")
        run_git(["add", "file.txt"], repo)
        (repo / "file.txt").write_text("staged change\nunstaged\n")  # 工作区再改

        data = await self._call(mcp, "git_read_diff", {"cached": True})
        assert "+staged change" in data["diff"]
        assert "+unstaged" not in data["diff"]

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
    async def test_diff_base_is_treated_as_revision_not_option(
        self, repo: Path, tmp_path: Path
    ):
        """base 以 '-' 开头时被当作 revision 解析并报错，不被当作 git option 执行。"""
        mcp = self._make_server(repo)
        target = tmp_path / "evil.txt"
        data = await self._call(mcp, "git_read_diff", {"base": f"--output={target}"})
        assert "error" in data
        assert not target.exists()

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

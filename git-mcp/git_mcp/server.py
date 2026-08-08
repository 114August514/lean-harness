"""MCP tool surface for Local Git capability.

Thin wiring layer: binds MCP tool schemas to git_facts / git_mutations.
No Git semantics here — only MCP registration and SDK-native structured output.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from . import git_facts, git_mutations
from .repository import bind_repository


def _redact_url(url: str) -> str:
    """Remove embedded credentials from a URL for Agent-facing output."""
    if not url:
        return url
    try:
        parts = urlsplit(url)
        if parts.password or parts.username:
            host = parts.hostname or ""
            if parts.port:
                host = f"{host}:{parts.port}"
            return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))
        return url
    except ValueError:
        return url


def create_server(repo_path: str) -> MCPServer:
    """Create and configure the MCP server for a repository."""
    ctx = bind_repository(repo_path)
    git = ctx.runner

    mcp = MCPServer(
        "lean-harness-git",
        version="0.1.0",
        instructions=(
            "Local Git capability for Lean Harness. "
            "Provides structured Git facts and bounded mutations "
            "confined to a single repository."
        ),
    )

    _register_read_tools(mcp, git)
    _register_mutation_tools(mcp, git)

    return mcp


def _head_to_dict(head) -> dict[str, Any]:
    return {
        "state": head.state.value,
        "branch": head.branch,
        "commit": head.commit,
        "upstream": head.upstream,
    }


def _entry_to_dict(e) -> dict[str, Any]:
    return {
        "path": e.path,
        "index_status": e.index_status,
        "worktree_status": e.worktree_status,
        "original_path": e.original_path,
    }


def _commit_to_dict(c) -> dict[str, Any]:
    return {
        "object_id": c.object_id,
        "object_type": c.object_type,
        "parents": c.parents,
        "tree": c.tree,
    }


def _diff_to_dict(d) -> dict[str, Any]:
    result: dict[str, Any] = {
        "diff": d.diff,
        "truncated": d.truncated,
        "total_lines": d.total_lines,
    }
    if d.error:
        result["error"] = d.error
    return result


def _status_to_dict(status) -> dict[str, Any]:
    return {
        "staged": [_entry_to_dict(e) for e in status.staged],
        "unstaged": [_entry_to_dict(e) for e in status.unstaged],
        "untracked": [{"path": e.path} for e in status.untracked],
        "ignored": [{"path": e.path} for e in status.ignored],
        "conflicted": [_entry_to_dict(e) for e in status.conflicted],
        "operation": status.operation.value,
    }


def _register_read_tools(mcp: MCPServer, git) -> None:

    @mcp.tool(
        description="Read repository identity, layout, and current context "
        "(HEAD state, branch, operation in progress).",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    def git_read_context() -> dict[str, Any]:
        repo = git_facts.read_repository(git)
        head = git_facts.read_head(git)
        status = git_facts.read_status(git)
        return {
            "repository": {
                "worktree_root": repo.worktree_root,
                "git_dir": repo.git_dir,
                "common_dir": repo.common_dir,
                "is_bare": repo.is_bare,
                "remotes": {
                    name: {
                        "fetch_url": _redact_url(urls["fetch_url"]),
                        "push_url": _redact_url(urls["push_url"]),
                    }
                    for name, urls in repo.remotes.items()
                },
            },
            "head": _head_to_dict(head),
            "operation": status.operation.value,
        }

    @mcp.tool(
        description="Read working tree and index status: staged, unstaged, "
        "untracked, ignored, conflicted files. Optionally include ignored files.",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    def git_read_status(include_ignored: bool = False) -> dict[str, Any]:
        status = git_facts.read_status(git, include_ignored=include_ignored)
        return _status_to_dict(status)

    @mcp.tool(
        description="Read all refs (branches, tags, remotes) and registered worktrees.",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    def git_read_refs() -> dict[str, Any]:
        refs = git_facts.read_refs(git)
        worktrees = git_facts.read_worktrees(git)
        return {
            "refs": [
                {
                    "name": r.name,
                    "object_id": r.object_id,
                    "object_type": r.object_type,
                    "symbolic_target": r.symbolic_target,
                    "upstream": r.upstream,
                }
                for r in refs
            ],
            "worktrees": [
                {
                    "path": w.path,
                    "head": w.head,
                    "branch": w.branch,
                    "is_main": w.is_main,
                    "is_locked": w.is_locked,
                    "is_prunable": w.is_prunable,
                }
                for w in worktrees
            ],
        }

    @mcp.tool(
        description="Read diff with bounded output. Returns diff text, "
        "truncation indicator, and total line count.",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    def git_read_diff(
        cached: bool = False,
        base: str = "",
        target: str = "",
        paths: list[str] | None = None,
        max_lines: int = 500,
    ) -> dict[str, Any]:
        diff = git_facts.read_diff(
            git,
            cached=cached,
            base=base or None,
            target=target or None,
            paths=paths or None,
            max_lines=max_lines,
        )
        return _diff_to_dict(diff)

    @mcp.tool(
        description="Read commit facts: existence, type, parents. "
        "Check ancestry/reachability between two commits.",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    def git_read_commits(
        revision: str = "",
        ancestor: str = "",
        descendant: str = "",
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if revision:
            probe = git_facts.probe_commit(git, revision)
            result["commit"] = _commit_to_dict(probe.commit) if probe.commit else None
            if probe.error:
                result["error"] = probe.error
            elif probe.object_type:
                # Object exists but is not a commit — legitimate absent.
                result["object_type"] = probe.object_type
        if ancestor and descendant:
            anc = git_facts.check_ancestor(git, ancestor, descendant)
            result["is_ancestor"] = anc.result
            if anc.error:
                result["ancestry_error"] = anc.error
        return result


def _register_mutation_tools(mcp: MCPServer, git) -> None:

    @mcp.tool(
        description="Create a new branch at an explicit start point. "
        "Refuses if the branch already exists.",
        annotations=ToolAnnotations(destructive_hint=False),
    )
    def git_branch_create(name: str, start_point: str = "HEAD") -> dict[str, Any]:
        return git_mutations.branch_create(git, name, start_point)

    @mcp.tool(
        description="Delete a local branch with safety checks. "
        "Requires expected_tip to match current tip. "
        "Optionally verify reachability from retained refs.",
        annotations=ToolAnnotations(destructive_hint=True),
    )
    def git_branch_delete(
        name: str,
        expected_tip: str = "",
        retained_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        return git_mutations.branch_delete(git, name, expected_tip, retained_refs)

    @mcp.tool(
        description="Create a linked worktree at an explicit path with an "
        "explicit branch or detached start point.",
        annotations=ToolAnnotations(destructive_hint=False),
    )
    def git_worktree_create(
        path: str,
        branch: str = "",
        start_point: str = "",
        detach: bool = False,
    ) -> dict[str, Any]:
        return git_mutations.worktree_create(git, path, branch, start_point, detach)

    @mcp.tool(
        description="Remove a worktree after verifying loss surface. "
        "Refuses if there are uncommitted changes, untracked files, "
        "or the worktree is locked.",
        annotations=ToolAnnotations(destructive_hint=True),
    )
    def git_worktree_remove(
        path: str,
        expected_head: str = "",
    ) -> dict[str, Any]:
        return git_mutations.worktree_remove(git, path, expected_head)

    @mcp.tool(
        description="Stage explicit paths. Only stages the specified paths, "
        "does not absorb unknown adjacent files.",
        annotations=ToolAnnotations(destructive_hint=False),
    )
    def git_stage(paths: list[str]) -> dict[str, Any]:
        return git_mutations.stage(git, paths)

    @mcp.tool(
        description="Create a commit from the current index. "
        "Does not amend, does not create empty commits. "
        "Optionally verify expected HEAD before committing.",
        annotations=ToolAnnotations(destructive_hint=False),
    )
    def git_commit(
        message: str,
        expected_head: str = "",
    ) -> dict[str, Any]:
        return git_mutations.commit(git, message, expected_head)

    @mcp.tool(
        description="Merge or rebase. Caller specifies the operation explicitly. "
        "Returns conflict state or in-progress operation on failure.",
        annotations=ToolAnnotations(destructive_hint=True),
    )
    def git_integrate(
        operation: str,
        source: str = "",
        onto: str = "",
        expected_head: str = "",
    ) -> dict[str, Any]:
        return git_mutations.integrate(git, operation, source, onto, expected_head)

    @mcp.tool(
        description="Continue or abort an in-progress merge/rebase. "
        "Must be explicitly specified by the caller.",
        annotations=ToolAnnotations(destructive_hint=True),
    )
    def git_integrate_continue(action: str) -> dict[str, Any]:
        return git_mutations.integrate_continue(git, action)


def main() -> None:
    """Entry point for stdio MCP server."""
    if len(sys.argv) < 2:
        print("Usage: python -m git_mcp <repository-path>", file=sys.stderr)
        sys.exit(1)

    mcp = create_server(sys.argv[1])
    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()

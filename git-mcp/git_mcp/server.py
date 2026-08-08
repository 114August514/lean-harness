"""MCP server for Local Git capability.

Exposes Git Contract semantics through structured MCP tools.
Confined to a single repository context. No arbitrary Git or
shell passthrough.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from .git_exec import GitRunner
from .git_facts import (
    OperationState,
    is_ancestor,
    read_commit,
    read_diff,
    read_head,
    read_refs,
    read_repository,
    read_status,
    read_worktrees,
)

server: MCPServer | None = None


def create_server(repo_path: str) -> MCPServer:
    """Create and configure the MCP server for a repository."""
    repo = Path(repo_path).resolve()
    git = GitRunner(repo)

    # Verify it's a Git repository
    result = git.run(["rev-parse", "--is-inside-work-tree"], check=False)
    if not result.ok or result.text.strip() != "true":
        print(f"Error: {repo} is not a Git repository", file=sys.stderr)
        sys.exit(1)

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


def _json(data: Any) -> str:
    """Serialize to JSON string for MCP text content."""
    return json.dumps(data, ensure_ascii=False, indent=2)


def _head_to_dict(head) -> dict:
    return {
        "state": head.state.value,
        "branch": head.branch,
        "commit": head.commit,
        "upstream": head.upstream,
    }


def _status_to_dict(status) -> dict:
    return {
        "staged": [
            {"path": e.path, "index_status": e.index_status, "worktree_status": e.worktree_status, "original_path": e.original_path}
            for e in status.staged
        ],
        "unstaged": [
            {"path": e.path, "index_status": e.index_status, "worktree_status": e.worktree_status, "original_path": e.original_path}
            for e in status.unstaged
        ],
        "untracked": [{"path": e.path} for e in status.untracked],
        "ignored": [{"path": e.path} for e in status.ignored],
        "conflicted": [
            {"path": e.path, "index_status": e.index_status, "worktree_status": e.worktree_status}
            for e in status.conflicted
        ],
        "operation": status.operation.value,
    }


def _register_read_tools(mcp: MCPServer, git: GitRunner) -> None:

    @mcp.tool(
        description="Read repository identity, layout, and current context "
        "(HEAD state, branch, operation in progress).",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    def git_read_context() -> str:
        repo = read_repository(git)
        head = read_head(git)
        status = read_status(git)
        return _json(
            {
                "repository": {
                    "worktree_root": repo.worktree_root,
                    "git_dir": repo.git_dir,
                    "common_dir": repo.common_dir,
                    "is_bare": repo.is_bare,
                    "remotes": repo.remotes,
                },
                "head": _head_to_dict(head),
                "operation": status.operation.value,
            }
        )

    @mcp.tool(
        description="Read working tree and index status: staged, unstaged, "
        "untracked, ignored, conflicted files. Optionally include ignored files.",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    def git_read_status(include_ignored: bool = False) -> str:
        status = read_status(git, include_ignored=include_ignored)
        return _json(_status_to_dict(status))

    @mcp.tool(
        description="Read all refs (branches, tags, remotes) and registered worktrees.",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    def git_read_refs() -> str:
        refs = read_refs(git)
        worktrees = read_worktrees(git)
        return _json(
            {
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
        )

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
    ) -> str:
        result = read_diff(
            git,
            cached=cached,
            base=base or None,
            target=target or None,
            paths=paths or None,
            max_lines=max_lines,
        )
        return _json(result)

    @mcp.tool(
        description="Read commit facts: existence, type, parents. "
        "Check ancestry/reachability between two commits.",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    def git_read_commits(
        revision: str = "",
        ancestor: str = "",
        descendant: str = "",
    ) -> str:
        result: dict[str, Any] = {}
        if revision:
            commit = read_commit(git, revision)
            if commit:
                result["commit"] = {
                    "object_id": commit.object_id,
                    "object_type": commit.object_type,
                    "parents": commit.parents,
                    "tree": commit.tree,
                }
            else:
                result["commit"] = None
                result["error"] = f"not a commit or does not exist: {revision}"
        if ancestor and descendant:
            result["is_ancestor"] = is_ancestor(git, ancestor, descendant)
        return _json(result)


def _register_mutation_tools(mcp: MCPServer, git: GitRunner) -> None:

    @mcp.tool(
        description="Create a new branch at an explicit start point. "
        "Refuses if the branch already exists.",
        annotations=ToolAnnotations(destructive_hint=False),
    )
    def git_branch_create(name: str, start_point: str = "HEAD") -> str:
        # Check branch doesn't already exist
        check = git.run(["rev-parse", "--verify", f"refs/heads/{name}"], check=False)
        if check.ok:
            return _json(
                {"error": f"branch already exists: {name}", "existing_tip": check.text.strip()}
            )
        # Verify start point
        sp = git.run(["rev-parse", start_point], check=False)
        if not sp.ok:
            return _json({"error": f"invalid start point: {start_point}"})
        # Create
        git.run(["branch", "--", name, start_point])
        # After-observation
        new_tip = git.run_text(["rev-parse", f"refs/heads/{name}"])
        return _json({"created": name, "tip": new_tip, "start_point": sp.text.strip()})

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
    ) -> str:
        # Read current tip
        ref = f"refs/heads/{name}"
        current = git.run(["rev-parse", ref], check=False)
        if not current.ok:
            return _json({"error": f"branch does not exist: {name}"})
        current_tip = current.text.strip()

        # Stale check
        if expected_tip and current_tip != expected_tip:
            return _json(
                {
                    "error": "stale precondition",
                    "expected_tip": expected_tip,
                    "observed_tip": current_tip,
                }
            )

        # Check not checked out in any worktree
        worktrees = read_worktrees(git)
        checked_out_in = [
            w.path for w in worktrees if w.branch == f"refs/heads/{name}"
        ]
        if checked_out_in:
            return _json(
                {
                    "error": "branch checked out elsewhere",
                    "worktrees": checked_out_in,
                }
            )

        # Resolve retained refs once, pin their OIDs, verify reachability
        pinned_retained: list[tuple[str, str]] = []
        if retained_refs:
            unreachable_from: list[str] = []
            for rr in retained_refs:
                rr_resolved = git.run(["rev-parse", rr], check=False)
                if not rr_resolved.ok:
                    return _json({"error": f"retained ref not found: {rr}"})
                rr_oid = rr_resolved.text.strip()
                pinned_retained.append((rr, rr_oid))
                if not is_ancestor(git, current_tip, rr_oid):
                    unreachable_from.append(rr)
            if unreachable_from:
                return _json(
                    {
                        "error": "branch tip not reachable from retained refs",
                        "branch_tip": current_tip,
                        "unreachable_from": unreachable_from,
                    }
                )

        # Re-verify retained refs haven't moved since the reachability check
        for rr, rr_oid in pinned_retained:
            moved = git.run(["rev-parse", rr], check=False)
            if not moved.ok or moved.text.strip() != rr_oid:
                return _json(
                    {
                        "error": "retained ref moved during check",
                        "ref": rr,
                        "expected": rr_oid,
                        "observed": moved.text.strip() if moved.ok else None,
                    }
                )

        # Atomic compare-and-delete: refuses if the ref moved since read
        deleted = git.run(
            ["update-ref", "-d", ref, current_tip], check=False
        )
        if not deleted.ok:
            return _json(
                {
                    "error": "compare-and-delete failed (ref moved or locked)",
                    "ref": ref,
                    "expected_tip": current_tip,
                    "detail": deleted.error_text,
                }
            )

        # After-observation
        gone = git.run(["rev-parse", ref], check=False)
        return _json(
            {
                "deleted": name,
                "was_tip": current_tip,
                "verified_gone": not gone.ok,
            }
        )

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
    ) -> str:
        target = Path(path)
        if target.exists() and any(target.iterdir()):
            return _json({"error": f"target path not empty: {path}"})

        args = ["worktree", "add"]
        if detach:
            args.append("--detach")
        if branch:
            args.extend(["-b", branch])
        args.append("--")
        args.append(path)
        if start_point:
            args.append(start_point)

        result = git.run(args, check=False)
        if not result.ok:
            return _json({"error": result.error_text})

        # After-observation
        wt_git = GitRunner(target.resolve())
        head = read_head(wt_git)
        return _json(
            {
                "created": str(target.resolve()),
                "head": _head_to_dict(head),
            }
        )

    @mcp.tool(
        description="Remove a worktree after verifying loss surface. "
        "Refuses if there are uncommitted changes, untracked files, "
        "or the worktree is locked.",
        annotations=ToolAnnotations(destructive_hint=True),
    )
    def git_worktree_remove(
        path: str,
        expected_head: str = "",
    ) -> str:
        target = Path(path).resolve()
        wt_git = GitRunner(target)

        # Verify it's a registered worktree
        worktrees = read_worktrees(git)
        registered = [w for w in worktrees if Path(w.path).resolve() == target]
        if not registered:
            return _json({"error": f"not a registered worktree: {path}"})
        wt = registered[0]

        if wt.is_locked:
            return _json({"error": f"worktree is locked: {path}"})

        # Loss surface
        status = read_status(wt_git, include_ignored=True)
        loss: dict[str, Any] = {}
        if status.staged:
            loss["staged"] = [e.path for e in status.staged]
        if status.unstaged:
            loss["unstaged"] = [e.path for e in status.unstaged]
        if status.untracked:
            loss["untracked"] = [e.path for e in status.untracked]
        if status.ignored:
            loss["ignored"] = [e.path for e in status.ignored]
        if status.conflicted:
            loss["conflicted"] = [e.path for e in status.conflicted]
        if status.operation != OperationState.NONE:
            loss["operation_in_progress"] = status.operation.value

        if loss:
            return _json(
                {
                    "error": "loss surface not empty",
                    "loss_surface": loss,
                    "worktree_head": wt.head,
                }
            )

        # Stale check
        if expected_head and wt.head != expected_head:
            return _json(
                {
                    "error": "stale precondition",
                    "expected_head": expected_head,
                    "observed_head": wt.head,
                }
            )

        # Remove
        git.run(["worktree", "remove", str(target)])
        return _json({"removed": str(target), "was_head": wt.head})

    @mcp.tool(
        description="Stage explicit paths. Only stages the specified paths, "
        "does not absorb unknown adjacent files.",
        annotations=ToolAnnotations(destructive_hint=False),
    )
    def git_stage(paths: list[str]) -> str:
        if not paths:
            return _json({"error": "no paths specified"})
        git.run(["add", "--", *paths])
        # After-observation
        status = read_status(git)
        return _json(
            {
                "staged": [
                    {"path": e.path, "index_status": e.index_status}
                    for e in status.staged
                ],
            }
        )

    @mcp.tool(
        description="Create a commit from the current index. "
        "Does not amend, does not create empty commits. "
        "Optionally verify expected HEAD before committing.",
        annotations=ToolAnnotations(destructive_hint=False),
    )
    def git_commit(
        message: str,
        expected_head: str = "",
    ) -> str:
        if not message.strip():
            return _json({"error": "empty commit message"})

        # Stale check
        if expected_head:
            current = read_head(git)
            if current.commit and current.commit != expected_head:
                return _json(
                    {
                        "error": "stale precondition",
                        "expected_head": expected_head,
                        "observed_head": current.commit,
                    }
                )

        # Check there are staged changes
        status = read_status(git)
        if not status.staged:
            return _json({"error": "no staged changes"})

        git.run(["commit", "-m", message])
        # After-observation
        head = read_head(git)
        return _json(
            {
                "commit": head.commit,
                "branch": head.branch,
                "state": head.state.value,
            }
        )

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
    ) -> str:
        # Stale check
        if expected_head:
            current = read_head(git)
            if current.commit and current.commit != expected_head:
                return _json(
                    {
                        "error": "stale precondition",
                        "expected_head": expected_head,
                        "observed_head": current.commit,
                    }
                )

        # Precondition: no in-progress operation
        status = read_status(git)
        if status.operation != OperationState.NONE:
            return _json(
                {
                    "error": "operation already in progress",
                    "operation": status.operation.value,
                }
            )

        # Precondition: index and tracked working tree must be clean
        if status.staged or status.unstaged:
            return _json(
                {
                    "error": "dirty worktree",
                    "staged": [e.path for e in status.staged],
                    "unstaged": [e.path for e in status.unstaged],
                }
            )
        if status.conflicted:
            return _json(
                {
                    "error": "unresolved conflicts",
                    "conflicted": [e.path for e in status.conflicted],
                }
            )

        if operation == "merge":
            if not source:
                return _json({"error": "merge requires source"})
            result = git.run(["merge", "--", source], check=False)
        elif operation == "rebase":
            if not source:
                return _json({"error": "rebase requires source (upstream)"})
            args = ["rebase"]
            if onto:
                args.extend(["--onto", onto])
            args.extend(["--", source])
            result = git.run(args, check=False)
        else:
            return _json({"error": f"unknown operation: {operation}. Use merge or rebase."})

        # After-observation
        head = read_head(git)
        after_status = read_status(git)
        response: dict[str, Any] = {
            "operation": operation,
            "success": result.ok,
            "head": _head_to_dict(head),
        }
        if not result.ok:
            response["error"] = result.error_text
            if after_status.operation != OperationState.NONE:
                response["in_progress"] = after_status.operation.value
            if after_status.conflicted:
                response["conflicted_files"] = [
                    e.path for e in after_status.conflicted
                ]
        return _json(response)

    @mcp.tool(
        description="Continue or abort an in-progress merge/rebase. "
        "Must be explicitly specified by the caller.",
        annotations=ToolAnnotations(destructive_hint=True),
    )
    def git_integrate_continue(action: str) -> str:
        status = read_status(git)
        if status.operation == OperationState.NONE:
            return _json({"error": "no operation in progress"})

        op = status.operation
        if action == "continue":
            if op == OperationState.MERGE:
                result = git.run(["merge", "--continue"], check=False)
            elif op == OperationState.REBASE:
                result = git.run(["rebase", "--continue"], check=False)
            elif op == OperationState.CHERRY_PICK:
                result = git.run(["cherry-pick", "--continue"], check=False)
            else:
                return _json({"error": f"cannot continue operation: {op.value}"})
        elif action == "abort":
            if op == OperationState.MERGE:
                result = git.run(["merge", "--abort"], check=False)
            elif op == OperationState.REBASE:
                result = git.run(["rebase", "--abort"], check=False)
            elif op == OperationState.CHERRY_PICK:
                result = git.run(["cherry-pick", "--abort"], check=False)
            else:
                return _json({"error": f"cannot abort operation: {op.value}"})
        else:
            return _json({"error": f"unknown action: {action}. Use continue or abort."})

        head = read_head(git)
        after = read_status(git)
        return _json(
            {
                "action": action,
                "operation": op.value,
                "success": result.ok,
                "error": result.error_text if not result.ok else None,
                "head": _head_to_dict(head),
                "remaining_operation": after.operation.value,
            }
        )


def main() -> None:
    """Entry point for stdio MCP server."""
    if len(sys.argv) < 2:
        print("Usage: python -m git_mcp <repository-path>", file=sys.stderr)
        sys.exit(1)

    mcp = create_server(sys.argv[1])

    import asyncio

    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()

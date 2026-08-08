"""Explicit Git mutations with preconditions and after-observation.

Each function follows the mutation boundary:
read before facts → check mechanical preconditions →
execute one explicit mutation → re-read after facts.

No workflow decisions. No automatic strategy selection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .git_exec import GitRunner
from .git_facts import (
    OperationState,
    is_ancestor,
    read_head,
    read_status,
    read_worktrees,
)


def _head_to_dict(head) -> dict:
    return {
        "state": head.state.value,
        "branch": head.branch,
        "commit": head.commit,
        "upstream": head.upstream,
    }


def branch_create(
    git: GitRunner, name: str, start_point: str = "HEAD"
) -> dict[str, Any]:
    """Create a branch at an explicit start point. Refuses if it already exists."""
    check = git.run(["rev-parse", "--verify", f"refs/heads/{name}"], check=False)
    if check.ok:
        return {
            "error": f"branch already exists: {name}",
            "existing_tip": check.text.strip(),
        }
    sp = git.run(["rev-parse", start_point], check=False)
    if not sp.ok:
        return {"error": f"invalid start point: {start_point}"}
    git.run(["branch", "--", name, start_point])
    new_tip = git.run_text(["rev-parse", f"refs/heads/{name}"])
    return {"created": name, "tip": new_tip, "start_point": sp.text.strip()}


def branch_delete(
    git: GitRunner,
    name: str,
    expected_tip: str = "",
    retained_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Delete a branch with compare-and-delete and optional reachability check."""
    ref = f"refs/heads/{name}"
    current = git.run(["rev-parse", ref], check=False)
    if not current.ok:
        return {"error": f"branch does not exist: {name}"}
    current_tip = current.text.strip()

    if expected_tip and current_tip != expected_tip:
        return {
            "error": "stale precondition",
            "expected_tip": expected_tip,
            "observed_tip": current_tip,
        }

    worktrees = read_worktrees(git)
    checked_out_in = [
        w.path for w in worktrees if w.branch == f"refs/heads/{name}"
    ]
    if checked_out_in:
        return {
            "error": "branch checked out elsewhere",
            "worktrees": checked_out_in,
        }

    pinned_retained: list[tuple[str, str]] = []
    if retained_refs:
        unreachable_from: list[str] = []
        for rr in retained_refs:
            rr_resolved = git.run(["rev-parse", rr], check=False)
            if not rr_resolved.ok:
                return {"error": f"retained ref not found: {rr}"}
            rr_oid = rr_resolved.text.strip()
            pinned_retained.append((rr, rr_oid))
            if not is_ancestor(git, current_tip, rr_oid):
                unreachable_from.append(rr)
        if unreachable_from:
            return {
                "error": "branch tip not reachable from retained refs",
                "branch_tip": current_tip,
                "unreachable_from": unreachable_from,
            }

    for rr, rr_oid in pinned_retained:
        moved = git.run(["rev-parse", rr], check=False)
        if not moved.ok or moved.text.strip() != rr_oid:
            return {
                "error": "retained ref moved during check",
                "ref": rr,
                "expected": rr_oid,
                "observed": moved.text.strip() if moved.ok else None,
            }

    deleted = git.run(["update-ref", "-d", ref, current_tip], check=False)
    if not deleted.ok:
        return {
            "error": "compare-and-delete failed (ref moved or locked)",
            "ref": ref,
            "expected_tip": current_tip,
            "detail": deleted.error_text,
        }

    gone = git.run(["rev-parse", ref], check=False)
    return {
        "deleted": name,
        "was_tip": current_tip,
        "verified_gone": not gone.ok,
    }


def worktree_create(
    git: GitRunner,
    path: str,
    branch: str = "",
    start_point: str = "",
    detach: bool = False,
) -> dict[str, Any]:
    """Create a linked worktree at an explicit path."""
    target = Path(path)
    if target.exists() and any(target.iterdir()):
        return {"error": f"target path not empty: {path}"}

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
        return {"error": result.error_text}

    wt_git = GitRunner(target.resolve())
    head = read_head(wt_git)
    return {
        "created": str(target.resolve()),
        "head": _head_to_dict(head),
    }


def worktree_remove(
    git: GitRunner,
    path: str,
    expected_head: str = "",
) -> dict[str, Any]:
    """Remove a worktree after verifying loss surface is empty."""
    target = Path(path).resolve()
    wt_git = GitRunner(target)

    worktrees = read_worktrees(git)
    registered = [w for w in worktrees if Path(w.path).resolve() == target]
    if not registered:
        return {"error": f"not a registered worktree: {path}"}
    wt = registered[0]

    if wt.is_locked:
        return {"error": f"worktree is locked: {path}"}

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
        return {
            "error": "loss surface not empty",
            "loss_surface": loss,
            "worktree_head": wt.head,
        }

    if expected_head and wt.head != expected_head:
        return {
            "error": "stale precondition",
            "expected_head": expected_head,
            "observed_head": wt.head,
        }

    git.run(["worktree", "remove", str(target)])
    return {"removed": str(target), "was_head": wt.head}


def stage(git: GitRunner, paths: list[str]) -> dict[str, Any]:
    """Stage explicit paths."""
    if not paths:
        return {"error": "no paths specified"}
    git.run(["add", "--", *paths])
    status = read_status(git)
    return {
        "staged": [
            {"path": e.path, "index_status": e.index_status}
            for e in status.staged
        ],
    }


def commit(
    git: GitRunner,
    message: str,
    expected_head: str = "",
) -> dict[str, Any]:
    """Create a commit from the current index."""
    if not message.strip():
        return {"error": "empty commit message"}

    if expected_head:
        current = read_head(git)
        if current.commit and current.commit != expected_head:
            return {
                "error": "stale precondition",
                "expected_head": expected_head,
                "observed_head": current.commit,
            }

    status = read_status(git)
    if not status.staged:
        return {"error": "no staged changes"}

    git.run(["commit", "-m", message])
    head = read_head(git)
    return {
        "commit": head.commit,
        "branch": head.branch,
        "state": head.state.value,
    }


def integrate(
    git: GitRunner,
    operation: str,
    source: str = "",
    onto: str = "",
    expected_head: str = "",
) -> dict[str, Any]:
    """Merge or rebase with preconditions and after-observation."""
    if expected_head:
        current = read_head(git)
        if current.commit and current.commit != expected_head:
            return {
                "error": "stale precondition",
                "expected_head": expected_head,
                "observed_head": current.commit,
            }

    status = read_status(git)
    if status.operation != OperationState.NONE:
        return {
            "error": "operation already in progress",
            "operation": status.operation.value,
        }

    if status.staged or status.unstaged:
        return {
            "error": "dirty worktree",
            "staged": [e.path for e in status.staged],
            "unstaged": [e.path for e in status.unstaged],
        }
    if status.conflicted:
        return {
            "error": "unresolved conflicts",
            "conflicted": [e.path for e in status.conflicted],
        }

    if operation == "merge":
        if not source:
            return {"error": "merge requires source"}
        result = git.run(["merge", "--", source], check=False)
    elif operation == "rebase":
        if not source:
            return {"error": "rebase requires source (upstream)"}
        args = ["rebase"]
        if onto:
            args.extend(["--onto", onto])
        args.extend(["--", source])
        result = git.run(args, check=False)
    else:
        return {"error": f"unknown operation: {operation}. Use merge or rebase."}

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
    return response


def integrate_continue(git: GitRunner, action: str) -> dict[str, Any]:
    """Continue or abort an in-progress merge/rebase/cherry-pick."""
    status = read_status(git)
    if status.operation == OperationState.NONE:
        return {"error": "no operation in progress"}

    op = status.operation
    if action == "continue":
        if op == OperationState.MERGE:
            result = git.run(["merge", "--continue"], check=False)
        elif op == OperationState.REBASE:
            result = git.run(["rebase", "--continue"], check=False)
        elif op == OperationState.CHERRY_PICK:
            result = git.run(["cherry-pick", "--continue"], check=False)
        else:
            return {"error": f"cannot continue operation: {op.value}"}
    elif action == "abort":
        if op == OperationState.MERGE:
            result = git.run(["merge", "--abort"], check=False)
        elif op == OperationState.REBASE:
            result = git.run(["rebase", "--abort"], check=False)
        elif op == OperationState.CHERRY_PICK:
            result = git.run(["cherry-pick", "--abort"], check=False)
        else:
            return {"error": f"cannot abort operation: {op.value}"}
    else:
        return {"error": f"unknown action: {action}. Use continue or abort."}

    head = read_head(git)
    after = read_status(git)
    return {
        "action": action,
        "operation": op.value,
        "success": result.ok,
        "error": result.error_text if not result.ok else None,
        "head": _head_to_dict(head),
        "remaining_operation": after.operation.value,
    }

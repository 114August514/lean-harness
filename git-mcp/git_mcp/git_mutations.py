"""Explicit Git mutations with preconditions and after-observation.

Each function follows the mutation boundary:
read before facts → check mechanical preconditions →
execute one explicit mutation → re-read after facts.

No workflow decisions. No automatic strategy selection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .git_exec import GitError, GitRunner
from .git_facts import (
    OperationState,
    check_ancestor,
    read_head,
    read_status,
    read_worktrees,
)


def _head_to_dict(head) -> dict:
    result = {
        "state": head.state.value if head.state else None,
        "branch": head.branch,
        "commit": head.commit,
        "upstream": head.upstream,
    }
    if head.error:
        result["error"] = head.error
    return result


def _observe_ref(git: GitRunner, ref: str) -> tuple[str | None, str | None]:
    exists = git.run(["show-ref", "--verify", "--quiet", ref], check=False)
    if exists.returncode == 1:
        return None, None
    if not exists.ok:
        return None, exists.error_text

    tip = git.run(["rev-parse", "--verify", ref], check=False)
    if not tip.ok:
        return None, tip.error_text
    return tip.text.strip(), None


def _status_to_dict(status) -> dict[str, Any]:
    return {
        "staged": [
            {"path": entry.path, "index_status": entry.index_status}
            for entry in status.staged
        ],
        "unstaged": [
            {"path": entry.path, "worktree_status": entry.worktree_status}
            for entry in status.unstaged
        ],
        "untracked": [{"path": entry.path} for entry in status.untracked],
        "conflicted": [{"path": entry.path} for entry in status.conflicted],
        "operation": status.operation.value,
    }


def _observe_worktree(
    git: GitRunner, target: Path
) -> tuple[dict | None, bool, str | None]:
    path_exists = target.exists()
    try:
        worktrees = read_worktrees(git)
    except GitError as error:
        return None, path_exists, str(error)

    for worktree in worktrees:
        if Path(worktree.path).resolve() == target:
            return (
                {
                    "path": worktree.path,
                    "head": worktree.head,
                    "branch": worktree.branch,
                    "is_locked": worktree.is_locked,
                    "is_prunable": worktree.is_prunable,
                },
                path_exists,
                None,
            )
    return None, path_exists, None


def branch_create(
    git: GitRunner, name: str, start_point: str = "HEAD"
) -> dict[str, Any]:
    """Create a branch at an explicit start point. Refuses if it already exists."""
    ref = f"refs/heads/{name}"
    existing_tip, observation_error = _observe_ref(git, ref)
    if observation_error:
        return {"error": observation_error}
    if existing_tip:
        return {
            "error": f"branch already exists: {name}",
            "existing_tip": existing_tip,
        }

    sp = git.run(["rev-parse", start_point], check=False)
    if not sp.ok:
        return {"error": f"invalid start point: {start_point}"}

    result = git.run(["branch", "--", name, start_point], check=False)
    if not result.ok:
        if not result.timed_out:
            return {"error": result.error_text}
        observed_tip, observation_error = _observe_ref(git, ref)
        if observed_tip == sp.text.strip():
            return {
                "created": name,
                "tip": observed_tip,
                "start_point": sp.text.strip(),
                "command_error": result.error_text,
            }
        response = {
            "error": result.error_text,
            "created": None,
            "observed_tip": observed_tip,
        }
        if observation_error:
            response["observation_error"] = observation_error
        return response

    new_tip = git.run_text(["rev-parse", ref])
    return {"created": name, "tip": new_tip, "start_point": sp.text.strip()}


def branch_delete(
    git: GitRunner,
    name: str,
    expected_tip: str = "",
    retained_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Delete a branch with compare-and-delete and optional reachability check."""
    ref = f"refs/heads/{name}"
    current_tip, observation_error = _observe_ref(git, ref)
    if observation_error:
        return {"error": observation_error}
    if current_tip is None:
        return {"error": f"branch does not exist: {name}"}

    if expected_tip and current_tip != expected_tip:
        return {
            "error": "stale precondition",
            "expected_tip": expected_tip,
            "observed_tip": current_tip,
        }

    worktrees = read_worktrees(git)
    checked_out_in = [w.path for w in worktrees if w.branch == f"refs/heads/{name}"]
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
            anc = check_ancestor(git, current_tip, rr_oid)
            if anc.error:
                return {"error": f"ancestry check failed: {anc.error}"}
            if anc.result is not True:
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
    if not deleted.ok and not deleted.timed_out:
        return {
            "error": "compare-and-delete failed (ref moved or locked)",
            "ref": ref,
            "expected_tip": current_tip,
            "detail": deleted.error_text,
        }

    observed_tip, observation_error = _observe_ref(git, ref)
    if observed_tip is None and not observation_error:
        response = {
            "deleted": name,
            "was_tip": current_tip,
            "verified_gone": True,
        }
        if deleted.timed_out:
            response["command_error"] = deleted.error_text
        return response

    response = {
        "error": deleted.error_text or "branch deletion could not be verified",
        "ref": ref,
        "expected_tip": current_tip,
        "observed_tip": observed_tip,
    }
    if observation_error:
        response["observation_error"] = observation_error
    return response


def worktree_create(
    git: GitRunner,
    path: str,
    branch: str = "",
    start_point: str = "",
    detach: bool = False,
) -> dict[str, Any]:
    """Create a linked worktree at an explicit path."""
    target = Path(path)
    if not target.is_absolute():
        return {"error": f"worktree path must be absolute: {path}"}
    target = target.resolve()
    if target.exists() and any(target.iterdir()):
        return {"error": f"target path not empty: {path}"}

    args = ["worktree", "add"]
    if detach:
        args.append("--detach")
    if branch:
        args.extend(["-b", branch])
    args.extend(["--", path])
    if start_point:
        args.append(start_point)

    result = git.run(args, check=False)
    if not result.ok:
        if not result.timed_out:
            return {"error": result.error_text}
        registration, path_exists, observation_error = _observe_worktree(git, target)
        response: dict[str, Any] = {
            "registration": registration,
            "path_exists": path_exists,
        }
        if registration is not None and path_exists:
            response.update(
                {
                    "created": str(target),
                    "head": _head_to_dict(read_head(GitRunner(target))),
                    "command_error": result.error_text,
                }
            )
        else:
            response["error"] = result.error_text
        if observation_error:
            response["observation_error"] = observation_error
        return response

    head = read_head(GitRunner(target))
    return {
        "created": str(target),
        "head": _head_to_dict(head),
    }


def worktree_remove(
    git: GitRunner,
    path: str,
    expected_head: str = "",
) -> dict[str, Any]:
    """Remove a worktree after verifying loss surface is empty."""
    target = Path(path)
    if not target.is_absolute():
        return {"error": f"worktree path must be absolute: {path}"}
    target = target.resolve()
    wt_git = GitRunner(target)

    worktrees = read_worktrees(git)
    registered = [w for w in worktrees if Path(w.path).resolve() == target]
    if not registered:
        return {"error": f"not a registered worktree: {path}"}
    wt = registered[0]

    if wt.is_locked:
        return {"error": f"worktree is locked: {path}"}
    if wt.is_main:
        return {"error": "cannot remove main worktree"}

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

    result = git.run(["worktree", "remove", str(target)], check=False)
    if not result.ok:
        if not result.timed_out:
            return {"error": result.error_text, "worktree": str(target)}
        registration, path_exists, observation_error = _observe_worktree(git, target)
        response: dict[str, Any] = {
            "registration": registration,
            "path_exists": path_exists,
        }
        if registration is None and not path_exists and not observation_error:
            response.update(
                {
                    "removed": str(target),
                    "was_head": wt.head,
                    "command_error": result.error_text,
                }
            )
        else:
            response["error"] = result.error_text
        if observation_error:
            response["observation_error"] = observation_error
        return response
    return {"removed": str(target), "was_head": wt.head}


def stage(git: GitRunner, paths: list[str]) -> dict[str, Any]:
    """Stage explicit paths."""
    if not paths:
        return {"error": "no paths specified"}

    result = git.run(["add", "--", *paths], check=False)
    if not result.ok and not result.timed_out:
        return {"error": result.error_text}

    try:
        status = read_status(git)
    except GitError as error:
        return {
            "error": result.error_text or "staging result could not be observed",
            "observation_error": str(error),
        }

    observed = _status_to_dict(status)
    if result.timed_out:
        return {
            "error": result.error_text,
            "status": observed,
        }
    return {"staged": observed["staged"]}


def commit(
    git: GitRunner,
    message: str,
    expected_head: str = "",
) -> dict[str, Any]:
    """Create a commit from the current index."""
    if not message.strip():
        return {"error": "empty commit message"}

    before_head = read_head(git)
    if before_head.error:
        return {
            "error": f"HEAD unavailable: {before_head.error}",
            "head": _head_to_dict(before_head),
        }
    if expected_head and before_head.commit != expected_head:
        return {
            "error": "stale precondition",
            "expected_head": expected_head,
            "observed_head": before_head.commit,
        }

    status = read_status(git)
    if not status.staged:
        return {"error": "no staged changes"}

    result = git.run(["commit", "-m", message], check=False)
    if not result.ok and not result.timed_out:
        return {"error": result.error_text}

    head = read_head(git)
    if result.timed_out:
        try:
            after_status = read_status(git)
        except GitError as error:
            return {
                "error": result.error_text,
                "head": _head_to_dict(head),
                "observation_error": str(error),
            }
        observed_status = _status_to_dict(after_status)
        if not head.error and head.commit != before_head.commit:
            return {
                "commit": head.commit,
                "branch": head.branch,
                "state": head.state.value if head.state else None,
                "staged": observed_status["staged"],
                "command_error": result.error_text,
            }
        return {
            "error": result.error_text,
            "before_head": _head_to_dict(before_head),
            "head": _head_to_dict(head),
            "status": observed_status,
        }

    if head.error:
        return {
            "error": f"commit created but HEAD observation failed: {head.error}",
            "head": _head_to_dict(head),
        }
    return {
        "commit": head.commit,
        "branch": head.branch,
        "state": head.state.value if head.state else None,
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
        if current.error:
            return {
                "error": f"HEAD unavailable: {current.error}",
                "head": _head_to_dict(current),
            }
        if current.commit != expected_head:
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
        result = git.run(["merge", "--end-of-options", source], check=False)
    elif operation == "rebase":
        if not source:
            return {"error": "rebase requires source (upstream)"}
        args = ["rebase"]
        if onto:
            args.extend(["--onto", onto])
        args.extend(["--end-of-options", source])
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
            response["conflicted_files"] = [e.path for e in after_status.conflicted]
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

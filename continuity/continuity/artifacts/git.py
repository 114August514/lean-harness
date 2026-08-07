"""Structured Git facts used for recovery and checkpoint validation."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from ..errors import GitFactError

_CONFLICT_CODES = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}


def _run_git(
    repo: Path, *arguments: str, text: bool = True
) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", "-C", str(Path(repo).resolve()), *arguments],
            capture_output=True,
            text=text,
            check=False,
        )
    except OSError as error:
        raise GitFactError(f"cannot execute Git: {error}") from error


def _raise_git_failure(operation: str, result: subprocess.CompletedProcess) -> None:
    stderr = result.stderr
    if isinstance(stderr, bytes):
        detail = os.fsdecode(stderr).strip()
    else:
        detail = (stderr or "").strip()
    suffix = f": {detail}" if detail else ""
    raise GitFactError(f"Git could not {operation}{suffix}")


def _required_git_path(repo: Path, argument: str) -> Path:
    result = _run_git(repo, "rev-parse", argument)
    if result.returncode != 0:
        _raise_git_failure(f"read {argument}", result)
    value = Path(result.stdout.strip())
    return (
        (Path(repo).resolve() / value).resolve() if not value.is_absolute() else value
    )


def git_common_dir(repo: Path) -> Path:
    return _required_git_path(repo, "--git-common-dir")


def git_dir(repo: Path) -> Path:
    return _required_git_path(repo, "--git-dir")


def origin_url(repo: Path) -> str | None:
    result = _run_git(repo, "config", "--get", "remote.origin.url")
    if result.returncode == 0:
        return result.stdout.strip() or None
    if result.returncode == 1:
        return None
    _raise_git_failure("read remote.origin.url", result)


def _find_commit(repo: Path, revision: str) -> str | None:
    result = _run_git(
        repo, "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}"
    )
    if result.returncode == 0:
        return result.stdout.strip()
    if result.returncode == 1:
        return None
    _raise_git_failure(f"resolve commit {revision}", result)


def head_commit(repo: Path) -> str | None:
    return _find_commit(repo, "HEAD")


def current_branch(repo: Path) -> str | None:
    result = _run_git(repo, "branch", "--show-current")
    if result.returncode != 0:
        _raise_git_failure("read the current branch", result)
    branch = result.stdout.strip()
    return branch or None


def resolve_commit(repo: Path, revision: str) -> str:
    commit = _find_commit(repo, revision)
    if commit is None:
        raise GitFactError(f"cannot resolve commit: {revision}")
    return commit


def commit_exists(repo: Path, commit: str) -> bool:
    return _find_commit(repo, commit) is not None


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = _run_git(repo, "merge-base", "--is-ancestor", ancestor, descendant)
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    _raise_git_failure(f"compare commits {ancestor} and {descendant}", result)


def structured_status(repo: Path) -> list[dict[str, Any]]:
    """Parse ``git status --porcelain=v1 -z`` without losing path facts."""

    result = _run_git(repo, "status", "--porcelain=v1", "-z", text=False)
    if result.returncode != 0:
        _raise_git_failure("read Git status", result)

    fields = result.stdout.split(b"\0")
    changes: list[dict[str, Any]] = []
    position = 0
    while position < len(fields):
        raw = fields[position]
        position += 1
        if not raw:
            continue
        if len(raw) < 3 or raw[2:3] != b" ":
            raise GitFactError(f"unexpected porcelain status record: {raw!r}")
        code = os.fsdecode(raw[:2])
        path = os.fsdecode(raw[3:])
        original_path: str | None = None
        if "R" in code or "C" in code:
            if position >= len(fields) or not fields[position]:
                raise GitFactError(f"rename/copy status lacks original path: {path}")
            original_path = os.fsdecode(fields[position])
            position += 1
        change = {
            "index_status": code[0],
            "worktree_status": code[1],
            "path": path,
            "conflict": code in _CONFLICT_CODES,
        }
        if original_path is not None:
            change["original_path"] = original_path
        changes.append(change)
    return changes


def git_snapshot(repo: Path) -> dict[str, Any]:
    return {
        "head": head_commit(repo),
        "branch": current_branch(repo),
        "changes": structured_status(repo),
    }

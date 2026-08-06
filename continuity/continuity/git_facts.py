"""Structured Git facts used during recovery and checkpoint validation."""

from __future__ import annotations

import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

from .errors import DamagedStateError, GitFactError
from .storage import atomic_write_json, read_json

_CONFLICT_CODES = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
_WORKTREE_ID = re.compile(r"^wt-[0-9a-f]{32}$")


def run_git(
    repo: Path, *arguments: str, text: bool = True
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(Path(repo).resolve()), *arguments],
        capture_output=True,
        text=text,
        check=False,
    )


def _required_git_path(repo: Path, argument: str) -> Path:
    result = run_git(repo, "rev-parse", argument)
    if result.returncode != 0:
        raise GitFactError(f"not a Git worktree: {Path(repo).resolve()}")
    value = Path(result.stdout.strip())
    return (
        (Path(repo).resolve() / value).resolve() if not value.is_absolute() else value
    )


def git_common_dir(repo: Path) -> Path:
    return _required_git_path(repo, "--git-common-dir")


def git_dir(repo: Path) -> Path:
    return _required_git_path(repo, "--git-dir")


def worktree_id(repo: Path) -> str:
    """Return a persisted identity attached to this worktree's Git metadata."""

    identity_path = git_dir(repo) / "lean-harness" / "worktree.json"
    current = read_json(identity_path)
    if current is not None:
        identity = current.get("worktree_id")
        if not isinstance(identity, str) or not _WORKTREE_ID.fullmatch(identity):
            raise DamagedStateError(
                f"damaged worktree identity at {identity_path}: invalid worktree_id"
            )
        return identity

    identity = f"wt-{uuid.uuid4().hex}"
    atomic_write_json(identity_path, {"schema_version": 1, "worktree_id": identity})
    return identity


def head_commit(repo: Path) -> str | None:
    result = run_git(repo, "rev-parse", "--verify", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None


def current_branch(repo: Path) -> str | None:
    result = run_git(repo, "branch", "--show-current")
    branch = result.stdout.strip()
    return branch or None


def resolve_commit(repo: Path, revision: str) -> str:
    result = run_git(repo, "rev-parse", "--verify", f"{revision}^{{commit}}")
    if result.returncode != 0:
        raise GitFactError(f"cannot resolve commit: {revision}")
    return result.stdout.strip()


def commit_exists(repo: Path, commit: str) -> bool:
    result = run_git(repo, "cat-file", "-e", f"{commit}^{{commit}}")
    return result.returncode == 0


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = run_git(repo, "merge-base", "--is-ancestor", ancestor, descendant)
    return result.returncode == 0


def structured_status(repo: Path) -> list[dict[str, Any]]:
    """Parse ``git status --porcelain=v1 -z`` without losing path information."""

    result = run_git(repo, "status", "--porcelain=v1", "-z", text=False)
    if result.returncode != 0:
        stderr = os.fsdecode(result.stderr).strip()
        raise GitFactError(f"cannot read Git status: {stderr}")

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

"""Structured Git facts.

Reads Git state using NUL-separated porcelain formats and returns
typed, machine-readable structures. Never parses human-oriented
Git output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .git_exec import GitRunner


class HeadState(Enum):
    BRANCH = "branch"
    DETACHED = "detached"
    UNBORN = "unborn"


class OperationState(Enum):
    NONE = "none"
    MERGE = "merge"
    REBASE = "rebase"
    CHERRY_PICK = "cherry-pick"
    REVERT = "revert"
    BISECT = "bisect"


@dataclass
class HeadInfo:
    state: HeadState
    branch: str | None = None  # set when state == BRANCH
    commit: str | None = None  # set when state != UNBORN
    upstream: str | None = None


@dataclass
class StatusEntry:
    path: str
    index_status: str  # single char: M A D R C U ? !
    worktree_status: str  # single char
    original_path: str | None = None  # set for renames/copies


@dataclass
class StatusInfo:
    entries: list[StatusEntry] = field(default_factory=list)
    operation: OperationState = OperationState.NONE

    @property
    def staged(self) -> list[StatusEntry]:
        return [
            e
            for e in self.entries
            if e.index_status not in (" ", "?", "!")
        ]

    @property
    def unstaged(self) -> list[StatusEntry]:
        return [
            e
            for e in self.entries
            if e.worktree_status not in (" ", "?", "!")
            and e.index_status != "?"
        ]

    @property
    def untracked(self) -> list[StatusEntry]:
        return [e for e in self.entries if e.index_status == "?"]

    @property
    def ignored(self) -> list[StatusEntry]:
        return [e for e in self.entries if e.index_status == "!"]

    @property
    def conflicted(self) -> list[StatusEntry]:
        return [
            e
            for e in self.entries
            if e.index_status == "U" or e.worktree_status == "U"
        ]


@dataclass
class WorktreeInfo:
    path: str
    head: str
    branch: str | None  # None when detached
    is_main: bool
    is_locked: bool
    is_prunable: bool


@dataclass
class RefInfo:
    name: str
    object_id: str
    object_type: str
    symbolic_target: str | None = None
    upstream: str | None = None


@dataclass
class CommitInfo:
    object_id: str
    object_type: str
    parents: list[str]
    tree: str


@dataclass
class RepositoryInfo:
    worktree_root: str
    git_dir: str
    common_dir: str
    is_bare: bool
    remotes: dict[str, dict[str, str]] = field(default_factory=dict)


def read_repository(git: GitRunner) -> RepositoryInfo:
    """Read repository identity and layout facts."""
    root = git.run_text(["rev-parse", "--show-toplevel"])
    git_dir_raw = git.run_text(["rev-parse", "--git-dir"])
    common_dir_raw = git.run_text(["rev-parse", "--git-common-dir"])
    bare = git.run_text(["rev-parse", "--is-bare-repository"]) == "true"

    git_dir = Path(git_dir_raw)
    if not git_dir.is_absolute():
        git_dir = git.work_dir / git_dir
    common_dir = Path(common_dir_raw)
    if not common_dir.is_absolute():
        common_dir = git.work_dir / common_dir

    remotes: dict[str, dict[str, str]] = {}
    remote_names = git.run_text(["remote"]).splitlines()
    for name in remote_names:
        name = name.strip()
        if not name:
            continue
        fetch_url = git.run_text(["remote", "get-url", name], check=False)
        push_url = git.run_text(["remote", "get-url", "--push", name], check=False)
        remotes[name] = {
            "fetch_url": fetch_url if fetch_url else "",
            "push_url": push_url if push_url else "",
        }

    return RepositoryInfo(
        worktree_root=root,
        git_dir=str(git_dir.resolve()),
        common_dir=str(common_dir.resolve()),
        is_bare=bare,
        remotes=remotes,
    )


def read_head(git: GitRunner) -> HeadInfo:
    """Read HEAD state: branch, detached, or unborn."""
    # Try to resolve HEAD to a commit first
    commit_result = git.run(["rev-parse", "HEAD"], check=False)
    if not commit_result.ok:
        return HeadInfo(state=HeadState.UNBORN)

    commit = commit_result.text.strip()

    # HEAD resolves to a commit — check if on a branch
    branch_result = git.run(["symbolic-ref", "--short", "HEAD"], check=False)
    if branch_result.ok:
        branch = branch_result.text.strip()
        upstream_result = git.run(
            ["rev-parse", "--abbrev-ref", "@{upstream}"], check=False
        )
        upstream = (
            upstream_result.text.strip() if upstream_result.ok else None
        )
        return HeadInfo(
            state=HeadState.BRANCH,
            branch=branch,
            commit=commit,
            upstream=upstream,
        )

    return HeadInfo(state=HeadState.DETACHED, commit=commit)


def read_status(git: GitRunner, *, include_ignored: bool = False) -> StatusInfo:
    """Read working tree and index status using porcelain v2 NUL format."""
    args = ["status", "--porcelain=v2", "-z", "--branch"]
    if include_ignored:
        args.append("--ignored=matching")
    result = git.run(args)

    entries: list[StatusEntry] = []
    raw = result.nul_fields()

    i = 0
    while i < len(raw):
        record = raw[i]
        i += 1
        if not record:
            continue
        kind = chr(record[0])
        if kind == "#":
            # branch header — skip
            continue
        elif kind == "1":
            # ordinary entry: 1 <XY> <sub> <mH> <mI> <mW> <hH> <hI> <path>
            parts = record.split(b" ", 8)
            if len(parts) >= 9:
                xy = parts[1].decode()
                path = parts[8].decode("utf-8", errors="replace")
                entries.append(
                    StatusEntry(
                        path=path,
                        index_status=xy[0],
                        worktree_status=xy[1],
                    )
                )
        elif kind == "2":
            # rename/copy: 2 <XY> <sub> <mH> <mI> <mW> <hH> <hI> <X><score> <path>
            # followed by original path in next NUL field
            parts = record.split(b" ", 9)
            if len(parts) >= 10:
                xy = parts[1].decode()
                path = parts[9].decode("utf-8", errors="replace")
                orig = (
                    raw[i].decode("utf-8", errors="replace")
                    if i < len(raw)
                    else None
                )
                if i < len(raw):
                    i += 1
                entries.append(
                    StatusEntry(
                        path=path,
                        index_status=xy[0],
                        worktree_status=xy[1],
                        original_path=orig,
                    )
                )
        elif kind == "u":
            # unmerged: u <XY> <sub> <m1> <m2> <m3> <mW> <h1> <h2> <h3> <path>
            parts = record.split(b" ", 10)
            if len(parts) >= 11:
                xy = parts[1].decode()
                path = parts[10].decode("utf-8", errors="replace")
                entries.append(
                    StatusEntry(
                        path=path,
                        index_status=xy[0],
                        worktree_status=xy[1],
                    )
                )
        elif kind == "?":
            path = record[2:].decode("utf-8", errors="replace")
            entries.append(
                StatusEntry(path=path, index_status="?", worktree_status="?")
            )
        elif kind == "!":
            path = record[2:].decode("utf-8", errors="replace")
            entries.append(
                StatusEntry(path=path, index_status="!", worktree_status="!")
            )

    operation = _detect_operation(git)
    return StatusInfo(entries=entries, operation=operation)


def _detect_operation(git: GitRunner) -> OperationState:
    """Detect in-progress Git operation from state files."""
    git_dir_raw = git.run_text(["rev-parse", "--git-dir"])
    git_dir = Path(git_dir_raw)
    if not git_dir.is_absolute():
        git_dir = git.work_dir / git_dir
    if (git_dir / "MERGE_HEAD").exists():
        return OperationState.MERGE
    if (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists():
        return OperationState.REBASE
    if (git_dir / "CHERRY_PICK_HEAD").exists():
        return OperationState.CHERRY_PICK
    if (git_dir / "REVERT_HEAD").exists():
        return OperationState.REVERT
    if (git_dir / "BISECT_LOG").exists():
        return OperationState.BISECT
    return OperationState.NONE


def read_worktrees(git: GitRunner) -> list[WorktreeInfo]:
    """Read all registered worktrees."""
    result = git.run(["worktree", "list", "--porcelain", "-z"])
    worktrees: list[WorktreeInfo] = []
    current: dict[str, str | bool] = {}

    for field_bytes in result.nul_fields():
        if not field_bytes:
            # Empty field = record separator
            if current:
                worktrees.append(_parse_worktree(current, is_main=len(worktrees) == 0))
                current = {}
            continue
        field_str = field_bytes.decode("utf-8", errors="replace")
        if " " in field_str:
            key, value = field_str.split(" ", 1)
            current[key] = value
        else:
            current[field_str] = True

    if current:
        worktrees.append(_parse_worktree(current, is_main=len(worktrees) == 0))

    return worktrees


def _parse_worktree(fields: dict[str, str | bool], *, is_main: bool) -> WorktreeInfo:
    branch_raw = fields.get("branch")
    return WorktreeInfo(
        path=str(fields.get("worktree", "")),
        head=str(fields.get("HEAD", "")),
        branch=str(branch_raw) if isinstance(branch_raw, str) else None,
        is_main=is_main,
        is_locked=bool(fields.get("locked")),
        is_prunable=bool(fields.get("prunable")),
    )


def read_refs(git: GitRunner) -> list[RefInfo]:
    """Read all refs with object IDs and types."""
    result = git.run(
        [
            "for-each-ref",
            "--format=%(refname)%00%(objectname)%00%(objecttype)%00%(symref)%00%(upstream:short)%00",
        ]
    )
    refs: list[RefInfo] = []
    fields = result.nul_fields()
    # Each ref produces 5 NUL-separated fields; entries separated by newline
    # at the start of the next refname field.
    i = 0
    while i + 4 < len(fields) + 1:
        if i + 4 >= len(fields):
            break
        name = fields[i].decode("utf-8", errors="replace").lstrip("\n")
        oid = fields[i + 1].decode("utf-8", errors="replace")
        otype = fields[i + 2].decode("utf-8", errors="replace")
        symref = fields[i + 3].decode("utf-8", errors="replace")
        upstream = fields[i + 4].decode("utf-8", errors="replace")
        refs.append(
            RefInfo(
                name=name,
                object_id=oid,
                object_type=otype,
                symbolic_target=symref if symref else None,
                upstream=upstream if upstream else None,
            )
        )
        i += 5
    return refs


def read_commit(git: GitRunner, rev: str) -> CommitInfo | None:
    """Read commit facts. Returns None if the object doesn't exist or isn't a commit."""
    result = git.run(["cat-file", "-t", "--end-of-options", rev], check=False)
    if not result.ok:
        return None
    obj_type = result.text.strip()
    if obj_type != "commit":
        return None

    parents_result = git.run(
        ["cat-file", "commit", "--end-of-options", rev], check=False
    )
    if not parents_result.ok:
        return None

    tree = ""
    parents: list[str] = []
    for line in parents_result.lines():
        if line.startswith("tree "):
            tree = line[5:]
        elif line.startswith("parent "):
            parents.append(line[7:])
        elif line == "":
            break

    return CommitInfo(
        object_id=git.run_text(["rev-parse", rev]),
        object_type=obj_type,
        parents=parents,
        tree=tree,
    )


def is_ancestor(git: GitRunner, ancestor: str, descendant: str) -> bool:
    """Check if ancestor is an ancestor of descendant."""
    result = git.run(
        ["merge-base", "--is-ancestor", "--end-of-options", ancestor, descendant],
        check=False,
    )
    return result.ok


def read_diff(
    git: GitRunner,
    *,
    cached: bool = False,
    base: str | None = None,
    target: str | None = None,
    paths: list[str] | None = None,
    max_lines: int = 500,
) -> dict:
    """Read diff with bounded output.

    Returns a dict with the diff text and truncation indicator.
    """
    args = ["diff", "--no-color", "--end-of-options"]
    if cached:
        args.append("--cached")
    if base and target:
        args.append(f"{base}...{target}")
    elif base:
        args.append(base)
    if paths:
        args.append("--")
        args.extend(paths)

    result = git.run(args, check=False)
    if not result.ok:
        return {
            "error": result.error_text,
            "diff": "",
            "truncated": False,
            "total_lines": 0,
        }

    lines = result.lines()
    truncated = len(lines) > max_lines
    if truncated:
        lines = lines[:max_lines]

    return {
        "diff": "\n".join(lines),
        "truncated": truncated,
        "total_lines": len(result.lines()),
    }

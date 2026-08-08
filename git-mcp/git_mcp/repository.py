"""Repository identity and confinement.

Binds a single repository at startup and provides canonical paths,
repository membership checks, and linked worktree resolution.
This is the safety boundary: all Git operations flow through here.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from .git_exec import GitRunner


@dataclass
class RepositoryContext:
    """A bound repository with resolved identity."""

    worktree_root: Path
    git_dir: Path
    common_dir: Path
    is_bare: bool

    @property
    def runner(self) -> GitRunner:
        """Git runner confined to this repository's main worktree."""
        return GitRunner(self.worktree_root)


def bind_repository(repo_path: str) -> RepositoryContext:
    """Bind to a repository, or exit with a diagnostic."""
    repo = Path(repo_path).resolve()
    git = GitRunner(repo)

    result = git.run(["rev-parse", "--is-inside-work-tree"], check=False)
    if not result.ok or result.text.strip() != "true":
        print(f"Error: {repo} is not a Git repository", file=sys.stderr)
        sys.exit(1)

    git_dir_raw = git.run_text(["rev-parse", "--git-dir"])
    common_dir_raw = git.run_text(["rev-parse", "--git-common-dir"])
    bare = git.run_text(["rev-parse", "--is-bare-repository"]) == "true"

    git_dir = Path(git_dir_raw)
    if not git_dir.is_absolute():
        git_dir = repo / git_dir
    common_dir = Path(common_dir_raw)
    if not common_dir.is_absolute():
        common_dir = repo / common_dir

    return RepositoryContext(
        worktree_root=repo,
        git_dir=git_dir.resolve(),
        common_dir=common_dir.resolve(),
        is_bare=bare,
    )

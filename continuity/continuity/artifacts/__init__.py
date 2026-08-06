"""Read-only facts from Git and project collaboration artifacts."""

from .git import (
    commit_exists,
    current_branch,
    git_common_dir,
    git_dir,
    git_snapshot,
    head_commit,
    is_ancestor,
    origin_url,
    resolve_commit,
    structured_status,
)
from .project import ProjectFactsSource, unavailable_fact

__all__ = [
    "ProjectFactsSource",
    "commit_exists",
    "current_branch",
    "git_common_dir",
    "git_dir",
    "git_snapshot",
    "head_commit",
    "is_ancestor",
    "origin_url",
    "resolve_commit",
    "structured_status",
    "unavailable_fact",
]

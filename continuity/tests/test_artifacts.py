from __future__ import annotations

import subprocess

import continuity.artifacts.git as git_facts
import pytest
from continuity.artifacts import (
    commit_exists,
    is_ancestor,
    origin_url,
    structured_status,
)

from continuity import GitFactError

from .conftest import commit_file, git


def test_structured_git_status_preserves_index_worktree_rename_and_conflict(repo):
    commit_file(repo, "old.txt", "old\n", "add old path")
    commit_file(repo, "conflict.txt", "base\n", "add conflict target")
    git(repo, "checkout", "-qb", "other")
    commit_file(repo, "conflict.txt", "other\n", "other side")
    git(repo, "checkout", "-q", "main")
    commit_file(repo, "conflict.txt", "main\n", "main side")
    result = subprocess.run(
        ["git", "-C", str(repo), "merge", "other"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0

    (repo / "README.md").write_text("unstaged\n", encoding="utf-8")
    (repo / "added.py").write_text("staged = True\n", encoding="utf-8")
    git(repo, "add", "added.py")
    git(repo, "mv", "old.txt", "new.txt")

    by_path = {change["path"]: change for change in structured_status(repo)}
    assert by_path["README.md"] == {
        "index_status": " ",
        "worktree_status": "M",
        "path": "README.md",
        "conflict": False,
    }
    assert by_path["added.py"]["index_status"] == "A"
    assert by_path["added.py"]["worktree_status"] == " "
    assert by_path["new.txt"]["index_status"] == "R"
    assert by_path["new.txt"]["original_path"] == "old.txt"
    assert by_path["conflict.txt"] == {
        "index_status": "U",
        "worktree_status": "U",
        "path": "conflict.txt",
        "conflict": True,
    }


def test_git_fact_queries_distinguish_absence_from_execution_failure(repo, monkeypatch):
    head = git(repo, "rev-parse", "HEAD")
    assert commit_exists(repo, head) is True
    assert commit_exists(repo, "missing") is False
    assert origin_url(repo) is None
    git(repo, "remote", "add", "origin", "https://github.com/owner/repo.git")
    assert origin_url(repo) == "https://github.com/owner/repo.git"

    def failed_git(arguments, **kwargs):
        return subprocess.CompletedProcess(arguments, 2, "", "repository read failed")

    monkeypatch.setattr(git_facts.subprocess, "run", failed_git)
    with pytest.raises(GitFactError, match="repository read failed"):
        commit_exists(repo, head)
    with pytest.raises(GitFactError, match="repository read failed"):
        is_ancestor(repo, head, head)

    def missing_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(git_facts.subprocess, "run", missing_git)
    with pytest.raises(GitFactError, match="cannot execute Git"):
        commit_exists(repo, head)

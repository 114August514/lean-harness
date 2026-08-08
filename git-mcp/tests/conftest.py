"""Shared fixtures for git-mcp tests.

Uses real Git repositories (tmp_path fixtures) to verify
Git Contract semantics. No fake Git substitutes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from git_mcp.git_exec import GitRunner


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Execute git command in test setup/teardown."""
    return subprocess.run(
        ["git", *args],
        check=False,
        cwd=cwd,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(cwd),
            "LC_ALL": "C",
            "GIT_TERMINAL_PROMPT": "0",
        },
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """Create a minimal Git repository with one commit."""
    r = tmp_path / "repo"
    r.mkdir()
    run_git(["init"], r)
    run_git(["config", "user.name", "Test"], r)
    run_git(["config", "user.email", "test@test"], r)
    (r / "file.txt").write_text("hello\n")
    run_git(["add", "file.txt"], r)
    run_git(["commit", "-m", "initial"], r)
    return r


@pytest.fixture()
def git(repo: Path) -> GitRunner:
    """GitRunner bound to the test repository."""
    return GitRunner(repo)

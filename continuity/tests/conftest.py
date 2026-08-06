from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from continuity import ContextReconstructor, RecoveryLog, WorkEvents

from .fakes import FakeSharedStore


def git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def configure_user(repo: Path) -> None:
    git(repo, "config", "user.email", "continuity@example.test")
    git(repo, "config", "user.name", "Continuity Test")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    configure_user(path)
    (path / "README.md").write_text("# fixture\n", encoding="utf-8")
    git(path, "add", "README.md")
    git(path, "commit", "-qm", "initial")
    return path


@pytest.fixture
def system(repo: Path):
    shared = FakeSharedStore()
    recovery = RecoveryLog(repo)
    events = WorkEvents(repo, shared, recovery)
    context = ContextReconstructor(repo, events, recovery, project_facts=shared)
    return shared, recovery, events, context


def commit_file(repo: Path, name: str, content: str, message: str) -> str:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD")

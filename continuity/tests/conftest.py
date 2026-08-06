"""共享测试 fixture。

每个测试使用一个临时 Git 仓库（``tmp_path / "repo"``），
``parts`` 返回绑定到该仓库的 (store, recovery, worklog, resume)。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from continuity import JsonlStore, RecoveryLog, ResumeContext, WorkLog


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, f"git {' '.join(args)}: {out.stderr}"
    return out.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("# test repo\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-qm", "initial")
    return repo


@pytest.fixture
def parts(repo: Path):
    store = JsonlStore(repo)
    recovery = RecoveryLog(store)
    worklog = WorkLog(store)
    resume = ResumeContext(store, worklog, recovery)
    return store, recovery, worklog, resume


def commit_file(repo: Path, name: str, content: str, message: str) -> str:
    (repo / name).parent.mkdir(parents=True, exist_ok=True)
    (repo / name).write_text(content, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD")

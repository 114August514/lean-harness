"""JSON Lines 存储层。

默认把连续性记录放在仓库根目录的 ``docs/journal/`` 之下，人类可以直接翻开：

- 工作日志：``docs/journal/work-log/<work>/log.jsonl``，被 Git 跟踪、随仓库演进；
- 恢复日志：``docs/journal/recovery/<worktree>/log.jsonl``，由 ``.gitignore`` 排除，
  不进入 index / commit / PR diff。

存储根可用环境变量 ``CONTINUITY_ROOT`` 或 ``JsonlStore(journal_root=...)`` 覆盖，
以适应不同仓库布局。写入被中断时文件尾部可能出现不完整行，读取一律忽略
最后一个不完整尾部，并按字节偏移截断，保证此前记录完好。
"""

from __future__ import annotations

import errno
import fcntl
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path


class StoreError(Exception):
    """存储层错误：非 Git 仓库、JSON 不合法等。"""


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def git_common_dir(repo: Path) -> Path:
    out = _git(repo, "rev-parse", "--git-common-dir")
    if out.returncode != 0:
        raise StoreError(f"not a git repository: {repo}")
    p = Path(out.stdout.strip())
    # git 可能返回相对路径（相对于 repo），也可能返回绝对路径
    return (Path(repo).resolve() / p).resolve() if not p.is_absolute() else p


def git_dir(repo: Path) -> Path:
    """返回当前 worktree 自己的 .git 目录（worktree 与主仓库不同）。"""
    out = _git(repo, "rev-parse", "--git-dir")
    if out.returncode != 0:
        raise StoreError(f"not a git repository: {repo}")
    return Path(out.stdout.strip()).resolve()


def head_commit(repo: Path) -> str | None:
    out = _git(repo, "rev-parse", "HEAD")
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def commit_exists(repo: Path, commit: str) -> bool:
    out = _git(repo, "cat-file", "-t", commit)
    return out.returncode == 0 and out.stdout.strip() == "commit"


def resolve_commit(repo: Path, rev: str) -> str:
    """把任意 rev（HEAD、分支名、短 hash）解析为完整 commit hash。"""
    out = _git(repo, "rev-parse", rev)
    if out.returncode != 0:
        raise StoreError(f"cannot resolve commit: {rev}")
    return out.stdout.strip()


def is_ancestor(repo: Path, old: str, new: str) -> bool:
    out = _git(repo, "merge-base", "--is-ancestor", old, new)
    return out.returncode == 0


def current_branch(repo: Path) -> str | None:
    out = _git(repo, "branch", "--show-current")
    branch = out.stdout.strip()
    return branch or None


class JsonlStore:
    """``docs/journal/`` 下的 JSONL 读写。

    - 工作日志路径基于主 worktree 根（跨 worktree 共享，随仓库生命周期存在）；
    - 恢复日志路径同样基于主 worktree 根，但按 worktree 名分目录，
      并由 ``.gitignore`` 排除，不进入 index / commit / PR。
    """

    def __init__(self, repo: Path, journal_root: Path | None = None):
        self.repo = Path(repo).resolve()
        self._common = git_common_dir(self.repo)
        if journal_root is not None:
            self._journal = Path(journal_root).resolve()
        elif os.environ.get("CONTINUITY_ROOT"):
            self._journal = Path(os.environ["CONTINUITY_ROOT"]).resolve()
        else:
            self._journal = self._common.parent / "docs" / "journal"

    @property
    def journal_root(self) -> Path:
        return self._journal

    @property
    def work_log_dir(self) -> Path:
        return self._journal / "work-log"

    @property
    def recovery_dir(self) -> Path:
        return self._journal / "recovery" / self.repo.name

    def work_log_path(self, work: str) -> Path:
        return self.work_log_dir / work / "log.jsonl"

    def list_partitions(self) -> list[str]:
        if not self.work_log_dir.exists():
            return []
        return sorted(p.name for p in self.work_log_dir.iterdir() if p.is_dir())

    @staticmethod
    def _flock(fd: int) -> None:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
        except OSError as e:  # macOS on some filesystems
            if e.errno == errno.ENOTSUP:
                return
            raise

    def append(self, path: Path, record: dict) -> dict:
        """以 O_APPEND 追加一条记录；返回写入后的 record。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False)
        with open(path, "a", encoding="utf-8") as f:
            self._flock(f.fileno())
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
        return record

    def read(self, path: Path) -> list[dict]:
        """读取全部记录，忽略不完整尾部并将其截断。"""
        self.truncate_incomplete_tail(path)
        if not path.exists():
            return []
        records = []
        with open(path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    raise StoreError(f"corrupt record at {path}:{lineno}: {e}") from e
        return records

    @staticmethod
    def truncate_incomplete_tail(path: Path) -> bool:
        """若文件不以换行结尾，截断到最后一个换行处。返回是否发生了截断。"""
        if not path.exists():
            return False
        size = path.stat().st_size
        if size == 0:
            return False
        with open(path, "rb+") as f:
            f.seek(-1, os.SEEK_END)
            if f.read(1) == b"\n":
                return False
            data = path.read_bytes()
            idx = data.rfind(b"\n")
            f.truncate(idx + 1 if idx >= 0 else 0)
            return True

    def rewrite(self, path: Path, records: list[dict]) -> None:
        """原子重写整个文件（tmp + fsync + rename）。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for record in records:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

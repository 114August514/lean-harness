"""Git executable wrapper.

All Git invocations go through this module. Uses argv execution
(no shell), non-interactive environment, and NUL-separated output
where Git supports it.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GitResult:
    """Result of a Git command execution."""

    returncode: int
    stdout: bytes
    stderr: bytes

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def text(self) -> str:
        return self.stdout.decode("utf-8", errors="replace")

    @property
    def error_text(self) -> str:
        return self.stderr.decode("utf-8", errors="replace")

    def lines(self) -> list[str]:
        return self.text.splitlines()

    def nul_fields(self) -> list[bytes]:
        """Split stdout on NUL bytes, dropping the trailing empty element."""
        parts = self.stdout.split(b"\x00")
        if parts and parts[-1] == b"":
            parts.pop()
        return parts


class GitError(Exception):
    """A Git command failed."""

    def __init__(self, result: GitResult, args: list[str]) -> None:
        self.result = result
        self.args = args
        super().__init__(
            f"git {' '.join(args)}: exit {result.returncode}: {result.error_text}"
        )


class GitRunner:
    """Executes Git commands confined to a single repository."""

    def __init__(self, work_dir: Path) -> None:
        self.work_dir = work_dir.resolve()

    def run(
        self,
        args: list[str],
        *,
        check: bool = True,
        timeout: int = 30,
    ) -> GitResult:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/tmp"),
            "LC_ALL": "C",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "true",
            "GIT_PAGER": "cat",
            "PAGER": "cat",
        }
        try:
            proc = subprocess.run(
                ["git", *args],
                cwd=self.work_dir,
                env=env,
                capture_output=True,
                timeout=timeout,
            )
            result = GitResult(
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        except subprocess.TimeoutExpired:
            result = GitResult(
                returncode=-1,
                stdout=b"",
                stderr=f"git {' '.join(args)}: timeout after {timeout}s".encode(),
            )
        if check and not result.ok:
            raise GitError(result, args)
        return result

    def run_text(self, args: list[str], **kwargs) -> str:
        return self.run(args, **kwargs).text.strip()

    def run_lines(self, args: list[str], **kwargs) -> list[str]:
        return self.run(args, **kwargs).lines()

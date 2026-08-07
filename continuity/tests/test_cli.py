from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    root = Path(__file__).resolve().parents[2]
    return subprocess.run(
        [sys.executable, "-m", "continuity", *arguments],
        cwd=root / "continuity",
        capture_output=True,
        text=True,
        check=False,
    )


def test_module_entrypoint_and_local_status_without_github(repo):
    result = _run_cli("--help")
    assert result.returncode == 0
    assert "recovery" in result.stdout
    assert "shared" in result.stdout
    assert "resume" in result.stdout

    result = _run_cli("--repo", str(repo), "recovery", "status")
    assert result.returncode == 0, result.stderr
    assert '"binding": null' in result.stdout

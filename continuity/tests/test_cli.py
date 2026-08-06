from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_python_module_entrypoint_smoke():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "continuity", "--help"],
        cwd=root / "continuity",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Project-shared work events" in result.stdout
    assert "recovery" in result.stdout
    assert "shared" in result.stdout
    assert "resume" in result.stdout


def test_local_recovery_status_does_not_require_a_github_remote(repo):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "continuity",
            "--repo",
            str(repo),
            "recovery",
            "status",
        ],
        cwd=root / "continuity",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert '"binding": null' in result.stdout

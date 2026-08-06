"""Crash-safe primitives used only by the clone-local recovery layer."""

from __future__ import annotations

import errno
import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .errors import DamagedStateError, RecoveryError


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    """Persist JSON using tmp -> fsync -> replace -> directory fsync."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DamagedStateError(f"damaged recovery state at {path}: {error}") from error
    if not isinstance(value, dict):
        raise DamagedStateError(f"damaged recovery state at {path}: expected object")
    return value


def _lock(fd: int) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
    except OSError as error:
        if error.errno != errno.ENOTSUP:
            raise


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """Append one fsynced record; concurrent local writers cannot interleave lines."""

    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as stream:
        _lock(stream.fileno())
        stream.write(encoded)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read complete records, repairing only an interrupted final append."""

    if not path.exists():
        return []
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        last_newline = data.rfind(b"\n")
        complete_size = last_newline + 1 if last_newline >= 0 else 0
        with path.open("rb+") as stream:
            _lock(stream.fileno())
            stream.truncate(complete_size)
            stream.flush()
            os.fsync(stream.fileno())
        data = data[:complete_size]

    records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(data.splitlines(), start=1):
        if not raw_line:
            continue
        try:
            value = json.loads(raw_line)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise RecoveryError(
                f"damaged recovery record at {path}:{line_number}: {error}"
            ) from error
        if not isinstance(value, dict):
            raise RecoveryError(
                f"damaged recovery record at {path}:{line_number}: expected object"
            )
        records.append(value)
    return records

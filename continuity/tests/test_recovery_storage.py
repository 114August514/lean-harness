from __future__ import annotations

import fcntl
import os
import threading

import continuity.recovery.storage as local_storage
import pytest
from continuity.recovery.storage import append_jsonl, atomic_write_json, read_jsonl

from continuity import DamagedJournalError, DamagedStateError


def test_state_updates_are_atomic_and_damage_is_diagnostic(recovery, monkeypatch):
    original = recovery.bind("issue-5", "cycle-1")

    def interrupted_replace(source, destination):
        raise OSError("simulated interruption before atomic replace")

    monkeypatch.setattr(local_storage.os, "replace", interrupted_replace)
    with pytest.raises(OSError, match="simulated interruption"):
        recovery.pause()

    assert recovery.status()["binding"] == original

    recovery.state_path.write_text('{"binding_id":', encoding="utf-8")
    with pytest.raises(DamagedStateError, match="damaged recovery state"):
        recovery.status()


def test_recovery_rejects_semantically_invalid_state_and_journal(recovery):
    state = recovery.bind("issue-5", "cycle-1")

    invalid_state = {key: value for key, value in state.items() if key != "work"}
    atomic_write_json(recovery.state_path, invalid_state)
    with pytest.raises(DamagedStateError, match="invalid work"):
        recovery.status()

    atomic_write_json(recovery.state_path, state)
    invalid_record = {**recovery.records()[0], "binding_id": "bind-wrong"}
    append_jsonl(recovery.log_path, invalid_record)
    with pytest.raises(DamagedJournalError, match="does not match journal binding"):
        recovery.status()


def test_jsonl_repair_rechecks_tail_after_waiting_for_writer(tmp_path, monkeypatch):
    path = tmp_path / "recovery.jsonl"
    writer = path.open("wb")
    fcntl.flock(writer.fileno(), fcntl.LOCK_EX)
    writer.write(b'{"record_id":"rec-1"')
    writer.flush()
    os.fsync(writer.fileno())

    reader_waiting = threading.Event()
    original_lock = local_storage._lock

    def announcing_lock(fd):
        reader_waiting.set()
        original_lock(fd)

    monkeypatch.setattr(local_storage, "_lock", announcing_lock)
    result = {}

    def read_records():
        result["records"] = read_jsonl(path)

    reader = threading.Thread(target=read_records)
    try:
        reader.start()
        assert reader_waiting.wait(timeout=2)
        writer.write(b',"value":1}\n')
        writer.flush()
        os.fsync(writer.fileno())
    finally:
        fcntl.flock(writer.fileno(), fcntl.LOCK_UN)
        writer.close()
    reader.join(timeout=2)

    assert not reader.is_alive()
    assert result["records"] == [{"record_id": "rec-1", "value": 1}]


def test_first_jsonl_append_fsyncs_its_directory(tmp_path, monkeypatch):
    path = tmp_path / "new-binding" / "recovery.jsonl"
    fsynced = []
    monkeypatch.setattr(local_storage, "_fsync_directory", fsynced.append)

    append_jsonl(path, {"record_id": "rec-first"})

    assert path.parent in fsynced

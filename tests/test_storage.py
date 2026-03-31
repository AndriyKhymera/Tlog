"""
Tests for tlog.storage — uses TLOG_DIR env var to isolate from ~/.tlog
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_tlog_dir(tmp_path, monkeypatch):
    """Redirect all storage operations to a temp directory."""
    tlog_dir = tmp_path / "tlog"
    monkeypatch.setenv("TLOG_DIR", str(tlog_dir))

    # Re-import storage so the module-level TLOG_DIR picks up the env var
    import importlib
    import tlog.storage as storage_mod
    importlib.reload(storage_mod)
    monkeypatch.setattr("tlog.storage.TLOG_DIR", tlog_dir)
    monkeypatch.setattr("tlog.storage.ENTRIES_FILE", tlog_dir / "entries.jsonl")
    monkeypatch.setattr("tlog.storage.CURRENT_FILE", tlog_dir / "current.json")

    return tlog_dir


@pytest.fixture
def storage():
    from tlog import storage
    return storage


@pytest.fixture
def sample_entry():
    from tlog.models import TimeEntry
    return TimeEntry(
        start=datetime(2026, 3, 19, 9, 0, tzinfo=timezone.utc),
        end=datetime(2026, 3, 19, 12, 30, tzinfo=timezone.utc),
        project="ClientA",
        description="Feature X",
        tags=["backend"],
    )


# ─── save_entry / load_entries ────────────────────────────────────────────────

def test_load_entries_empty(storage):
    assert storage.load_entries() == []


def test_save_and_load_one_entry(storage, sample_entry):
    storage.save_entry(sample_entry)
    entries = storage.load_entries()

    assert len(entries) == 1
    e = entries[0]
    assert e.project == "ClientA"
    assert e.description == "Feature X"
    assert e.tags == ["backend"]
    assert e.start == sample_entry.start
    assert e.end == sample_entry.end


def test_save_multiple_entries_preserves_order(storage):
    from tlog.models import TimeEntry
    e1 = TimeEntry(
        start=datetime(2026, 3, 19, 9, 0, tzinfo=timezone.utc),
        end=datetime(2026, 3, 19, 10, 0, tzinfo=timezone.utc),
        project="P1", description="D1",
    )
    e2 = TimeEntry(
        start=datetime(2026, 3, 19, 11, 0, tzinfo=timezone.utc),
        end=datetime(2026, 3, 19, 12, 0, tzinfo=timezone.utc),
        project="P2", description="D2",
    )
    storage.save_entry(e1)
    storage.save_entry(e2)

    entries = storage.load_entries()
    assert len(entries) == 2
    assert entries[0].project == "P1"
    assert entries[1].project == "P2"


def test_corrupt_line_is_skipped(storage, sample_entry, isolated_tlog_dir):
    """A corrupt JSONL line should be silently skipped, not crash."""
    from tlog import storage as s
    s.save_entry(sample_entry)

    entries_file = isolated_tlog_dir / "entries.jsonl"
    with entries_file.open("a") as f:
        f.write("NOT VALID JSON\n")

    s.save_entry(sample_entry)  # append a valid one after the corrupt line

    entries = s.load_entries()
    assert len(entries) == 2  # only the two valid ones


# ─── current session ──────────────────────────────────────────────────────────

def test_get_current_when_nothing_running(storage):
    assert storage.get_current() is None


def test_set_and_get_current(storage):
    now = datetime(2026, 3, 19, 9, 0, tzinfo=timezone.utc)
    storage.set_current(
        project="Alpha",
        description="Writing tests",
        tags=["dev"],
        start=now,
    )
    current = storage.get_current()
    assert current is not None
    assert current["project"] == "Alpha"
    assert current["description"] == "Writing tests"
    assert current["tags"] == ["dev"]
    assert datetime.fromisoformat(current["start"]) == now


def test_clear_current(storage):
    now = datetime(2026, 3, 19, 9, 0, tzinfo=timezone.utc)
    storage.set_current("P", "D", [], now)
    assert storage.get_current() is not None
    storage.clear_current()
    assert storage.get_current() is None


def test_clear_current_when_already_clear_is_safe(storage):
    storage.clear_current()  # should not raise


def test_current_file_is_valid_json(storage, isolated_tlog_dir):
    now = datetime(2026, 3, 19, 9, 0, tzinfo=timezone.utc)
    storage.set_current("P", "D", ["t1"], now)
    current_file = isolated_tlog_dir / "current.json"
    data = json.loads(current_file.read_text())
    assert data["project"] == "P"
    assert data["tags"] == ["t1"]


# ─── TimeEntry model ──────────────────────────────────────────────────────────

def test_time_entry_duration(sample_entry):
    from datetime import timedelta
    assert sample_entry.duration == timedelta(hours=3, minutes=30)


def test_time_entry_round_trip(sample_entry):
    from tlog.models import TimeEntry
    restored = TimeEntry.from_dict(sample_entry.to_dict())
    assert restored.project == sample_entry.project
    assert restored.start == sample_entry.start
    assert restored.end == sample_entry.end
    assert restored.tags == sample_entry.tags


def test_time_entry_json_round_trip(sample_entry):
    from tlog.models import TimeEntry
    restored = TimeEntry.from_json(sample_entry.to_json())
    assert restored.description == sample_entry.description

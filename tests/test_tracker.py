"""
Tests for tlog.tracker — storage is patched so no disk I/O happens.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from tlog.models import TimeEntry


@pytest.fixture
def mock_storage():
    """Return a mock storage module with sensible defaults."""
    m = MagicMock()
    m.get_current.return_value = None
    return m


def _make_current(project="ClientA", description="Feature X", tags=None, offset_minutes=30):
    """Helper: a current-session dict started `offset_minutes` ago."""
    start = datetime.now(tz=timezone.utc) - timedelta(minutes=offset_minutes)
    return {
        "project": project,
        "description": description,
        "tags": tags or [],
        "start": start.isoformat(),
    }


# ─── start ────────────────────────────────────────────────────────────────────

def test_start_when_nothing_running(mock_storage):
    with patch("tlog.tracker.storage", mock_storage):
        from tlog import tracker
        session, was_stopped = tracker.start("Alpha", "Task 1", ["dev"])

    assert session["project"] == "Alpha"
    assert session["description"] == "Task 1"
    assert session["tags"] == ["dev"]
    assert was_stopped is False
    mock_storage.set_current.assert_called_once()
    mock_storage.save_entry.assert_not_called()


def test_start_auto_stops_existing_session(mock_storage):
    mock_storage.get_current.return_value = _make_current("OldProject", "Old task")

    with patch("tlog.tracker.storage", mock_storage):
        from tlog import tracker
        session, was_stopped = tracker.start("NewProject", "New task", [])

    assert was_stopped is True
    mock_storage.save_entry.assert_called_once()  # old session was saved
    mock_storage.set_current.assert_called_once()  # new session was started


# ─── stop ─────────────────────────────────────────────────────────────────────

def test_stop_when_nothing_running(mock_storage):
    mock_storage.get_current.return_value = None

    with patch("tlog.tracker.storage", mock_storage):
        from tlog import tracker
        result = tracker.stop()

    assert result is None
    mock_storage.save_entry.assert_not_called()


def test_stop_saves_entry_and_clears_current(mock_storage):
    mock_storage.get_current.return_value = _make_current()

    with patch("tlog.tracker.storage", mock_storage):
        from tlog import tracker
        entry = tracker.stop()

    assert isinstance(entry, TimeEntry)
    assert entry.project == "ClientA"
    assert entry.duration > timedelta(0)
    mock_storage.save_entry.assert_called_once_with(entry)
    mock_storage.clear_current.assert_called_once()


# ─── cancel ───────────────────────────────────────────────────────────────────

def test_cancel_when_nothing_running(mock_storage):
    mock_storage.get_current.return_value = None

    with patch("tlog.tracker.storage", mock_storage):
        from tlog import tracker
        result = tracker.cancel()

    assert result is None
    mock_storage.clear_current.assert_not_called()


def test_cancel_discards_without_saving(mock_storage):
    current = _make_current()
    mock_storage.get_current.return_value = current

    with patch("tlog.tracker.storage", mock_storage):
        from tlog import tracker
        result = tracker.cancel()

    assert result is not None
    assert result["project"] == "ClientA"
    mock_storage.save_entry.assert_not_called()  # not saved!
    mock_storage.clear_current.assert_called_once()


# ─── status ───────────────────────────────────────────────────────────────────

def test_status_when_nothing_running(mock_storage):
    mock_storage.get_current.return_value = None

    with patch("tlog.tracker.storage", mock_storage):
        from tlog import tracker
        result = tracker.status()

    assert result is None


def test_status_returns_elapsed(mock_storage):
    mock_storage.get_current.return_value = _make_current(offset_minutes=45)

    with patch("tlog.tracker.storage", mock_storage):
        from tlog import tracker
        result = tracker.status()

    assert result is not None
    assert "elapsed" in result
    # Elapsed should be approximately 45 minutes
    assert timedelta(minutes=44) < result["elapsed"] < timedelta(minutes=46)

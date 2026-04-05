"""
Tests for the `tlog add` CLI command.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from typer.testing import CliRunner

from tlog.main import app, _parse_duration

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_tlog_dir(tmp_path, monkeypatch):
    """Redirect all storage operations to a temp directory."""
    tlog_dir = tmp_path / "tlog"
    monkeypatch.setenv("TLOG_DIR", str(tlog_dir))

    import importlib
    import tlog.storage as storage_mod
    importlib.reload(storage_mod)
    monkeypatch.setattr("tlog.storage.TLOG_DIR", tlog_dir)
    monkeypatch.setattr("tlog.storage.ENTRIES_FILE", tlog_dir / "entries.jsonl")
    monkeypatch.setattr("tlog.storage.CURRENT_FILE", tlog_dir / "current.json")

    return tlog_dir


# ─── _parse_duration unit tests ───────────────────────────────────────────────

class TestParseDuration:
    def test_hours_and_minutes(self):
        assert _parse_duration("2h30m") == timedelta(hours=2, minutes=30)

    def test_hours_only(self):
        assert _parse_duration("1h") == timedelta(hours=1)

    def test_minutes_only(self):
        assert _parse_duration("45m") == timedelta(minutes=45)

    def test_plain_integer_is_minutes(self):
        assert _parse_duration("90") == timedelta(minutes=90)

    def test_decimal_hours(self):
        assert _parse_duration("1.5h") == timedelta(hours=1, minutes=30)

    def test_colon_format(self):
        assert _parse_duration("1:30") == timedelta(hours=1, minutes=30)

    def test_colon_format_zero_hours(self):
        assert _parse_duration("0:45") == timedelta(minutes=45)


# ─── add command tests ────────────────────────────────────────────────────────

class TestAddCommand:
    def test_add_start_and_end(self, isolated_tlog_dir):
        result = runner.invoke(app, [
            "add", "ClientA", "Bug fix",
            "--start", "09:00", "--end", "11:00",
            "--date", "2026-03-31",
        ])
        assert result.exit_code == 0
        import tlog.storage as storage
        entries = storage.load_entries()
        assert len(entries) == 1
        e = entries[0]
        assert e.project == "ClientA"
        assert e.description == "Bug fix"
        assert e.start == datetime(2026, 3, 31, 9, 0)
        assert e.end == datetime(2026, 3, 31, 11, 0)

    def test_add_start_and_duration(self, isolated_tlog_dir):
        result = runner.invoke(app, [
            "add", "ClientA", "Meeting",
            "--start", "09:00", "--duration", "1h30m",
            "--date", "2026-03-31",
        ])
        assert result.exit_code == 0
        import tlog.storage as storage
        entries = storage.load_entries()
        assert entries[0].end == datetime(2026, 3, 31, 10, 30)

    def test_add_end_and_duration(self, isolated_tlog_dir):
        result = runner.invoke(app, [
            "add", "ClientA", "Design review",
            "--end", "12:00", "--duration", "2h",
            "--date", "2026-03-31",
        ])
        assert result.exit_code == 0
        import tlog.storage as storage
        entries = storage.load_entries()
        assert entries[0].start == datetime(2026, 3, 31, 10, 0)
        assert entries[0].end == datetime(2026, 3, 31, 12, 0)

    def test_add_duration_only_ends_now(self, isolated_tlog_dir):
        from datetime import date
        before = datetime.now().replace(second=0, microsecond=0)
        result = runner.invoke(app, [
            "add", "ClientA", "Quick task",
            "--duration", "30m",
        ])
        after = datetime.now().replace(second=0, microsecond=0)
        assert result.exit_code == 0
        import tlog.storage as storage
        entries = storage.load_entries()
        e = entries[0]
        assert e.duration == timedelta(minutes=30)
        assert e.start.date() == date.today()
        # end should be within [before, after+1min] window
        assert before - timedelta(minutes=1) <= e.end <= after + timedelta(minutes=1)

    def test_add_defaults_to_today(self):
        from datetime import date
        result = runner.invoke(app, [
            "add", "ClientA", "Work",
            "--start", "10:00", "--end", "12:00",
        ])
        assert result.exit_code == 0
        import tlog.storage as storage
        entries = storage.load_entries()
        assert entries[0].start.date() == date.today()

    def test_add_with_tags(self, isolated_tlog_dir):
        result = runner.invoke(app, [
            "add", "ClientA", "Frontend work",
            "--start", "14:00", "--end", "16:30",
            "--date", "2026-03-31",
            "--tag", "frontend", "--tag", "react",
        ])
        assert result.exit_code == 0
        import tlog.storage as storage
        entries = storage.load_entries()
        assert entries[0].tags == ["frontend", "react"]

    def test_add_duration_is_correct(self, isolated_tlog_dir):
        result = runner.invoke(app, [
            "add", "ClientA", "Meeting",
            "--start", "09:00", "--end", "10:30",
            "--date", "2026-03-31",
        ])
        assert result.exit_code == 0
        import tlog.storage as storage
        entries = storage.load_entries()
        assert entries[0].duration == timedelta(hours=1, minutes=30)

    def test_add_midnight_crossing(self, isolated_tlog_dir):
        result = runner.invoke(app, [
            "add", "ClientA", "Late night session",
            "--start", "23:00", "--end", "01:00",
            "--date", "2026-03-31",
        ])
        assert result.exit_code == 0
        import tlog.storage as storage
        entries = storage.load_entries()
        assert entries[0].duration == timedelta(hours=2)
        assert entries[0].end.date().isoformat() == "2026-04-01"

    def test_add_no_time_info_fails(self):
        result = runner.invoke(app, [
            "add", "ClientA", "Work",
        ])
        assert result.exit_code != 0

    def test_add_only_start_fails(self):
        result = runner.invoke(app, [
            "add", "ClientA", "Work", "--start", "09:00",
        ])
        assert result.exit_code != 0

    def test_add_invalid_start_time(self):
        result = runner.invoke(app, [
            "add", "ClientA", "Work",
            "--start", "not-a-time", "--end", "10:00",
        ])
        assert result.exit_code != 0

    def test_add_invalid_date(self):
        result = runner.invoke(app, [
            "add", "ClientA", "Work",
            "--start", "09:00", "--end", "10:00",
            "--date", "31-03-2026",
        ])
        assert result.exit_code != 0

    def test_add_output_confirms_entry(self, isolated_tlog_dir):
        result = runner.invoke(app, [
            "add", "ClientA", "Design session",
            "--start", "13:00", "--end", "15:00",
            "--date", "2026-03-31",
        ])
        assert result.exit_code == 0
        assert "Added" in result.output
        assert "ClientA" in result.output
        assert "Design session" in result.output
        assert "2h" in result.output



@pytest.fixture(autouse=True)
def isolated_tlog_dir(tmp_path, monkeypatch):
    """Redirect all storage operations to a temp directory."""
    tlog_dir = tmp_path / "tlog"
    monkeypatch.setenv("TLOG_DIR", str(tlog_dir))

    import importlib
    import tlog.storage as storage_mod
    importlib.reload(storage_mod)
    monkeypatch.setattr("tlog.storage.TLOG_DIR", tlog_dir)
    monkeypatch.setattr("tlog.storage.ENTRIES_FILE", tlog_dir / "entries.jsonl")
    monkeypatch.setattr("tlog.storage.CURRENT_FILE", tlog_dir / "current.json")

    return tlog_dir


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestAddCommand:
    def test_add_saves_entry(self, isolated_tlog_dir):
        result = runner.invoke(app, [
            "add", "ClientA", "Bug fix",
            "--start", "09:00", "--end", "11:00",
            "--date", "2026-03-31",
        ])
        assert result.exit_code == 0
        import tlog.storage as storage
        entries = storage.load_entries()
        assert len(entries) == 1
        e = entries[0]
        assert e.project == "ClientA"
        assert e.description == "Bug fix"
        assert e.start == datetime(2026, 3, 31, 9, 0)
        assert e.end == datetime(2026, 3, 31, 11, 0)

    def test_add_defaults_to_today(self):
        from datetime import date
        result = runner.invoke(app, [
            "add", "ClientA", "Work",
            "--start", "10:00", "--end", "12:00",
        ])
        assert result.exit_code == 0
        import tlog.storage as storage
        entries = storage.load_entries()
        assert entries[0].start.date() == date.today()

    def test_add_with_tags(self, isolated_tlog_dir):
        result = runner.invoke(app, [
            "add", "ClientA", "Frontend work",
            "--start", "14:00", "--end", "16:30",
            "--date", "2026-03-31",
            "--tag", "frontend", "--tag", "react",
        ])
        assert result.exit_code == 0
        import tlog.storage as storage
        entries = storage.load_entries()
        assert entries[0].tags == ["frontend", "react"]

    def test_add_duration_is_correct(self, isolated_tlog_dir):
        from datetime import timedelta
        result = runner.invoke(app, [
            "add", "ClientA", "Meeting",
            "--start", "09:00", "--end", "10:30",
            "--date", "2026-03-31",
        ])
        assert result.exit_code == 0
        import tlog.storage as storage
        entries = storage.load_entries()
        assert entries[0].duration == timedelta(hours=1, minutes=30)

    def test_add_midnight_crossing(self, isolated_tlog_dir):
        """end < start should be treated as crossing midnight."""
        result = runner.invoke(app, [
            "add", "ClientA", "Late night session",
            "--start", "23:00", "--end", "01:00",
            "--date", "2026-03-31",
        ])
        assert result.exit_code == 0
        import tlog.storage as storage
        from datetime import timedelta
        entries = storage.load_entries()
        assert entries[0].duration == timedelta(hours=2)
        assert entries[0].end.date().isoformat() == "2026-04-01"

    def test_add_invalid_start_time(self):
        result = runner.invoke(app, [
            "add", "ClientA", "Work",
            "--start", "not-a-time", "--end", "10:00",
        ])
        assert result.exit_code != 0

    def test_add_invalid_date(self):
        result = runner.invoke(app, [
            "add", "ClientA", "Work",
            "--start", "09:00", "--end", "10:00",
            "--date", "31-03-2026",
        ])
        assert result.exit_code != 0

    def test_add_output_confirms_entry(self, isolated_tlog_dir):
        result = runner.invoke(app, [
            "add", "ClientA", "Design session",
            "--start", "13:00", "--end", "15:00",
            "--date", "2026-03-31",
        ])
        assert result.exit_code == 0
        assert "Added" in result.output
        assert "ClientA" in result.output
        assert "Design session" in result.output
        assert "2h" in result.output

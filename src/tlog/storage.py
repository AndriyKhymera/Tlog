from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

from tlog.models import TimeEntry

# Allow override via env var — useful for tests and advanced users
TLOG_DIR = Path(os.environ.get("TLOG_DIR", Path.home() / ".tlog"))
ENTRIES_FILE = TLOG_DIR / "entries.jsonl"
CURRENT_FILE = TLOG_DIR / "current.json"
CONFIG_FILE = TLOG_DIR / "config.toml"


def _ensure_dir() -> None:
    TLOG_DIR.mkdir(parents=True, exist_ok=True)


# ─── Completed entries (JSONL) ────────────────────────────────────────────────

def load_entries() -> list[TimeEntry]:
    """Load all completed entries from the journal file."""
    _ensure_dir()
    if not ENTRIES_FILE.exists():
        return []
    entries: list[TimeEntry] = []
    with ENTRIES_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(TimeEntry.from_json(line))
                except (json.JSONDecodeError, KeyError):
                    # Corrupt line — skip rather than crash; user can fix with editor
                    pass
    return entries


def save_entry(entry: TimeEntry) -> None:
    """Append a completed entry to the journal file (atomic append)."""
    _ensure_dir()
    with ENTRIES_FILE.open("a", encoding="utf-8") as f:
        f.write(entry.to_json() + "\n")


# ─── Active session ───────────────────────────────────────────────────────────

def get_current() -> dict | None:
    """Return the active session dict, or None if nothing is running."""
    _ensure_dir()
    if not CURRENT_FILE.exists():
        return None
    try:
        with CURRENT_FILE.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def set_current(
    project: str,
    description: str,
    tags: list[str],
    start: datetime,
) -> None:
    """Atomically write the active session file."""
    _ensure_dir()
    data = {
        "project": project,
        "description": description,
        "tags": tags,
        "start": start.isoformat(),
    }
    tmp_fd, tmp_path_str = tempfile.mkstemp(dir=str(TLOG_DIR), prefix=".current.")
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, CURRENT_FILE)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def clear_current() -> None:
    """Remove the active session file."""
    CURRENT_FILE.unlink(missing_ok=True)


# ─── Configuration ────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Load ~/.tlog/config.toml. Returns empty dict if file doesn't exist."""
    if not CONFIG_FILE.exists():
        return {}
    with CONFIG_FILE.open("rb") as f:
        return tomllib.load(f)


def get_reporter_config(reporter_name: str) -> dict:
    """Return the config section for a specific reporter."""
    config = load_config()
    return config.get("reporters", {}).get(reporter_name, {})

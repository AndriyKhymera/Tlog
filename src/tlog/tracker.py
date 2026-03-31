from __future__ import annotations

from datetime import datetime, timezone

from tlog import storage
from tlog.models import TimeEntry


def _now() -> datetime:
    """Current time as a timezone-aware local datetime."""
    return datetime.now(tz=timezone.utc).astimezone()


# ─── Core operations ──────────────────────────────────────────────────────────

def start(project: str, description: str, tags: list[str]) -> tuple[dict, bool]:
    """
    Start a new session.

    If a session is already running it is automatically stopped and saved first
    (same behaviour as bartib — no need for an explicit stop).

    Returns (session_dict, was_previous_stopped).
    """
    now = _now()
    current = storage.get_current()
    was_previous_stopped = False

    if current:
        _commit_current(current, end=now)
        was_previous_stopped = True

    storage.set_current(
        project=project,
        description=description,
        tags=tags,
        start=now,
    )
    return {"project": project, "description": description, "tags": tags, "start": now}, was_previous_stopped


def stop() -> TimeEntry | None:
    """
    Stop the running session and save it.
    Returns the saved TimeEntry, or None if nothing was running.
    """
    current = storage.get_current()
    if not current:
        return None
    return _commit_current(current, end=_now())


def cancel() -> dict | None:
    """
    Discard the running session without saving it.
    Returns the discarded session dict, or None if nothing was running.
    """
    current = storage.get_current()
    if not current:
        return None
    storage.clear_current()
    return current


def status() -> dict | None:
    """
    Return the running session with an 'elapsed' timedelta injected,
    or None if nothing is running.
    """
    current = storage.get_current()
    if not current:
        return None
    start = datetime.fromisoformat(current["start"])
    elapsed = _now() - start
    return {**current, "elapsed": elapsed}


# ─── Internal ─────────────────────────────────────────────────────────────────

def _commit_current(current: dict, end: datetime) -> TimeEntry:
    """Save the active session as a completed entry and clear it."""
    start = datetime.fromisoformat(current["start"])
    entry = TimeEntry(
        start=start,
        end=end,
        project=current["project"],
        description=current["description"],
        tags=current.get("tags", []),
    )
    storage.save_entry(entry)
    storage.clear_current()
    return entry

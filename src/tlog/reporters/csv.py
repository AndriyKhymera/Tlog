from __future__ import annotations

import csv
import sys
from pathlib import Path

from tlog.models import TimeEntry


class CsvReporter:
    """Built-in CSV reporter — ships free with tlog."""

    name = "csv"
    description = "Export time entries to a CSV file (built-in)"

    _FIELDS = [
        "date",
        "start",
        "end",
        "duration_minutes",
        "project",
        "description",
        "tags",
    ]

    def configure(self, config: dict) -> None:
        pass  # No configuration options for the basic CSV reporter

    def validate(self, entries: list[TimeEntry]) -> list[str]:
        return []  # Always valid

    def export(self, entries: list[TimeEntry], output: Path | None) -> None:
        f = output.open("w", newline="", encoding="utf-8") if output else sys.stdout
        try:
            writer = csv.DictWriter(f, fieldnames=self._FIELDS)
            writer.writeheader()
            for entry in entries:
                total_seconds = entry.duration.total_seconds()
                writer.writerow(
                    {
                        "date": entry.start.date().isoformat(),
                        "start": entry.start.strftime("%H:%M:%S"),
                        "end": entry.end.strftime("%H:%M:%S"),
                        "duration_minutes": round(total_seconds / 60, 2),
                        "project": entry.project,
                        "description": entry.description,
                        "tags": ",".join(entry.tags),
                    }
                )
        finally:
            if output:
                f.close()

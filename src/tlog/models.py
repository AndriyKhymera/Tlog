from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class TimeEntry:
    """A single completed time tracking entry."""

    start: datetime
    end: datetime
    project: str
    description: str
    tags: list[str] = field(default_factory=list)

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    def to_dict(self) -> dict:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "project": self.project,
            "description": self.description,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TimeEntry:
        return cls(
            start=datetime.fromisoformat(data["start"]),
            end=datetime.fromisoformat(data["end"]),
            project=data["project"],
            description=data["description"],
            tags=data.get("tags", []),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, line: str) -> TimeEntry:
        return cls.from_dict(json.loads(line))

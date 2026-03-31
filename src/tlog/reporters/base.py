from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from tlog.models import TimeEntry


@runtime_checkable
class Reporter(Protocol):
    """
    The plugin contract that every tlog reporter must satisfy.

    Plugin authors implement this class in their package and register it
    via a pyproject.toml entry point::

        [project.entry-points."tlog.reporters"]
        my_reporter = "my_package.reporter:MyReporter"

    Users install the plugin with::

        pipx inject tlog tlog-my-reporter
    """

    #: Short identifier used on the CLI: ``tlog report --reporter <name>``
    name: str

    #: One-line human description shown in ``tlog plugins list``
    description: str

    def configure(self, config: dict) -> None:
        """
        Apply configuration values.

        Called before validate/export. ``config`` is the reporter's section
        from ``~/.tlog/config.toml``, e.g. ``{"contract_id": "xxx"}``.
        """
        ...

    def validate(self, entries: list[TimeEntry]) -> list[str]:
        """
        Return a list of warning strings.

        An empty list means the entries are valid for this reporter.
        Warnings are printed to the user before export; export is not blocked.
        """
        ...

    def export(self, entries: list[TimeEntry], output: Path | None) -> None:
        """
        Write the report.

        If ``output`` is None, write to stdout.
        If ``output`` is a Path, write to that file (create/overwrite).
        """
        ...

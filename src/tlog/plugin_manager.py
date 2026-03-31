from __future__ import annotations

import subprocess
from importlib.metadata import entry_points

from tlog.reporters.base import Reporter
from tlog.reporters.csv import CsvReporter

# Built-in reporters: always present, no installation needed
_BUILTINS: dict[str, Reporter] = {
    CsvReporter.name: CsvReporter(),
}


def get_reporter(name: str) -> Reporter | None:
    """
    Return the reporter instance for the given name, or None if not found.

    Resolution order: built-ins first, then installed plugin entry points.
    """
    if name in _BUILTINS:
        return _BUILTINS[name]

    for ep in entry_points(group="tlog.reporters"):
        if ep.name == name:
            cls = ep.load()
            return cls()

    return None


def list_reporters() -> list[dict]:
    """
    Return metadata for all available reporters.

    Each dict has keys: name, description, source ("built-in" or "plugin").
    """
    reporters = [
        {"name": r.name, "description": r.description, "source": "built-in"}
        for r in _BUILTINS.values()
    ]

    for ep in entry_points(group="tlog.reporters"):
        try:
            cls = ep.load()
            reporters.append(
                {
                    "name": ep.name,
                    "description": getattr(cls, "description", ""),
                    "source": "plugin",
                }
            )
        except Exception as exc:
            reporters.append(
                {
                    "name": ep.name,
                    "description": f"(failed to load: {exc})",
                    "source": "plugin",
                }
            )

    return reporters


def install_plugin(package: str) -> bool:
    """
    Install a plugin into the current pipx environment via ``pipx inject``.

    ``package`` may be a PyPI package name, a local wheel path, or a URL.
    Returns True on success.
    """
    result = subprocess.run(
        ["pipx", "inject", "tlog", package],
        check=False,
    )
    return result.returncode == 0

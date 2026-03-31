from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import box

from tlog import tracker, storage
from tlog.models import TimeEntry
from tlog import plugin_manager

app = typer.Typer(
    name="tlog",
    help="A CLI time tracker with extensible reporter plugins.",
    add_completion=False,
    no_args_is_help=True,
)
plugins_app = typer.Typer(help="Manage reporter plugins.")
app.add_typer(plugins_app, name="plugins")

console = Console()
err_console = Console(stderr=True)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fmt_duration(td: timedelta) -> str:
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        return "0m"
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def _filter_entries(
    entries: list[TimeEntry],
    *,
    today: bool = False,
    yesterday: bool = False,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    project: Optional[str] = None,
) -> list[TimeEntry]:
    today_date = date.today()

    if today:
        from_date = today_date
        to_date = today_date
    elif yesterday:
        y = today_date - timedelta(days=1)
        from_date = y
        to_date = y

    result = entries
    if from_date:
        result = [e for e in result if e.start.date() >= from_date]
    if to_date:
        result = [e for e in result if e.start.date() <= to_date]
    if project:
        result = [e for e in result if e.project.lower() == project.lower()]
    return result


def _parse_date(value: str | None, name: str = "date") -> date | None:
    """Parse YYYY-MM-DD string into a date, or abort with a clear message."""
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        _abort(f"Invalid {name} format: {value!r}. Expected YYYY-MM-DD.")


def _parse_time(value: str, name: str = "time") -> time:
    """Parse HH:MM or HH:MM:SS string into a time, or abort with a clear message."""
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            pass
    _abort(f"Invalid {name} format: {value!r}. Expected HH:MM.")


def _abort(message: str) -> None:
    err_console.print(f"[bold red]Error:[/bold red] {message}")
    raise typer.Exit(code=1)


# ─── Tracking commands ────────────────────────────────────────────────────────

@app.command()
def start(
    project: Annotated[str, typer.Argument(help="Project name")],
    description: Annotated[str, typer.Argument(help="What you are working on")],
    tag: Annotated[Optional[list[str]], typer.Option("--tag", "-t", help="Tag (repeatable)")] = None,
) -> None:
    """Start tracking time on a task. Stops any running session automatically."""
    tags = tag or []
    session, was_stopped = tracker.start(project, description, tags)

    if was_stopped:
        console.print("[yellow]⏹  Stopped previous session.[/yellow]")

    tag_str = f"  [{', '.join(tags)}]" if tags else ""
    console.print(
        f"[green]▶  Started:[/green] [bold]{project}[/bold] — {description}{tag_str}\n"
        f"   [dim]at {session['start'].strftime('%H:%M:%S')}[/dim]"
    )


@app.command()
def stop() -> None:
    """Stop the current session and save it."""
    entry = tracker.stop()
    if not entry:
        _abort("No session is running. Use [bold]tlog start[/bold] to begin one.")

    console.print(
        f"[green]⏹  Stopped:[/green] [bold]{entry.project}[/bold] — {entry.description}\n"
        f"   [dim]Duration: {_fmt_duration(entry.duration)}[/dim]"
    )


@app.command()
def cancel() -> None:
    """Discard the running session without saving it."""
    session = tracker.cancel()
    if not session:
        _abort("No session is running.")

    console.print(
        f"[yellow]✕  Cancelled:[/yellow] [bold]{session['project']}[/bold] — {session['description']}"
    )


@app.command()
def status() -> None:
    """Show the currently running session."""
    current = tracker.status()
    if not current:
        console.print("[dim]No session running.[/dim]  Use [bold]tlog start[/bold] to begin.")
        return

    tag_str = f"  [{', '.join(current['tags'])}]" if current.get("tags") else ""
    console.print(
        f"[green]▶  Running:[/green] [bold]{current['project']}[/bold] — {current['description']}{tag_str}\n"
        f"   [dim]Elapsed: {_fmt_duration(current['elapsed'])}[/dim]"
    )


@app.command()
def add(
    project: Annotated[str, typer.Argument(help="Project name")],
    description: Annotated[str, typer.Argument(help="What you worked on")],
    start: Annotated[str, typer.Option("--start", "-s", help="Start time (HH:MM)")],
    end: Annotated[str, typer.Option("--end", "-e", help="End time (HH:MM)")],
    entry_date: Annotated[Optional[str], typer.Option("--date", "-d", help="Date (YYYY-MM-DD, default: today)")] = None,
    tag: Annotated[Optional[list[str]], typer.Option("--tag", "-t", help="Tag (repeatable)")] = None,
) -> None:
    """Add a completed time entry manually."""
    on = _parse_date(entry_date, "--date") or date.today()
    start_time = _parse_time(start, "--start")
    end_time = _parse_time(end, "--end")

    start_dt = datetime.combine(on, start_time)
    end_dt = datetime.combine(on, end_time)

    if end_dt <= start_dt:
        # Handle crossing midnight: end is on the next day
        end_dt = datetime.combine(on + timedelta(days=1), end_time)

    tags = tag or []
    entry = TimeEntry(
        start=start_dt,
        end=end_dt,
        project=project,
        description=description,
        tags=tags,
    )
    storage.save_entry(entry)

    tag_str = f"  [{', '.join(tags)}]" if tags else ""
    console.print(
        f"[green]✚  Added:[/green] [bold]{project}[/bold] — {description}{tag_str}\n"
        f"   [dim]{on.isoformat()}  {start} – {end}  ({_fmt_duration(entry.duration)})[/dim]"
    )


# ─── Listing / reporting ──────────────────────────────────────────────────────

@app.command()
def log(
    today: Annotated[bool, typer.Option("--today", help="Show today's entries")] = False,
    yesterday: Annotated[bool, typer.Option("--yesterday", help="Show yesterday's entries")] = False,
    from_date: Annotated[Optional[str], typer.Option("--from", help="Start date (YYYY-MM-DD)")] = None,
    to_date: Annotated[Optional[str], typer.Option("--to", help="End date (YYYY-MM-DD)")] = None,
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Filter by project")] = None,
) -> None:
    """List time entries grouped by day."""
    entries = _filter_entries(
        storage.load_entries(),
        today=today,
        yesterday=yesterday,
        from_date=_parse_date(from_date, "--from"),
        to_date=_parse_date(to_date, "--to"),
        project=project,
    )

    if not entries:
        console.print("[dim]No entries found.[/dim]")
        return

    # Group by date
    by_date: dict[date, list[TimeEntry]] = {}
    for e in entries:
        d = e.start.date()
        by_date.setdefault(d, []).append(e)

    for day in sorted(by_date):
        day_entries = by_date[day]
        day_total = sum((e.duration for e in day_entries), timedelta())

        table = Table(
            box=box.SIMPLE_HEAD,
            show_header=True,
            header_style="bold cyan",
            title=f"[bold]{day.isoformat()}[/bold]  [dim]total {_fmt_duration(day_total)}[/dim]",
            title_justify="left",
        )
        table.add_column("Start", style="dim", width=8)
        table.add_column("End", style="dim", width=8)
        table.add_column("Duration", width=8)
        table.add_column("Project", style="bold")
        table.add_column("Description")
        table.add_column("Tags", style="dim")

        for e in sorted(day_entries, key=lambda x: x.start):
            table.add_row(
                e.start.strftime("%H:%M"),
                e.end.strftime("%H:%M"),
                _fmt_duration(e.duration),
                e.project,
                e.description,
                ", ".join(e.tags) if e.tags else "",
            )

        console.print(table)


@app.command()
def report(
    reporter_name: Annotated[str, typer.Option("--reporter", "-r", help="Reporter to use")] = "csv",
    today: Annotated[bool, typer.Option("--today", help="Report today's entries")] = False,
    yesterday: Annotated[bool, typer.Option("--yesterday", help="Report yesterday's entries")] = False,
    from_date: Annotated[Optional[str], typer.Option("--from", help="Start date (YYYY-MM-DD)")] = None,
    to_date: Annotated[Optional[str], typer.Option("--to", help="End date (YYYY-MM-DD)")] = None,
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Filter by project")] = None,
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Output file path (default: stdout)")] = None,
) -> None:
    """Generate a report using the specified reporter plugin."""
    rep = plugin_manager.get_reporter(reporter_name)
    if not rep:
        available = ", ".join(r["name"] for r in plugin_manager.list_reporters())
        _abort(
            f"Reporter [bold]{reporter_name!r}[/bold] not found.\n"
            f"  Available: {available}\n"
            f"  Install a plugin: [bold]tlog plugins install <package>[/bold]"
        )

    entries = _filter_entries(
        storage.load_entries(),
        today=today,
        yesterday=yesterday,
        from_date=_parse_date(from_date, "--from"),
        to_date=_parse_date(to_date, "--to"),
        project=project,
    )

    rep.configure(storage.get_reporter_config(reporter_name))

    # Show validation warnings but don't block export
    warnings = rep.validate(entries)
    for w in warnings:
        err_console.print(f"[yellow]⚠  {w}[/yellow]")

    rep.export(entries, output)

    if output:
        console.print(f"[green]✓[/green]  Exported {len(entries)} entries to [bold]{output}[/bold]")


# ─── Plugin management ────────────────────────────────────────────────────────

@plugins_app.command("list")
def plugins_list() -> None:
    """List all available reporters (built-in and installed plugins)."""
    reporters = plugin_manager.list_reporters()

    table = Table(box=box.SIMPLE_HEAD, header_style="bold cyan", show_header=True)
    table.add_column("Name", style="bold")
    table.add_column("Source")
    table.add_column("Description")

    for r in reporters:
        source_style = "dim" if r["source"] == "built-in" else "green"
        table.add_row(r["name"], f"[{source_style}]{r['source']}[/{source_style}]", r["description"])

    console.print(table)


@plugins_app.command("install")
def plugins_install(
    package: Annotated[str, typer.Argument(help="PyPI package name or path to .whl file")],
) -> None:
    """Install a reporter plugin via pipx inject."""
    console.print(f"Installing [bold]{package}[/bold] …")
    success = plugin_manager.install_plugin(package)
    if success:
        console.print(f"[green]✓[/green]  Plugin installed. Run [bold]tlog plugins list[/bold] to verify.")
    else:
        _abort("Installation failed. Make sure tlog was installed via pipx.")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    app()

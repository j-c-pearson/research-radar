from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from litreview.dates import (
    LONDON_TZ,
    default_window,
    initial_last_run_date,
    parse_date,
)
from litreview.env import load_local_env
from litreview.launchd import launchd_plist
from litreview.registry import (
    RegistryValidationError,
    load_registry,
    render_registry_markdown,
)
from litreview.render import render_report
from litreview.state import StateStore
from litreview.workflow import RunSkippedError, collect_records, run_review

app = typer.Typer(help="Weekly report-file literature alerts.")


@app.command()
def run(
    from_date: Annotated[
        str | None, typer.Option("--from", help="Start date, YYYY-MM-DD.")
    ] = None,
    to_date: Annotated[
        str | None, typer.Option("--to", help="End date, YYYY-MM-DD.")
    ] = None,
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite", help="Replace an existing report for the date window."
        ),
    ] = False,
    no_date_update: Annotated[
        bool,
        typer.Option(
            "--no-date-update",
            help="Write a report without advancing the stored last-run date.",
        ),
    ] = False,
    registry_path: Annotated[
        Path, typer.Option("--registry", help="Path to registry.yaml.")
    ] = Path("registry.yaml"),
    state_path: Annotated[
        Path, typer.Option("--state", help="Path to SQLite state DB.")
    ] = Path("state/litreview.sqlite"),
    reports_dir: Annotated[
        Path, typer.Option("--reports-dir", help="Directory for Markdown reports.")
    ] = Path("reports"),
) -> None:
    load_local_env()
    registry = _load_or_exit(registry_path)
    state = StateStore(state_path)
    try:
        if from_date and to_date:
            window = default_window(parse_date(from_date), now=_end_datetime(to_date))
        elif from_date or to_date:
            raise typer.BadParameter("--from and --to must be supplied together")
        else:
            window = default_window(state.get_last_run_date(), now=None)
        report_path = run_review(
            registry,
            window,
            state,
            reports_dir=reports_dir,
            overwrite=overwrite,
            update_last_run=not no_date_update,
        )
    except RunSkippedError as exc:
        typer.echo(str(exc))
        if exc.report_path:
            typer.echo(f"Existing report: {exc.report_path}")
        raise typer.Exit(0) from exc
    finally:
        state.close()
    typer.echo(f"Wrote report: {report_path}")


@app.command("scheduled-run")
def scheduled_run(
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite", help="Replace an existing report for the date window."
        ),
    ] = False,
    registry_path: Annotated[
        Path, typer.Option("--registry", help="Path to registry.yaml.")
    ] = Path("registry.yaml"),
    state_path: Annotated[
        Path, typer.Option("--state", help="Path to SQLite state DB.")
    ] = Path("state/litreview.sqlite"),
    reports_dir: Annotated[
        Path, typer.Option("--reports-dir", help="Directory for Markdown reports.")
    ] = Path("reports"),
) -> None:
    load_local_env()
    now = datetime.now(tz=LONDON_TZ)
    if now.weekday() != 4 or now.hour != 8:
        typer.echo(f"Not due: London time is {now.isoformat(timespec='minutes')}")
        return
    registry = _load_or_exit(registry_path)
    state = StateStore(state_path)
    try:
        window = default_window(state.get_last_run_date(now), now=now)
        report_path = run_review(
            registry, window, state, reports_dir=reports_dir, overwrite=overwrite
        )
    except RunSkippedError as exc:
        typer.echo(str(exc))
        if exc.report_path:
            typer.echo(f"Existing report: {exc.report_path}")
        raise typer.Exit(0) from exc
    finally:
        state.close()
    typer.echo(f"Wrote report: {report_path}")


@app.command()
def test(
    registry_path: Annotated[
        Path, typer.Option("--registry", help="Path to registry.yaml.")
    ] = Path("registry.yaml"),
) -> None:
    load_local_env()
    registry = _load_or_exit(registry_path)
    window = default_window(initial_last_run_date(), now=None)
    matched, diagnostics = collect_records(registry, window)
    typer.echo(render_report(registry, window, matched, diagnostics))


@app.command("validate-registry")
def validate_registry(
    registry_path: Annotated[
        Path, typer.Option("--registry", help="Path to registry.yaml.")
    ] = Path("registry.yaml"),
) -> None:
    _load_or_exit(registry_path)
    typer.echo(f"Registry is valid: {registry_path}")


@app.command("render-registry")
def render_registry(
    registry_path: Annotated[
        Path, typer.Option("--registry", help="Path to registry.yaml.")
    ] = Path("registry.yaml"),
    output: Annotated[
        Path, typer.Option("--output", help="Markdown output path.")
    ] = Path("registry.md"),
) -> None:
    registry = _load_or_exit(registry_path)
    output.write_text(render_registry_markdown(registry))
    typer.echo(f"Wrote registry view: {output}")


@app.command("install-launchd")
def install_launchd(
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Print the plist without installing.")
    ] = False,
    project_dir: Annotated[
        Path, typer.Option("--project-dir", help="Project working directory.")
    ] = Path("."),
    label: Annotated[
        str, typer.Option("--label", help="launchd label.")
    ] = "com.local.paper-alert-bot",
) -> None:
    resolved_project_dir = (
        Path.cwd() if str(project_dir) == "." else project_dir
    ).resolve()
    content = launchd_plist(resolved_project_dir, label=label)
    target = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
    if dry_run:
        typer.echo(content)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    typer.echo(f"Wrote launchd plist: {target}")


def _load_or_exit(path: Path):
    try:
        return load_registry(path)
    except RegistryValidationError as exc:
        for error in exc.errors:
            typer.echo(f"Registry error: {error}", err=True)
        raise typer.Exit(1) from exc


def _end_datetime(to_date: str) -> datetime:
    return datetime.combine(parse_date(to_date), datetime.min.time())


if __name__ == "__main__":
    app()

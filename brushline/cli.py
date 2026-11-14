"""The Brushline command line.

The command surface grows one phase at a time. Phase 0 establishes the entry point and the
version contract; later phases add the build, simulate, plan, monitor, compare, validate, and
serve commands described in ``ROADMAP.md``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from brushline import __version__
from brushline.model.schema import validate_dataset

app = typer.Typer(
    name="brushline",
    help="Decision support for vegetation management along linear infrastructure corridors.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    """Print the package version and exit when ``--version`` is given.

    Parameters
    ----------
    value : bool
        Whether the eager ``--version`` flag was supplied.

    Raises
    ------
    typer.Exit
        When ``value`` is true.
    """
    if value:
        typer.echo(f"brushline {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the package version and exit.",
        ),
    ] = False,
) -> None:
    """Run the Brushline command line."""


@app.command()
def status() -> None:
    """Print the package version and its pre-alpha status."""
    typer.echo(f"brushline {__version__} (pre-alpha)")
    typer.echo("Phase 1: contracts and prototype. No vegetation model or planner is available yet.")


@app.command()
def validate(
    dataset: Annotated[
        Path,
        typer.Option("--dataset", help="Compiled dataset directory to validate."),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the validation report as JSON."),
    ] = False,
) -> None:
    """Validate a compiled corridor dataset against its manifest.

    Parameters
    ----------
    dataset : Path
        Dataset directory that contains ``manifest.json``.
    json_output : bool, optional
        Print the JSON report instead of the text summary.

    Raises
    ------
    typer.Exit
        With status 1 when the dataset is invalid.
    """
    report = validate_dataset(dataset)
    if json_output:
        typer.echo(json.dumps(report.to_dict(), indent=2))
    else:
        typer.echo(f"dataset: {report.dataset}")
        typer.echo(f"tables: {len(report.tables)}")
        for name, rows in sorted(report.tables.items()):
            typer.echo(f"  {name}: {rows} rows")
        if report.warnings:
            typer.echo("warnings:")
            for message in report.warnings:
                typer.echo(f"  {message}")
        if report.errors:
            typer.echo("errors:")
            for message in report.errors:
                typer.echo(f"  {message}")
        typer.echo("VALID" if report.is_valid else "INVALID")
    if not report.is_valid:
        raise typer.Exit(code=1)

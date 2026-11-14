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
from brushline.fixtures.synthetic import DEFAULT_SEED, generate_fixture
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
def fixture(
    out: Annotated[
        Path,
        typer.Option("--out", help="Directory for the synthetic corridor fixture."),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite the known fixture files."),
    ] = False,
    seed: Annotated[
        int,
        typer.Option("--seed", help="Fixture seed."),
    ] = DEFAULT_SEED,
) -> None:
    """Generate the deterministic synthetic corridor fixture.

    Parameters
    ----------
    out : Path
        Destination directory.
    force : bool, optional
        Overwrite the known fixture files. Defaults to ``False``.
    seed : int, optional
        Fixture seed. Defaults to ``DEFAULT_SEED``.

    Raises
    ------
    typer.Exit
        With status 1 when the destination is not empty or a contract fails.
    """
    try:
        result = generate_fixture(out, seed=seed, force=force)
    except (FileExistsError, RuntimeError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"fixture: {result.root}")
    typer.echo(f"artifacts: {len(result.artifacts)}")
    typer.echo(f"content_digest: {result.content_digest}")


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

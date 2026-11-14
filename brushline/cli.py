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
from brushline.build.compiler import compile_fixture
from brushline.fixtures.synthetic import DEFAULT_SEED, generate_fixture
from brushline.model.schema import validate_dataset
from brushline.sim.engine import simulate_dataset

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
def build(
    fixture: Annotated[
        Path,
        typer.Option("--fixture", help="Fixture directory to compile."),
    ],
    out: Annotated[
        Path,
        typer.Option("--out", help="Compiled dataset directory."),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite an existing compiled dataset."),
    ] = False,
) -> None:
    """Compile a fixture into a validated Brushline dataset.

    Parameters
    ----------
    fixture : Path
        Fixture directory.
    out : Path
        Compiled dataset directory.
    force : bool, optional
        Overwrite an existing dataset. Defaults to ``False``.

    Raises
    ------
    typer.Exit
        With status 1 when the compile fails.
    """
    try:
        result = compile_fixture(fixture, out, force=force)
    except (FileExistsError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"dataset: {result.root}")
    typer.echo(f"segments: {len(result.segments)}")
    typer.echo(f"states: {len(result.states)}")
    typer.echo(f"content_digest: {result.manifest.content_digest}")


@app.command()
def simulate(
    dataset: Annotated[
        Path,
        typer.Option("--dataset", help="Compiled dataset directory."),
    ],
    out: Annotated[
        Path,
        typer.Option("--out", help="Run directory."),
    ],
    plan: Annotated[
        Path | None,
        typer.Option("--plan", help="Plan artifact to replay."),
    ] = None,
    schedule: Annotated[
        Path | None,
        typer.Option("--schedule", help="Schedule CSV to replay."),
    ] = None,
    years: Annotated[
        int,
        typer.Option("--years", min=1, max=50, help="Simulation years."),
    ] = 5,
    start_year: Annotated[
        int,
        typer.Option("--start-year", help="First simulation year."),
    ] = 2026,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite an existing run directory."),
    ] = False,
) -> None:
    """Replay a plan or schedule against a compiled dataset.

    Parameters
    ----------
    dataset : Path
        Compiled dataset directory.
    out : Path
        Run directory.
    plan : Path or None, optional
        Plan artifact. Exactly one of ``plan`` and ``schedule`` is required.
    schedule : Path or None, optional
        Schedule CSV. Exactly one of ``plan`` and ``schedule`` is required.
    years : int, optional
        Simulation years. Defaults to ``5``.
    start_year : int, optional
        First simulation year. Defaults to ``2026``.
    force : bool, optional
        Overwrite an existing run. Defaults to ``False``.

    Raises
    ------
    typer.Exit
        With status 1 when the simulation fails.
    """
    try:
        result = simulate_dataset(
            dataset,
            out,
            plan=plan,
            schedule=schedule,
            years=years,
            start_year=start_year,
            force=force,
        )
    except (FileExistsError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"run: {result.run_dir}")
    typer.echo(f"total_cost: {result.summary['total_cost']}")
    typer.echo(f"final_mean_height_m: {result.summary['final_mean_height_m']}")


@app.command()
def prototype(
    fixture: Annotated[
        Path,
        typer.Option("--fixture", help="Fixture directory."),
    ],
    out: Annotated[
        Path,
        typer.Option("--out", help="Prototype output directory."),
    ],
    years: Annotated[
        int,
        typer.Option("--years", min=1, max=50, help="Simulation years."),
    ] = 5,
) -> None:
    """Compile and simulate the synthetic fixture end to end.

    Parameters
    ----------
    fixture : Path
        Fixture directory.
    out : Path
        Output directory. The dataset is written under ``dataset`` and the run under ``run``.
    years : int, optional
        Simulation years. Defaults to ``5``.

    Raises
    ------
    typer.Exit
        With status 1 when the compile or simulation fails.
    """
    try:
        compiled = compile_fixture(fixture, out / "dataset", force=True)
        result = simulate_dataset(
            compiled.root,
            out / "run",
            plan=Path(fixture) / "plan.json",
            years=years,
            force=True,
        )
    except (FileExistsError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"dataset: {compiled.root}")
    typer.echo(f"run: {result.run_dir}")
    typer.echo(f"total_cost: {result.summary['total_cost']}")


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

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
from brushline.demo.builder import build_demo_site
from brushline.field.validation import validate_field_csv, write_field_validation
from brushline.fixtures.synthetic import DEFAULT_SEED, generate_fixture
from brushline.instance_ops import (
    build_demo_file,
    compile_dataset_file,
    seed_state_file,
    segment_corridor_file,
    validate_aoi_file,
    validate_scenario_file,
)
from brushline.instance_template import install_instance_template
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
    typer.echo(
        "Planning, monitoring, exchange, public demo, and studio are present. "
        "See the release notes and known gaps before use."
    )


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


instance_app = typer.Typer(
    help="Manage Brushline instance templates.",
    no_args_is_help=True,
)


@instance_app.command("template")
def instance_template(
    instance_root: Annotated[
        Path,
        typer.Option("--instance-root", help="FEMIC instance root."),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing template files."),
    ] = False,
) -> None:
    """Install the Brushline template overlay on a FEMIC instance.

    Parameters
    ----------
    instance_root : Path
        FEMIC instance root. It is created when it does not exist.
    force : bool, optional
        Overwrite existing template files. Defaults to ``False``.

    Raises
    ------
    typer.Exit
        With status 1 when the packaged template is missing.
    """
    try:
        result = install_instance_template(instance_root, force=force)
    except FileNotFoundError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"instance: {result.root}")
    typer.echo(f"written: {len(result.written)}")
    typer.echo(f"skipped: {len(result.skipped)}")


@instance_app.command("validate-aoi")
def instance_validate_aoi(
    aoi: Annotated[Path, typer.Option("--aoi", help="AOI GeoJSON.")],
    out: Annotated[Path, typer.Option("--out", help="Output directory.")],
) -> None:
    """Validate an AOI GeoJSON and write the report."""
    try:
        path = validate_aoi_file(aoi, out)
    except (OSError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"aoi_validation: {path}")


@instance_app.command("segment-corridor")
def instance_segment_corridor(
    corridor: Annotated[Path, typer.Option("--corridor", help="Corridor graph JSON.")],
    out: Annotated[Path, typer.Option("--out", help="Output directory.")],
) -> None:
    """Validate a corridor graph and write its segment table."""
    try:
        path = segment_corridor_file(corridor, out)
    except (OSError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"segments: {path}")


@instance_app.command("compile-dataset")
def instance_compile_dataset(
    fixture: Annotated[Path, typer.Option("--fixture", help="Fixture directory.")],
    out: Annotated[Path, typer.Option("--out", help="Compiled dataset directory.")],
    force: Annotated[bool, typer.Option("--force", help="Overwrite the dataset.")] = False,
) -> None:
    """Compile a fixture into a validated Brushline dataset."""
    try:
        result = compile_dataset_file(fixture, out, force=force)
    except (OSError, ValueError, FileExistsError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"dataset: {result.root}")
    typer.echo(f"content_digest: {result.manifest.content_digest}")


@instance_app.command("seed-state")
def instance_seed_state(
    state: Annotated[Path, typer.Option("--state", help="State contract JSON.")],
    out: Annotated[Path, typer.Option("--out", help="Output directory.")],
) -> None:
    """Validate a state contract and write the seed state artifact."""
    try:
        path = seed_state_file(state, out)
    except (OSError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"state: {path}")


@instance_app.command("validate-scenario")
def instance_validate_scenario(
    scenario: Annotated[Path, typer.Option("--scenario", help="Scenario YAML.")],
    targets: Annotated[Path, typer.Option("--targets", help="Targets YAML.")],
    out: Annotated[Path, typer.Option("--out", help="Output directory.")],
) -> None:
    """Validate the scenario and targets YAML."""
    try:
        path = validate_scenario_file(scenario, targets, out)
    except (OSError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"scenario_validation: {path}")


@instance_app.command("build-demo")
def instance_build_demo(
    demo: Annotated[Path, typer.Option("--demo", help="Demo manifest JSON.")],
    out: Annotated[Path, typer.Option("--out", help="Output directory.")],
) -> None:
    """Validate a demo manifest and write the demo artifact."""
    try:
        path = build_demo_file(demo, out)
    except (OSError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"demo: {path}")


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


field_app = typer.Typer(help="Validate field observations for a planned campaign.")


@field_app.command("validate")
def field_validate(
    observations: Annotated[
        Path, typer.Option("--csv", help="Field observations CSV exported from the field kit.")
    ],
    plots: Annotated[Path, typer.Option("--plots", help="Planned plot points as GeoJSON.")],
    out: Annotated[
        Path | None, typer.Option("--out", help="Write normalized observations to JSON.")
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Print the validation report as JSON.")
    ] = False,
) -> None:
    """Validate field observations and optionally write normalized JSON.

    Parameters
    ----------
    observations : Path
        Field observations CSV.
    plots : Path
        Planned plot references GeoJSON.
    out : Path, optional
        Normalized JSON output.
    json_output : bool, optional
        Print JSON instead of a text summary.

    Raises
    ------
    typer.Exit
        With status 1 when the observations are invalid.
    """
    try:
        report = validate_field_csv(observations, plots)
    except (OSError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if out is not None:
        write_field_validation(report, out)
    if json_output:
        typer.echo(report.model_dump_json(indent=2))
    else:
        typer.echo(f"observations: {report.source_csv}")
        typer.echo(f"plots_expected: {report.plots_expected}")
        typer.echo(f"observations_valid: {len(report.observations)}")
        if report.warnings:
            typer.echo("warnings:")
            for message in report.warnings:
                typer.echo(f"  {message}")
        if report.errors:
            typer.echo("errors:")
            for message in report.errors:
                typer.echo(f"  {message}")
        typer.echo("VALID" if report.valid else "INVALID")
    if not report.valid:
        raise typer.Exit(code=1)


app.add_typer(field_app, name="field")
app.add_typer(instance_app, name="instance")


demo_app = typer.Typer(help="Build the public demo portal.")


@demo_app.command("build")
def demo_build(
    out: Annotated[Path, typer.Option("--out", help="Destination directory.")] = Path("build/demo"),
    artifact_root: Annotated[
        Path, typer.Option("--artifact-root", help="Run artifact root.")
    ] = Path("examples/synthetic-corridor"),
) -> None:
    """Build the static public demo site."""
    root = build_demo_site(out, artifact_root=artifact_root)
    typer.echo(f"demo: {root}")


app.add_typer(demo_app, name="demo")

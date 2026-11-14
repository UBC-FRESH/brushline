"""The Brushline command line.

The command surface grows one phase at a time. Phase 0 establishes the entry point and the
version contract; later phases add the build, simulate, plan, monitor, compare, validate, and
serve commands described in ``ROADMAP.md``.
"""

from __future__ import annotations

from typing import Annotated

import typer

from brushline import __version__

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
    typer.echo("Phase 0: bootstrap and scope. No vegetation model or planner is available yet.")

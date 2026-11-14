"""Contract tests for the Brushline command line."""

from __future__ import annotations

from brushline import __version__
from brushline.cli import app
from typer.testing import CliRunner

RUNNER = CliRunner()


def test_version_option_prints_the_package_version() -> None:
    """The eager ``--version`` flag exits cleanly and names the version."""
    result = RUNNER.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_names_the_status_command_and_the_version_flag() -> None:
    """The help text exposes the first command surface."""
    result = RUNNER.invoke(app, ["--help"])
    assert result.exit_code == 0
    text = result.stdout.lower()
    assert "status" in text
    assert "version" in text


def test_status_prints_the_version_and_the_pre_alpha_state() -> None:
    """The status command states the package version and that no model exists yet."""
    result = RUNNER.invoke(app, ["status"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
    assert "pre-alpha" in result.stdout
    assert "No vegetation model" in result.stdout


def test_unknown_command_exits_with_a_usage_error() -> None:
    """An unknown command exits with the conventional usage status."""
    result = RUNNER.invoke(app, ["not-a-command"])
    assert result.exit_code == 2

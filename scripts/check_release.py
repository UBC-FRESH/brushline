"""Verify local release artifacts and a clean wheel install."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

EXPECTED = ("brushline", "LICENSE", "README.md")


def check_dist(dist: Path) -> list[str]:
    """Return problems with the wheel/sdist contents.

    Parameters
    ----------
    dist : Path
        Distribution directory.

    Returns
    -------
    list of str
        Problems, or an empty list.
    """
    problems: list[str] = []
    wheels = sorted(dist.glob("brushline-*.whl"))
    sdists = sorted(dist.glob("brushline-*.tar.gz"))
    if not wheels:
        problems.append("missing wheel")
    if not sdists:
        problems.append("missing sdist")
    if wheels:
        with zipfile.ZipFile(wheels[-1]) as archive:
            names = archive.namelist()
            for expected in EXPECTED:
                if not any(expected in name for name in names):
                    problems.append(f"wheel missing {expected}")
            if not any("brushline/web/static/studio.html" in name for name in names):
                problems.append("wheel missing studio shell")
    if sdists:
        with tarfile.open(sdists[-1]) as archive:
            names = archive.getnames()
            if not any("RELEASE_NOTES.md" in name for name in names):
                problems.append("sdist missing RELEASE_NOTES.md")
    return problems


def clean_install(wheel: Path) -> list[str]:
    """Install the wheel into a temporary venv and run version.

    Parameters
    ----------
    wheel : Path
        Wheel path.

    Returns
    -------
    list of str
        Problems, or an empty list.
    """
    problems: list[str] = []
    venv = Path("/tmp") / "brushline-release-check"
    subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", str(venv)], check=False)
    python = venv / "bin" / "python"
    result = subprocess.run(
        [str(python), "-m", "pip", "install", "--force-reinstall", str(wheel)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return [f"wheel install failed: {result.stderr[-300:]}"]
    result = subprocess.run(
        [str(venv / "bin" / "brushline"), "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or "brushline" not in result.stdout:
        problems.append("installed CLI version failed")
    return problems


def main() -> int:
    """Run the release artifact checks.

    Returns
    -------
    int
        Process exit status.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    problems = check_dist(args.dist)
    if args.install:
        wheels = sorted(args.dist.glob("brushline-*.whl"))
        if wheels:
            problems.extend(clean_install(wheels[-1]))
    if problems:
        print("\n".join(problems))
        return 1
    print("release artifacts: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

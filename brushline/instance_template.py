"""Install the Brushline instance template overlay on a FEMIC instance."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

TEMPLATE_ROOT: Path = Path(__file__).resolve().parent / "resources" / "instance"
TEMPLATE_SCHEMA_VERSION = "brushline.instance-template.v1"


@dataclass(frozen=True)
class InstanceTemplateResult:
    """The outcome of installing the Brushline instance template.

    Parameters
    ----------
    root : Path
        Instance root.
    written : tuple of Path
        Files written.
    skipped : tuple of Path
        Files skipped because they already exist.
    """

    root: Path
    written: tuple[Path, ...]
    skipped: tuple[Path, ...]


def install_instance_template(
    instance_root: Path,
    *,
    force: bool = False,
) -> InstanceTemplateResult:
    """Install the Brushline overlay into a FEMIC instance root.

    Parameters
    ----------
    instance_root : Path
        FEMIC instance root. It is created when it does not exist.
    force : bool, optional
        Overwrite existing Brushline template files. Defaults to ``False``.

    Returns
    -------
    InstanceTemplateResult
        The root, written files, and skipped files.

    Raises
    ------
    FileNotFoundError
        When the packaged template is incomplete.
    """
    root = Path(instance_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not TEMPLATE_ROOT.is_dir():
        raise FileNotFoundError(f"instance template is missing: {TEMPLATE_ROOT}")
    written: list[Path] = []
    skipped: list[Path] = []
    for source in sorted(TEMPLATE_ROOT.rglob("*")):
        if not source.is_file() or source.name == "__init__.py":
            continue
        relative = source.relative_to(TEMPLATE_ROOT)
        target = root / relative
        if target.exists() and not force:
            skipped.append(target)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        written.append(target)
    return InstanceTemplateResult(root, tuple(written), tuple(skipped))


__all__ = [
    "TEMPLATE_ROOT",
    "TEMPLATE_SCHEMA_VERSION",
    "InstanceTemplateResult",
    "install_instance_template",
]

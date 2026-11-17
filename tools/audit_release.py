# mypy: ignore-errors
"""Audit the private/public boundary before any release or data-sharing review.

This is a read-only repository check. It does not grant release approval and does not inspect
whether the data-sharing agreement is in place.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PREFIXES = ("runtime/", "data/private/", "local/", "tmp/", "outputs/")
FORBIDDEN_TEXT = ("/srv/shared-data", "/home/gep")
PUBLIC_DEMO = ROOT / "examples/synthetic-corridor"
PRIVATE_DEMO_TERMS = ("bc-hydro-network", "mkrf", "runtime/private")
TEXT_SUFFIXES = {".py", ".md", ".rst", ".js", ".html", ".json", ".toml", ".yml", ".yaml", ".txt"}


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [item for item in result.stdout.split("\0") if item]


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": ok, "detail": detail}


def audit_release() -> dict[str, Any]:
    """Return release-boundary checks for the current checkout."""
    tracked = _tracked_files()
    checks: list[dict[str, Any]] = []
    private_paths = [path for path in tracked if path.startswith(FORBIDDEN_PREFIXES)]
    checks.append(
        _check(
            "private-paths-untracked",
            not private_paths,
            "no tracked private paths" if not private_paths else f"tracked: {private_paths[:5]}",
        )
    )
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    missing_ignore = [item for item in ("runtime/", "data/private/") if item not in gitignore]
    checks.append(
        _check(
            "gitignore-boundary",
            not missing_ignore,
            "runtime/ and data/private/ ignored"
            if not missing_ignore
            else f"missing: {missing_ignore}",
        )
    )
    absolute_hits: list[str] = []
    for path in tracked:
        if path == "tools/audit_release.py":
            continue
        file_path = ROOT / path
        if file_path.suffix.lower() not in TEXT_SUFFIXES or not file_path.is_file():
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for needle in FORBIDDEN_TEXT:
            if needle in text:
                absolute_hits.append(f"{path}:{needle}")
    checks.append(
        _check(
            "no-local-absolute-paths",
            not absolute_hits,
            "no local absolute paths" if not absolute_hits else f"hits: {absolute_hits[:5]}",
        )
    )
    public_hits: list[str] = []
    for path in sorted(PUBLIC_DEMO.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for needle in PRIVATE_DEMO_TERMS:
            if needle in text:
                public_hits.append(f"{path.relative_to(ROOT)}:{needle}")
    checks.append(
        _check(
            "public-demo-synthetic",
            PUBLIC_DEMO.exists() and not public_hits,
            "synthetic demo contains no private references"
            if PUBLIC_DEMO.exists() and not public_hits
            else f"missing or references: {public_hits[:5]}",
        )
    )
    private_dir = ROOT / "runtime/private"
    private_count = (
        sum(1 for path in private_dir.rglob("*") if path.is_file()) if private_dir.exists() else 0
    )
    status = "pass" if all(check["ok"] for check in checks) else "fail"
    return {
        "schema_version": "brushline.release-audit.v1",
        "status": status,
        "checks": checks,
        "tracked_files": len(tracked),
        "private_files_present": private_count,
        "note": (
            "Read-only boundary audit; release approval and data-sharing sign-off are external."
        ),
    }


def main() -> None:
    """Print the release-boundary audit and exit non-zero on failure."""
    result = audit_release()
    print(json.dumps(result, indent=2))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

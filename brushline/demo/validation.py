"""Static portal validation."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VALIDATION_SCHEMA_VERSION: Literal["brushline.demo-validation.v1"] = "brushline.demo-validation.v1"


class PortalValidation(BaseModel):
    """Portal validation result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.demo-validation.v1"] = VALIDATION_SCHEMA_VERSION
    root: str
    passed: bool
    pages: list[str] = Field(default_factory=list)
    problems: list[str] = Field(default_factory=list)


def validate_site(root: str | Path) -> PortalValidation:
    """Check required files, links, licences, caveats, and read-only health."""
    base = Path(root)
    problems: list[str] = []
    pages = sorted(str(path.relative_to(base)) for path in base.rglob("*.html"))
    for required in ("index.html", "pilot.html", "style.css", "demo.js", "health.json"):
        if not (base / required).exists():
            problems.append(f"missing {required}")
    for page in pages:
        text = (base / page).read_text(encoding="utf-8")
        if "caveat" not in text and page != "index.html":
            problems.append(f"missing caveat in {page}")
        if "licence" not in text.lower() and page != "index.html":
            problems.append(f"missing licence in {page}")
        if "private" in text.lower() and "no private" not in text.lower():
            problems.append(f"possible private data mention in {page}")
    health = (
        (base / "health.json").read_text(encoding="utf-8")
        if (base / "health.json").exists()
        else ""
    )
    if '"read_only": true' not in health:
        problems.append("health is not read-only")
    return PortalValidation(root=str(base), passed=not problems, pages=pages, problems=problems)

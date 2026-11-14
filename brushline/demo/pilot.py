"""Pilot brief and data boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PILOT_SCHEMA_VERSION: Literal["brushline.pilot-brief.v1"] = "brushline.pilot-brief.v1"


class PilotBrief(BaseModel):
    """Public pilot request and data-boundary brief."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.pilot-brief.v1"] = PILOT_SCHEMA_VERSION
    title: str
    contact: str
    data_request: list[str] = Field(min_length=1)
    protection: list[str] = Field(min_length=1)
    success_metrics: list[str] = Field(min_length=1)
    nda_path: str
    caveats: list[str] = Field(min_length=1)


def default_pilot(contact: str = "pilot@example.org") -> PilotBrief:
    """Return the public pilot funnel brief."""
    return PilotBrief(
        title="Bring a corridor question, not a private dataset",
        contact=contact,
        data_request=[
            "A corridor or treatment-unit boundary and segment ids",
            "A vegetation inventory, LiDAR product, or field observation sample",
            "The service standard, current cycle, and budget envelope",
            "A named owner reviewer and a question the pilot should answer",
        ],
        protection=[
            "Start with public or synthetic data; no private payload is required for the demo.",
            "Private data is reviewed under the owner's access, retention, and NDA terms.",
            "The demo portal is read-only and does not accept uploads.",
            "Credentials and raw private payloads never enter the public site.",
        ],
        success_metrics=[
            "The plan reproduces its cost and service totals.",
            "Every assumption and caveat is visible to the reviewer.",
            "The owner can compare the plan with BAU on the same data.",
        ],
        nda_path="The owner's security and NDA path is agreed before any private data transfer.",
        caveats=["No upload, no account, and no private data in the public portal."],
    )


def _items(values: list[str]) -> str:
    return "".join(f"<li>{value}</li>" for value in values)


def render_pilot(brief: PilotBrief) -> str:
    """Render a standalone HTML pilot page."""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<title>{brief.title}</title><link rel="stylesheet" href="style.css"></head>'
        f"<body><main><h1>{brief.title}</h1><p><strong>Contact:</strong> {brief.contact}</p>"
        f"<h2>What to bring</h2><ul>{_items(brief.data_request)}</ul>"
        f"<h2>How data is protected</h2><ul>{_items(brief.protection)}</ul>"
        f"<h2>Success metrics</h2><ul>{_items(brief.success_metrics)}</ul>"
        f"<h2>NDA and security</h2><p>{brief.nda_path}</p><p>Licence: public pilot brief; synthetic examples are CC0-1.0.</p>"  # noqa: E501
        f'<p class="caveat">{_items(brief.caveats)}</p>'
        '<p><a href="index.html">Back to the demo portfolio</a></p>'
        "</main></body></html>"
    )


def write_pilot(brief: PilotBrief, path: str | Path) -> Path:
    """Write the pilot page."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_pilot(brief), encoding="utf-8")
    return destination

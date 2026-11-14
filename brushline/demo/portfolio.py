"""Curated public demo portfolio."""

from __future__ import annotations

from datetime import UTC, datetime

from brushline.model.demo import DemoArtifacts, DemoManifest, DemoMetric, DemoSource

DEMO_PORTFOLIO_SCHEMA: str = "brushline.demo-portfolio.v1"


def build_portfolio(created_utc: datetime | None = None) -> list[DemoManifest]:
    """Return the five public/synthetic demo narratives."""
    created = created_utc or datetime(2026, 11, 14, tzinfo=UTC)
    entries = [
        (
            "synthetic-corridor",
            "Synthetic corridor",
            "utility",
            "British Columbia",
            "What does a risk-ranked treatment plan look like on a small synthetic corridor?",
            5300,
            0.12,
        ),
        (
            "utility-risk-first",
            "Utility risk-first",
            "utility",
            "British Columbia",
            "How does a risk-first budget change the service and cost trade-off?",
            4700,
            0.16,
        ),
        (
            "pipeline-access",
            "Pipeline access",
            "pipeline",
            "Alberta",
            "Where does access constrain a treatment plan on a linear corridor?",
            5100,
            0.18,
        ),
        (
            "rail-season",
            "Rail season",
            "railway",
            "British Columbia",
            "How does a seasonal window change treatment timing and cost?",
            4900,
            0.14,
        ),
        (
            "roadside-priority",
            "Roadside priority",
            "road",
            "British Columbia",
            "Which segments should a roadside program treat first under a fixed budget?",
            4300,
            0.22,
        ),
    ]
    manifests: list[DemoManifest] = []
    for index, (demo_id, title, sector, region, question, cost, risk) in enumerate(entries):
        manifests.append(
            DemoManifest(
                id=demo_id,
                title=title,
                sector=sector,
                region=region,
                aoi="aoi.geojson",
                question=question,
                data_sources=[
                    DemoSource(
                        name="Synthetic corridor fixture",
                        licence="CC0-1.0",
                        version="1.0",
                        url="",
                    )
                ],
                scenarios=["baseline", "risk-first"],
                artifacts=DemoArtifacts(
                    run="run.json",
                    plan="plan.json",
                    reports="reports",
                    pareto="pareto.json",
                    timeline="operations_timeline.jsonl",
                ),
                headline_metrics=[
                    DemoMetric(name="present_cost", value=cost, unit="CAD"),
                    DemoMetric(name="service_risk", value=risk, unit="index"),
                ],
                caveats=[
                    "Synthetic geometry and synthetic costs; not an operational plan.",
                    "The display is a context view, not a survey or safety certification.",
                    f"Demo narrative {index + 1} uses the same synthetic evidence base.",
                ],
                pilot="pilot.md",
                status="published",
                created_utc=created,
                contact="pilot@example.org",
            )
        )
    return manifests

"""Contract tests for the plan, run, Pareto archive, timeline, and demo manifest."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from brushline.model.archive import (
    ArchiveMember,
    Objective,
    ParetoArchive,
    Scalarization,
    dominates,
    validate_pareto_archive,
)
from brushline.model.demo import (
    DemoArtifacts,
    DemoManifest,
    DemoMetric,
    DemoSource,
    validate_demo_manifest,
)
from brushline.model.plan import (
    CostLine,
    Plan,
    PlanAction,
    PlanAssumption,
    PlanHeader,
    validate_plan,
)
from brushline.model.run import RunArtifact, RunManifest, validate_run_manifest
from brushline.model.timeline import OperationsTimeline, TimelineEvent, validate_timeline
from pydantic import ValidationError

NOW = datetime(2026, 11, 14, tzinfo=UTC)
SHA = "a" * 64


def _plan() -> Plan:
    action = PlanAction(
        action_id="a1",
        segment_id="s1",
        year=2026,
        season="summer",
        method="mowing",
        intensity=0.8,
        cost_lines=[
            CostLine(category="labour", quantity=10.0, rate=100.0, amount=1000.0),
            CostLine(category="equipment", amount=500.0),
        ],
        quantity_ha=1.0,
        assumptions=["Rates from the 2026 contract."],
    )
    header = PlanHeader(
        plan_id="plan-1",
        version=1,
        status="proposed",
        scenario_id="scenario-1",
        dataset_id="dataset-1",
        data_version="sha256:abc",
        model_versions={"growth": "p1", "treatment": "p1"},
        currency="CAD",
        created_utc=NOW,
        created_by="tests",
    )
    return Plan(
        header=header,
        actions=[action],
        assumptions=[
            PlanAssumption(
                assumption_id="as1",
                statement="One pass per segment.",
                source="tests",
            )
        ],
    )


def _run() -> RunManifest:
    return RunManifest(
        run_id="run-1",
        run_type="plan",
        status="complete",
        created_utc=NOW,
        data_version="sha256:abc",
        model_versions={"growth": "p1"},
        artifacts=[
            RunArtifact(
                name="plan",
                path="plan.json",
                schema_version="brushline.plan.v1",
                media_type="application/json",
                sha256=SHA,
            ),
            RunArtifact(
                name="timeline",
                path="operations_timeline.jsonl",
                schema_version="brushline.timeline.v1",
                media_type="application/jsonl",
                available=False,
                reason="No operations run for this scenario.",
            ),
        ],
        created_by="tests",
    )


def _archive() -> ParetoArchive:
    return ParetoArchive(
        instance_id="instance-1",
        run_id="run-1",
        objectives=[
            Objective(name="present_cost", direction="minimize", unit="CAD"),
            Objective(name="service_risk", direction="minimize", unit="index"),
        ],
        scalarizations=[
            Scalarization(
                scalarization_id="balanced",
                weights={"present_cost": 0.5, "service_risk": 0.5},
            )
        ],
        members=[
            ArchiveMember(
                plan_id="plan-a",
                plan_path="plans/a.json",
                objective={"present_cost": 100.0, "service_risk": 0.2},
                feasible=True,
                seed=1,
                evidence_path="evidence/a.json",
            ),
            ArchiveMember(
                plan_id="plan-b",
                plan_path="plans/b.json",
                objective={"present_cost": 80.0, "service_risk": 0.3},
                feasible=True,
                seed=2,
                evidence_path="evidence/b.json",
            ),
        ],
        eviction="crowding-distance",
        created_utc=NOW,
        created_by="tests",
    )


def _timeline() -> OperationsTimeline:
    start = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    return OperationsTimeline(
        run_id="run-1",
        events=[
            TimelineEvent(
                event_id="e1",
                resource_id="crew-1",
                resource_type="crew",
                segment_id="s1",
                event_type="travel",
                start_utc=start,
                end_utc=start + timedelta(minutes=30),
                state="travel",
            ),
            TimelineEvent(
                event_id="e2",
                resource_id="crew-1",
                resource_type="crew",
                segment_id="s1",
                event_type="treatment",
                start_utc=start + timedelta(minutes=30),
                end_utc=start + timedelta(minutes=90),
                state="working",
                action_id="a1",
                cost=1500.0,
            ),
        ],
        created_utc=NOW,
        created_by="tests",
    )


def _demo() -> DemoManifest:
    return DemoManifest(
        id="utility-lidar",
        title="Utility corridor with open LiDAR",
        sector="utility",
        region="British Columbia",
        aoi="aoi.geojson",
        question="What does a risk-ranked treatment program look like?",
        data_sources=[
            DemoSource(name="LidarBC", licence="OGL-BC", version="2024"),
            DemoSource(name="Synthetic asset", licence="CC0-1.0", version="1.0"),
        ],
        scenarios=["baseline", "risk-first"],
        artifacts=DemoArtifacts(
            run="runs/risk-first",
            plan="runs/risk-first/plan.json",
            reports="runs/risk-first/reports",
            pareto="runs/risk-first/pareto.json",
            timeline="runs/risk-first/operations_timeline.jsonl",
        ),
        headline_metrics=[
            DemoMetric(name="present_cost", value=1200000.0, unit="CAD"),
        ],
        caveats=["Synthetic asset geometry; public vegetation data."],
        pilot="pilot/utility-lidar.md",
        status="published",
        created_utc=NOW,
        contact="pilot@example.org",
    )


def test_plan_passes_and_totals_costs() -> None:
    """A valid plan passes and totals its cost lines."""
    plan = _plan()
    report = validate_plan(plan, known_segment_ids={"s1"})
    assert report.is_valid
    assert report.counts["total_cost"] == 1500.0
    assert plan.total_cost == 1500.0


def test_plan_rejects_duplicate_actions_and_assumptions() -> None:
    """Duplicate action or assumption ids fail with PLAN-ID."""
    plan = _plan()
    variants = [
        plan.model_copy(update={"actions": [plan.actions[0], plan.actions[0]]}),
        plan.model_copy(update={"assumptions": [plan.assumptions[0], plan.assumptions[0]]}),
    ]
    for variant in variants:
        report = validate_plan(variant)
        assert any(message.startswith("PLAN-ID") for message in report.errors)


def test_plan_rejects_unknown_segment_and_currency() -> None:
    """An unknown segment and a currency mismatch fail."""
    plan = _plan()
    unknown = plan.actions[0].model_copy(update={"segment_id": "s9"})
    report = validate_plan(
        plan.model_copy(update={"actions": [unknown]}),
        known_segment_ids={"s1"},
    )
    assert any(message.startswith("PLAN-REF") for message in report.errors)
    wrong_currency = plan.actions[0].model_copy(
        update={
            "cost_lines": [
                CostLine(category="labour", amount=100.0, currency="USD"),
            ]
        }
    )
    report = validate_plan(plan.model_copy(update={"actions": [wrong_currency]}))
    assert any(message.startswith("PLAN-CURRENCY") for message in report.errors)


def test_plan_warns_on_missing_action_assumption() -> None:
    """An action without an explicit assumption gets a warning."""
    plan = _plan()
    action = plan.actions[0].model_copy(update={"assumptions": []})
    report = validate_plan(plan.model_copy(update={"actions": [action]}))
    assert report.is_valid
    assert any(message.startswith("PLAN-ASSUMPTION") for message in report.warnings)


def test_plan_rejects_self_parent_and_naive_time() -> None:
    """A plan cannot be its own parent and the creation time must be timezone-aware."""
    plan = _plan()
    header = plan.header.model_copy(update={"parent_plan_id": "plan-1"})
    report = validate_plan(plan.model_copy(update={"header": header}))
    assert any(message.startswith("PLAN-VERSION") for message in report.errors)
    payload = plan.header.model_dump()
    payload["created_utc"] = datetime(2026, 11, 14)
    with pytest.raises(ValidationError):
        PlanHeader.model_validate(payload)


def test_cost_line_amount_must_match_quantity_times_rate() -> None:
    """A rate-based cost line must agree with its amount."""
    with pytest.raises(ValidationError):
        CostLine(category="labour", quantity=10.0, rate=100.0, amount=999.0)


def test_run_manifest_passes() -> None:
    """A valid run manifest passes and counts its artifacts."""
    report = validate_run_manifest(_run())
    assert report.is_valid
    assert report.counts == {"artifacts": 2, "available_artifacts": 1}


def test_run_manifest_duplicate_artifact_is_named() -> None:
    """Duplicate artifact names fail with RUN-ID."""
    run = _run()
    duplicate = run.model_copy(update={"artifacts": [run.artifacts[0], run.artifacts[0]]})
    report = validate_run_manifest(duplicate)
    assert any(message.startswith("RUN-ID") for message in report.errors)


def test_run_manifest_status_warnings() -> None:
    """A complete run with no artifact and a failed run with one are warnings."""
    run = _run()
    unavailable = [
        artifact.model_copy(update={"available": False, "sha256": None, "reason": "missing"})
        for artifact in run.artifacts
    ]
    report = validate_run_manifest(run.model_copy(update={"artifacts": unavailable}))
    assert any(message.startswith("RUN-ARTIFACT") for message in report.warnings)
    report = validate_run_manifest(run.model_copy(update={"status": "failed"}))
    assert any(message.startswith("RUN-ARTIFACT") for message in report.warnings)


def test_run_artifact_availability_and_path_are_validated() -> None:
    """An available artifact needs a hash; an unavailable one needs a reason."""
    with pytest.raises(ValidationError):
        RunArtifact(
            name="plan",
            path="plan.json",
            schema_version="brushline.plan.v1",
            media_type="application/json",
        )
    with pytest.raises(ValidationError):
        RunArtifact(
            name="plan",
            path="plan.json",
            schema_version="brushline.plan.v1",
            media_type="application/json",
            available=False,
        )
    with pytest.raises(ValidationError):
        RunArtifact(
            name="plan",
            path="../plan.json",
            schema_version="brushline.plan.v1",
            media_type="application/json",
            sha256=SHA,
        )
    with pytest.raises(ValidationError):
        RunManifest(
            run_id="run-1",
            run_type="plan",
            status="complete",
            created_utc=datetime(2026, 11, 14),
            data_version="v1",
            model_versions={"growth": "p1"},
            artifacts=[_run().artifacts[0]],
            created_by="tests",
        )


def test_pareto_archive_passes() -> None:
    """A non-dominated archive passes and counts its members."""
    report = validate_pareto_archive(_archive())
    assert report.is_valid
    assert report.counts == {"members": 2, "objectives": 2, "scalarizations": 1}


def test_pareto_dominance_is_rejected() -> None:
    """A dominated archive member fails with PARETO-DOMINANCE."""
    archive = _archive()
    dominated = ArchiveMember(
        plan_id="plan-c",
        plan_path="plans/c.json",
        objective={"present_cost": 120.0, "service_risk": 0.4},
        feasible=True,
        seed=3,
        evidence_path="evidence/c.json",
    )
    report = validate_pareto_archive(
        archive.model_copy(update={"members": [*archive.members, dominated]})
    )
    assert any(message.startswith("PARETO-DOMINANCE") for message in report.errors)
    assert not dominates(archive.members[0], archive.members[1], archive.objectives)
    assert not dominates(archive.members[1], archive.members[1], archive.objectives)


def test_pareto_objective_keys_are_checked() -> None:
    """A member with a missing or unknown objective fails."""
    archive = _archive()
    missing = archive.members[0].model_copy(update={"objective": {"present_cost": 100.0}})
    unknown = archive.members[0].model_copy(
        update={"objective": {"present_cost": 100.0, "service_risk": 0.2, "other": 1.0}}
    )
    for member in (missing, unknown):
        report = validate_pareto_archive(
            archive.model_copy(update={"members": [member, archive.members[1]]})
        )
        assert any(message.startswith("PARETO-OBJECTIVE") for message in report.errors)


def test_pareto_duplicate_ids_and_unknown_scalarization_are_named() -> None:
    """Duplicate ids and an unknown scalarization objective fail."""
    archive = _archive()
    duplicate_objective = archive.model_copy(
        update={"objectives": [archive.objectives[0], archive.objectives[0]]}
    )
    duplicate_member = archive.model_copy(
        update={"members": [archive.members[0], archive.members[0]]}
    )
    unknown_weight = archive.scalarizations[0].model_copy(
        update={"weights": {"present_cost": 0.5, "service_risk": 0.5, "other": 0.0}}
    )
    for variant in (
        duplicate_objective,
        duplicate_member,
        archive.model_copy(update={"scalarizations": [unknown_weight]}),
    ):
        report = validate_pareto_archive(variant)
        assert report.errors


def test_scalarization_weights_must_sum_to_one() -> None:
    """A scalarization with weights that do not sum to one fails at the model boundary."""
    with pytest.raises(ValidationError):
        Scalarization(
            scalarization_id="bad",
            weights={"present_cost": 0.5, "service_risk": 0.2},
        )
    with pytest.raises(ValidationError):
        Scalarization(
            scalarization_id="bad",
            weights={"present_cost": -0.1, "service_risk": 1.1},
        )


def test_empty_pareto_archive_is_a_warning() -> None:
    """An empty archive is valid but warned."""
    archive = _archive().model_copy(update={"members": []})
    report = validate_pareto_archive(archive)
    assert report.is_valid
    assert any(message.startswith("PARETO-EMPTY") for message in report.warnings)


def test_timeline_passes() -> None:
    """A valid timeline passes and counts resources and segments."""
    report = validate_timeline(_timeline(), known_segment_ids={"s1"})
    assert report.is_valid
    assert report.counts == {"events": 2, "resources": 1, "segments": 1}


def test_timeline_order_and_duplicate_ids_are_named() -> None:
    """Out-of-order events and duplicate ids fail."""
    timeline = _timeline()
    duplicate = timeline.model_copy(update={"events": [timeline.events[0], timeline.events[0]]})
    report = validate_timeline(duplicate)
    assert any(message.startswith("TIMELINE-ID") for message in report.errors)
    reversed_events = timeline.model_copy(
        update={"events": [timeline.events[1], timeline.events[0]]}
    )
    report = validate_timeline(reversed_events)
    assert any(message.startswith("TIMELINE-ORDER") for message in report.errors)


def test_timeline_references_and_open_events() -> None:
    """An unknown segment fails and an open event warns."""
    timeline = _timeline()
    unknown = timeline.events[0].model_copy(update={"segment_id": "s9"})
    report = validate_timeline(
        timeline.model_copy(update={"events": [unknown]}),
        known_segment_ids={"s1"},
    )
    assert any(message.startswith("TIMELINE-REF") for message in report.errors)
    open_event = timeline.events[0].model_copy(update={"end_utc": None})
    report = validate_timeline(timeline.model_copy(update={"events": [open_event]}))
    assert any(message.startswith("TIMELINE-OPEN") for message in report.warnings)


def test_timeline_time_validation() -> None:
    """An end before the start or a naive timestamp fails at the model boundary."""
    event = _timeline().events[0]
    with pytest.raises(ValidationError):
        TimelineEvent.model_validate(
            {**event.model_dump(), "end_utc": event.start_utc - timedelta(minutes=1)}
        )
    with pytest.raises(ValidationError):
        TimelineEvent(
            event_id="e1",
            resource_id="crew-1",
            resource_type="crew",
            segment_id="s1",
            event_type="travel",
            start_utc=datetime(2026, 7, 1, 8, 0),
            state="travel",
        )
    with pytest.raises(ValidationError):
        OperationsTimeline(
            run_id="run-1",
            events=[event],
            created_utc=datetime(2026, 7, 1, 8, 0),
            created_by="tests",
        )


def test_demo_manifest_passes() -> None:
    """A published public demo passes and counts its sources and caveats."""
    report = validate_demo_manifest(_demo())
    assert report.is_valid
    assert report.counts == {"caveats": 1, "metrics": 1, "scenarios": 2, "sources": 2}


def test_demo_status_and_optional_artifacts_warn() -> None:
    """A draft demo and a demo without archive or timeline are warnings."""
    demo = _demo()
    draft = demo.model_copy(update={"status": "draft"})
    assert any(
        message.startswith("DEMO-STATUS") for message in validate_demo_manifest(draft).warnings
    )
    artifacts = demo.artifacts.model_copy(update={"pareto": None, "timeline": None})
    report = validate_demo_manifest(demo.model_copy(update={"artifacts": artifacts}))
    assert report.is_valid
    assert any(message.startswith("DEMO-ARTIFACT") for message in report.warnings)


def test_demo_paths_and_ranges_are_validated() -> None:
    """An escaping path, an invalid id, and a missing licence fail at the model boundary."""
    with pytest.raises(ValidationError):
        DemoArtifacts(run="../run", plan="plan.json", reports="reports")
    demo = _demo()
    payload = demo.model_dump()
    payload["id"] = "Not A Slug"
    with pytest.raises(ValidationError):
        DemoManifest.model_validate(payload)
    with pytest.raises(ValidationError):
        DemoSource(name="source", licence="", version="1")
    with pytest.raises(ValidationError):
        DemoManifest(
            id="demo",
            title="Demo",
            sector="utility",
            region="BC",
            aoi="aoi.geojson",
            question="What?",
            data_sources=[DemoSource(name="s", licence="CC0", version="1")],
            scenarios=["base"],
            artifacts=DemoArtifacts(run="run", plan="plan.json", reports="reports"),
            headline_metrics=[DemoMetric(name="cost", value=1.0, unit="CAD")],
            caveats=[],
            pilot="pilot.md",
            status="published",
            created_utc=NOW,
        )

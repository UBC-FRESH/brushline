"""Deterministic synthetic corridor fixture.

The fixture is public-safe and small. It exercises the dataset, corridor, state, plan, run,
archive, timeline, and demo contracts. The generator is deterministic from its seed and a fixed
creation time, so the committed fixture and a fresh build produce the same digests.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from brushline.model.archive import (
    ArchiveMember,
    Objective,
    ParetoArchive,
    Scalarization,
    validate_pareto_archive,
)
from brushline.model.corridor import (
    AccessPoint,
    Corridor,
    CorridorNetwork,
    Segment,
    ServiceStandard,
    Span,
    Structure,
    TreatmentUnit,
    validate_corridor_network,
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
from brushline.model.schema import (
    ColumnSpec,
    DatasetManifest,
    Provenance,
    TableSpec,
    file_sha256,
    write_manifest,
)
from brushline.model.state import (
    Observation,
    StateContract,
    TreatmentAction,
    TreatmentTransition,
    Uncertainty,
    VegetationState,
    validate_state_contract,
)
from brushline.model.timeline import (
    OperationsTimeline,
    TimelineEvent,
    validate_timeline,
)

FIXTURE_SCHEMA_VERSION: Literal["brushline.fixture.v1"] = "brushline.fixture.v1"
TINY_SCHEMA_VERSION: Literal["brushline.fixture.tiny.v1"] = "brushline.fixture.tiny.v1"
DEFAULT_SEED: int = 20261114
FIXED_CREATED_UTC: datetime = datetime(2026, 11, 14, tzinfo=UTC)


@dataclass(frozen=True)
class FixtureResult:
    """The result of generating the synthetic corridor fixture.

    Parameters
    ----------
    root : Path
        Fixture directory.
    seed : int
        Fixture seed.
    artifacts : dict of str to str
        Contract artifact path to SHA-256.
    content_digest : str
        Canonical digest over the artifact list.
    expected : dict of str to int or float or str
        Expected counts and the tiny known optimum.
    """

    root: Path
    seed: int
    artifacts: dict[str, str]
    content_digest: str
    expected: dict[str, int | float | str]


def generate_fixture(
    root: Path,
    *,
    seed: int = DEFAULT_SEED,
    force: bool = False,
) -> FixtureResult:
    """Generate the synthetic corridor fixture.

    Parameters
    ----------
    root : Path
        Destination directory.
    seed : int, optional
        Fixture seed. Defaults to ``DEFAULT_SEED``.
    force : bool, optional
        Overwrite the known fixture files when the directory is not empty. Defaults to ``False``.

    Returns
    -------
    FixtureResult
        The fixture root, seed, artifact digests, content digest, and expected values.

    Raises
    ------
    FileExistsError
        When the destination is not empty and ``force`` is false.
    RuntimeError
        When a generated contract fails its own validator.
    """
    target = Path(root).expanduser().resolve()
    if target.exists() and any(target.iterdir()) and not force:
        raise FileExistsError(f"{target} is not empty; pass force=True to overwrite")
    target.mkdir(parents=True, exist_ok=True)

    network = _corridor_network()
    corridor_report = validate_corridor_network(network)
    if not corridor_report.is_valid:
        raise RuntimeError("; ".join(corridor_report.errors))
    _write_json(target / "corridor.json", network.model_dump(mode="json"))

    state_contract = _state_contract()
    state_report = validate_state_contract(
        state_contract,
        required_segment_ids={"s1", "s2", "s3", "s4", "s5"},
    )
    if not state_report.is_valid:
        raise RuntimeError("; ".join(state_report.errors))
    _write_json(target / "state.json", state_contract.model_dump(mode="json"))

    dataset_manifest = _dataset_manifest(target)
    plan = _plan(dataset_manifest.content_digest)
    plan_report = validate_plan(plan, known_segment_ids={"s1", "s2", "s3", "s4", "s5"})
    if not plan_report.is_valid:
        raise RuntimeError("; ".join(plan_report.errors))
    _write_json(target / "plan.json", plan.model_dump(mode="json"))

    archive = _archive(target, dataset_manifest.content_digest, seed)
    archive_report = validate_pareto_archive(archive)
    if not archive_report.is_valid:
        raise RuntimeError("; ".join(archive_report.errors))
    _write_json(target / "pareto.json", archive.model_dump(mode="json"))

    timeline = _timeline()
    timeline_report = validate_timeline(timeline, known_segment_ids={"s1", "s2", "s3", "s4", "s5"})
    if not timeline_report.is_valid:
        raise RuntimeError("; ".join(timeline_report.errors))
    _write_jsonl(
        target / "operations_timeline.jsonl",
        [event.model_dump(mode="json") for event in timeline.events],
    )

    _write_geojson(target / "aoi.geojson")
    _write_text(target / "reports" / "summary.md", _report_text(plan))
    _write_text(target / "pilot.md", _pilot_text())
    _write_text(target / "README.md", _readme_text())

    tiny = _tiny_optimum()
    _write_json(target / "tiny_optimum.json", tiny)

    demo = _demo(plan, seed)
    demo_report = validate_demo_manifest(demo)
    if not demo_report.is_valid:
        raise RuntimeError("; ".join(demo_report.errors))
    _write_json(target / "demo.json", demo.model_dump(mode="json"))

    entries: dict[str, dict[str, str]] = {}

    def record(relative: str, schema_version: str) -> None:
        path = target / relative
        entries[relative] = {
            "path": relative,
            "schema_version": schema_version,
            "sha256": file_sha256(path),
        }

    record("dataset/manifest.json", "brushline.dataset.v1")
    record("dataset/segments.csv", "brushline.dataset.table.v1")
    record("corridor.json", "brushline.corridor.v1")
    record("state.json", "brushline.state.v1")
    record("plan.json", "brushline.plan.v1")
    record("pareto.json", "brushline.pareto.v1")
    record("operations_timeline.jsonl", "brushline.timeline.v1")
    record("demo.json", "brushline.demo.v1")
    record("tiny_optimum.json", TINY_SCHEMA_VERSION)
    record("plans/plan-a.json", "brushline.plan.v1")
    record("plans/plan-b.json", "brushline.plan.v1")
    record("plans/plan-c.json", "brushline.plan.v1")
    record("evidence/plan-a.json", "brushline.evidence.v1")
    record("evidence/plan-b.json", "brushline.evidence.v1")
    record("evidence/plan-c.json", "brushline.evidence.v1")

    run = _run(entries)
    run_report = validate_run_manifest(run)
    if not run_report.is_valid:
        raise RuntimeError("; ".join(run_report.errors))
    _write_json(target / "run.json", run.model_dump(mode="json"))
    record("run.json", "brushline.run.v1")

    artifact_list = [entries[path] for path in sorted(entries)]
    content_digest = _canonical_digest(artifact_list)
    expected: dict[str, int | float | str] = {
        "corridors": 2,
        "segments": 5,
        "states": 5,
        "treatments": 3,
        "observations": 4,
        "structures": 1,
        "access_gaps": 1,
        "monitoring_gaps": 1,
        "plan_actions": 5,
        "pareto_members": 3,
        "timeline_events": 5,
        "known_optimum": "mow-2026",
        "known_optimum_penalty": 0.46,
    }
    fixture_manifest: dict[str, object] = {
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "fixture_id": "synthetic-corridor",
        "seed": seed,
        "created_utc": FIXED_CREATED_UTC.isoformat(),
        "generator": "brushline.fixtures.synthetic.generate_fixture",
        "expected": expected,
        "artifacts": artifact_list,
        "content_digest": content_digest,
    }
    _write_json(target / "fixture.json", fixture_manifest)
    return FixtureResult(
        root=target,
        seed=seed,
        artifacts={item["path"]: item["sha256"] for item in artifact_list},
        content_digest=content_digest,
        expected=expected,
    )


def load_fixture_manifest(root: Path) -> dict[str, object]:
    """Load a fixture manifest.

    Parameters
    ----------
    root : Path
        Fixture directory.

    Returns
    -------
    dict of str to object
        The parsed manifest.
    """
    path = Path(root).expanduser().resolve() / "fixture.json"
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return value


def _corridor_network() -> CorridorNetwork:
    return CorridorNetwork(
        crs="EPSG:3005",
        corridors=[
            Corridor(
                corridor_id="c1",
                name="Synthetic transmission corridor",
                asset_type="transmission",
                length_m=300.0,
                crs="EPSG:3005",
            ),
            Corridor(
                corridor_id="c2",
                name="Synthetic pipeline corridor",
                asset_type="pipeline",
                length_m=200.0,
                crs="EPSG:3005",
            ),
        ],
        segments=[
            Segment(
                segment_id="s1",
                corridor_id="c1",
                span_id="sp1",
                treatment_unit_id="tu1",
                sequence=0,
                length_m=100.0,
                geometry_wkt="LINESTRING (0 0, 100 0)",
                service_standard_id="std1",
                access_point_id="ap1",
                structure_ids=["st1"],
            ),
            Segment(
                segment_id="s2",
                corridor_id="c1",
                span_id="sp1",
                treatment_unit_id="tu1",
                sequence=1,
                length_m=100.0,
                geometry_wkt="LINESTRING (100 0, 200 0)",
                service_standard_id="std1",
                access_point_id="ap1",
            ),
            Segment(
                segment_id="s3",
                corridor_id="c1",
                span_id="sp1",
                treatment_unit_id="tu1",
                sequence=2,
                length_m=100.0,
                geometry_wkt="LINESTRING (200 0, 300 0)",
                service_standard_id="std1",
            ),
            Segment(
                segment_id="s4",
                corridor_id="c2",
                span_id="sp2",
                treatment_unit_id="tu2",
                sequence=0,
                length_m=100.0,
                geometry_wkt="LINESTRING (0 100, 100 100)",
                service_standard_id="std2",
                access_point_id="ap2",
            ),
            Segment(
                segment_id="s5",
                corridor_id="c2",
                span_id="sp2",
                treatment_unit_id="tu2",
                sequence=1,
                length_m=100.0,
                geometry_wkt="LINESTRING (100 100, 200 100)",
                service_standard_id="std2",
                access_point_id="ap2",
            ),
        ],
        spans=[
            Span(span_id="sp1", corridor_id="c1", segment_ids=["s1", "s2", "s3"]),
            Span(
                span_id="sp2", corridor_id="c2", segment_ids=["s4", "s5"], access_point_ids=["ap2"]
            ),
        ],
        treatment_units=[
            TreatmentUnit(
                treatment_unit_id="tu1",
                corridor_id="c1",
                segment_ids=["s1", "s2", "s3"],
                contract_start_year=2026,
                contract_end_year=2030,
            ),
            TreatmentUnit(
                treatment_unit_id="tu2",
                corridor_id="c2",
                segment_ids=["s4", "s5"],
                contract_start_year=2026,
                contract_end_year=2028,
            ),
        ],
        access_points=[
            AccessPoint(
                access_point_id="ap1",
                corridor_id="c1",
                kind="road",
                location_wkt="POINT (0 0)",
            ),
            AccessPoint(
                access_point_id="ap2",
                corridor_id="c2",
                kind="trail",
                location_wkt="POINT (200 100)",
            ),
        ],
        structures=[
            Structure(
                structure_id="st1",
                corridor_id="c1",
                segment_id="s1",
                structure_type="tower",
                clearance_m=6.0,
            )
        ],
        service_standards=[
            ServiceStandard(
                service_standard_id="std1",
                max_height_m=3.0,
                min_clearance_m=6.0,
            ),
            ServiceStandard(
                service_standard_id="std2",
                max_height_m=1.5,
                min_clearance_m=4.0,
            ),
        ],
    )


def _state_contract() -> StateContract:
    return StateContract(
        states=[
            VegetationState(
                segment_id="s1",
                state_year=2026,
                functional_group="shrub",
                state_class="shrub",
                height_m=2.0,
                cover_pct=50.0,
                density_per_ha=1200.0,
                age_years=3,
                uncertainty=Uncertainty(height_m_sd=0.2, cover_pct_sd=5.0, confidence=0.9),
                source="synthetic",
                source_version="1.0",
            ),
            VegetationState(
                segment_id="s2",
                state_year=2026,
                functional_group="deciduous_sprout",
                state_class="mixed",
                height_m=1.8,
                cover_pct=40.0,
                density_per_ha=900.0,
                age_years=2,
                uncertainty=Uncertainty(confidence=0.7),
                source="synthetic",
                source_version="1.0",
            ),
            VegetationState(
                segment_id="s3",
                state_year=2026,
                functional_group="unknown",
                state_class="unknown",
                height_m=0.0,
                cover_pct=0.0,
                uncertainty=Uncertainty(confidence=0.1),
                source="synthetic",
                source_version="1.0",
            ),
            VegetationState(
                segment_id="s4",
                state_year=2026,
                functional_group="grass_herb",
                state_class="grass_herb",
                height_m=0.5,
                cover_pct=70.0,
                age_years=1,
                uncertainty=Uncertainty(confidence=0.8),
                source="synthetic",
                source_version="1.0",
            ),
            VegetationState(
                segment_id="s5",
                state_year=2026,
                functional_group="conifer",
                state_class="young_tree",
                height_m=1.2,
                cover_pct=30.0,
                density_per_ha=600.0,
                age_years=2,
                uncertainty=Uncertainty(confidence=0.8),
                source="synthetic",
                source_version="1.0",
            ),
        ],
        treatments=[
            TreatmentAction(
                action_id="a1",
                segment_id="s1",
                year=2025,
                season="summer",
                method="mowing",
                intensity=0.8,
                efficacy=0.75,
                cost_per_ha=1200.0,
                status="applied",
            ),
            TreatmentAction(
                action_id="a2",
                segment_id="s2",
                year=2026,
                season="summer",
                method="manual",
                intensity=0.6,
                efficacy=0.6,
                cost_per_ha=900.0,
                status="planned",
            ),
            TreatmentAction(
                action_id="a3",
                segment_id="s5",
                year=2026,
                season="fall",
                method="manual",
                intensity=0.5,
                efficacy=0.55,
                cost_per_ha=800.0,
                status="planned",
            ),
        ],
        transitions=[
            TreatmentTransition(
                transition_id="t1",
                segment_id="s1",
                year=2025,
                method="mowing",
                before_height_m=2.4,
                after_height_m=0.6,
                before_cover_pct=60.0,
                after_cover_pct=15.0,
                efficacy=0.75,
                regrowth_delay_years=2,
                source="synthetic",
            )
        ],
        observations=[
            Observation(
                observation_id="o1",
                segment_id="s1",
                observed_date=datetime(2026, 6, 1, tzinfo=UTC).date(),
                sensor="lidar",
                product="CHM",
                coverage_pct=100.0,
                height_m=2.0,
                cover_pct=50.0,
                height_error_m=0.2,
                cover_error_pct=5.0,
                source="synthetic",
                source_version="1.0",
            ),
            Observation(
                observation_id="o2",
                segment_id="s2",
                observed_date=datetime(2026, 6, 1, tzinfo=UTC).date(),
                sensor="lidar",
                product="CHM",
                coverage_pct=40.0,
                height_m=1.8,
                cover_pct=40.0,
                height_error_m=0.2,
                cover_error_pct=5.0,
                source="synthetic",
                source_version="1.0",
            ),
            Observation(
                observation_id="o3",
                segment_id="s4",
                observed_date=datetime(2026, 6, 15, tzinfo=UTC).date(),
                sensor="field",
                product="plot",
                coverage_pct=100.0,
                height_m=0.5,
                cover_pct=70.0,
                cover_error_pct=10.0,
                source="synthetic",
                source_version="1.0",
            ),
            Observation(
                observation_id="o4",
                segment_id="s5",
                observed_date=datetime(2026, 6, 20, tzinfo=UTC).date(),
                sensor="uav_lidar",
                product="CHM",
                coverage_pct=100.0,
                height_m=1.2,
                cover_pct=30.0,
                height_error_m=0.15,
                cover_error_pct=4.0,
                source="synthetic",
                source_version="1.0",
            ),
        ],
    )


def _dataset_manifest(root: Path) -> DatasetManifest:
    dataset_dir = root / "dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    table_path = dataset_dir / "segments.csv"
    rows = [
        ("s1", "c1", "100.0", "LINESTRING (0 0, 100 0)"),
        ("s2", "c1", "100.0", "LINESTRING (100 0, 200 0)"),
        ("s3", "c1", "100.0", "LINESTRING (200 0, 300 0)"),
        ("s4", "c2", "100.0", "LINESTRING (0 100, 100 100)"),
        ("s5", "c2", "100.0", "LINESTRING (100 100, 200 100)"),
    ]
    with table_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["segment_id", "corridor_id", "length_m", "geometry_wkt"])
        writer.writerows(rows)
    table = TableSpec(
        name="segments",
        path="segments.csv",
        format="csv",
        primary_key=["segment_id"],
        columns=[
            ColumnSpec(name="segment_id", dtype="string"),
            ColumnSpec(name="corridor_id", dtype="string"),
            ColumnSpec(name="length_m", dtype="float64", unit="m"),
            ColumnSpec(name="geometry_wkt", dtype="string"),
        ],
        row_count=len(rows),
        sha256=file_sha256(table_path),
    )
    manifest = DatasetManifest(
        dataset_id="synthetic-corridor",
        name="Synthetic corridor dataset",
        description="A small two-corridor contract fixture.",
        created_utc=FIXED_CREATED_UTC,
        crs="EPSG:3005",
        units={"length": "m", "area": "ha"},
        tables=[table],
        provenance=Provenance(
            source="synthetic",
            source_version="1.0",
            licence="CC0-1.0",
            created_by="brushline.fixtures.synthetic",
        ),
        content_digest="0" * 64,
    )
    manifest.content_digest = manifest.compute_content_digest()
    write_manifest(dataset_dir, manifest)
    return manifest


def _plan(dataset_digest: str) -> Plan:
    header = PlanHeader(
        plan_id="plan-2026",
        version=1,
        status="proposed",
        scenario_id="scenario-2026",
        dataset_id="synthetic-corridor",
        data_version=f"sha256:{dataset_digest}",
        model_versions={"growth": "p1-prototype", "treatment": "p1-prototype"},
        currency="CAD",
        created_utc=FIXED_CREATED_UTC,
        created_by="brushline.fixtures.synthetic",
        seed=DEFAULT_SEED,
    )
    actions = [
        _plan_action("pa1", "s1", 2026, "summer", "mowing", 0.8, 1500.0),
        _plan_action("pa2", "s2", 2026, "summer", "manual", 0.6, 900.0),
        _plan_action("pa3", "s3", 2027, "summer", "mowing", 0.8, 1500.0),
        _plan_action("pa4", "s4", 2026, "fall", "mowing", 0.7, 600.0),
        _plan_action("pa5", "s5", 2026, "summer", "manual", 0.5, 800.0),
    ]
    return Plan(
        header=header,
        actions=actions,
        assumptions=[
            PlanAssumption(
                assumption_id="as1",
                statement="Synthetic rates; not a real contract price.",
                source="brushline.fixtures.synthetic",
            )
        ],
    )


def _plan_action(
    action_id: str,
    segment_id: str,
    year: int,
    season: Literal["spring", "summer", "fall", "winter", "any"],
    method: Literal[
        "manual", "mechanical", "chemical", "mowing", "grazing", "prescribed_fire", "other"
    ],
    intensity: float,
    amount: float,
) -> PlanAction:
    return PlanAction(
        action_id=action_id,
        segment_id=segment_id,
        year=year,
        season=season,
        method=method,
        intensity=intensity,
        cost_lines=[
            CostLine(
                category="labour",
                amount=amount,
                description="Synthetic treatment cost.",
                source="synthetic",
            )
        ],
        quantity_ha=1.0,
        assumptions=["Synthetic rate; not a real contract price."],
    )


def _archive(root: Path, dataset_digest: str, seed: int) -> ParetoArchive:
    plans = [
        ("plan-a", 5300.0, 0.12, "plan-a"),
        ("plan-b", 4700.0, 0.16, "plan-b"),
        ("plan-c", 4300.0, 0.22, "plan-c"),
    ]
    members: list[ArchiveMember] = []
    for plan_id, cost, risk, slug in plans:
        plan = _archive_plan(plan_id, dataset_digest, cost)
        plan_path = f"plans/{slug}.json"
        _write_json(root / plan_path, plan.model_dump(mode="json"))
        evidence_path = f"evidence/{slug}.json"
        _write_json(
            root / evidence_path,
            {
                "schema_version": "brushline.evidence.v1",
                "plan_id": plan_id,
                "seed": seed,
                "objective": {"present_cost": cost, "service_risk": risk},
            },
        )
        members.append(
            ArchiveMember(
                plan_id=plan_id,
                plan_path=plan_path,
                objective={"present_cost": cost, "service_risk": risk},
                feasible=True,
                seed=seed,
                evidence_path=evidence_path,
                budget=1000,
            )
        )
    return ParetoArchive(
        instance_id="synthetic-corridor",
        run_id="run-2026",
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
        members=members,
        eviction="crowding-distance",
        created_utc=FIXED_CREATED_UTC,
        created_by="brushline.fixtures.synthetic",
    )


def _archive_plan(plan_id: str, dataset_digest: str, amount: float) -> Plan:
    header = PlanHeader(
        plan_id=plan_id,
        version=1,
        status="proposed",
        scenario_id="scenario-2026",
        dataset_id="synthetic-corridor",
        data_version=f"sha256:{dataset_digest}",
        model_versions={"growth": "p1-prototype", "treatment": "p1-prototype"},
        currency="CAD",
        created_utc=FIXED_CREATED_UTC,
        created_by="brushline.fixtures.synthetic",
        seed=DEFAULT_SEED,
    )
    return Plan(
        header=header,
        actions=[_plan_action(f"{plan_id}-a1", "s1", 2026, "summer", "mowing", 0.8, amount)],
        assumptions=[
            PlanAssumption(
                assumption_id="as1",
                statement="Synthetic archive plan; not a real contract price.",
                source="brushline.fixtures.synthetic",
            )
        ],
    )


def _timeline() -> OperationsTimeline:
    start = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    events = [
        TimelineEvent(
            event_id="e1",
            resource_id="crew-1",
            resource_type="crew",
            segment_id="s1",
            event_type="travel",
            start_utc=start,
            end_utc=start.replace(hour=8, minute=20),
            state="travel",
        ),
        TimelineEvent(
            event_id="e2",
            resource_id="crew-1",
            resource_type="crew",
            segment_id="s1",
            event_type="treatment",
            start_utc=start.replace(hour=8, minute=20),
            end_utc=start.replace(hour=9, minute=20),
            state="working",
            action_id="pa1",
            cost=1500.0,
        ),
        TimelineEvent(
            event_id="e3",
            resource_id="crew-1",
            resource_type="crew",
            segment_id="s2",
            event_type="treatment",
            start_utc=start.replace(hour=9, minute=40),
            end_utc=start.replace(hour=10, minute=40),
            state="working",
            action_id="pa2",
            cost=900.0,
        ),
        TimelineEvent(
            event_id="e4",
            resource_id="crew-2",
            resource_type="crew",
            segment_id="s4",
            event_type="treatment",
            start_utc=start.replace(hour=11, minute=0),
            end_utc=start.replace(hour=11, minute=40),
            state="working",
            action_id="pa4",
            cost=600.0,
        ),
        TimelineEvent(
            event_id="e5",
            resource_id="crew-2",
            resource_type="crew",
            segment_id="s5",
            event_type="treatment",
            start_utc=start.replace(hour=13, minute=0),
            end_utc=start.replace(hour=14, minute=0),
            state="working",
            action_id="pa5",
            cost=800.0,
        ),
    ]
    return OperationsTimeline(
        run_id="run-2026",
        events=events,
        created_utc=FIXED_CREATED_UTC,
        created_by="brushline.fixtures.synthetic",
    )


def _run(entries: dict[str, dict[str, str]]) -> RunManifest:
    artifacts = [
        RunArtifact(
            name=name,
            path=path,
            schema_version=entries[path]["schema_version"],
            media_type=_media_type(path),
            sha256=entries[path]["sha256"],
        )
        for name, path in [
            ("plan", "plan.json"),
            ("corridor", "corridor.json"),
            ("state", "state.json"),
            ("pareto", "pareto.json"),
            ("timeline", "operations_timeline.jsonl"),
            ("demo", "demo.json"),
            ("dataset", "dataset/manifest.json"),
        ]
    ]
    return RunManifest(
        run_id="run-2026",
        run_type="plan",
        status="complete",
        created_utc=FIXED_CREATED_UTC,
        data_version="sha256:synthetic-corridor",
        model_versions={"growth": "p1-prototype", "treatment": "p1-prototype"},
        artifacts=artifacts,
        created_by="brushline.fixtures.synthetic",
        seed=DEFAULT_SEED,
        summary={"plan_id": "plan-2026", "actions": 5},
    )


def _demo(plan: Plan, seed: int) -> DemoManifest:
    return DemoManifest(
        id="synthetic-corridor",
        title="Synthetic corridor",
        sector="utility",
        region="British Columbia",
        aoi="aoi.geojson",
        question="What does a risk-ranked treatment plan look like on a small synthetic corridor?",
        data_sources=[
            DemoSource(
                name="Synthetic corridor",
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
            DemoMetric(name="present_cost", value=plan.total_cost, unit="CAD"),
            DemoMetric(name="service_risk", value=0.12, unit="index"),
        ],
        caveats=[
            "Synthetic geometry and synthetic costs; not an operational plan.",
            "The state and treatment models are P1 prototypes, not the calibrated P4 model.",
        ],
        pilot="pilot.md",
        status="published",
        created_utc=FIXED_CREATED_UTC,
        contact="pilot@example.org",
    )


def _tiny_optimum() -> dict[str, object]:
    return {
        "schema_version": TINY_SCHEMA_VERSION,
        "segment_id": "s1",
        "seed": DEFAULT_SEED,
        "objective": {"cost_weight": 0.4, "risk_weight": 0.6, "cost_scale": 1000.0},
        "options": [
            {"option_id": "none", "cost": 0.0, "risk": 0.8},
            {"option_id": "mow-2026", "cost": 1000.0, "risk": 0.1},
            {"option_id": "mow-2027", "cost": 900.0, "risk": 0.2},
        ],
        "optimum": "mow-2026",
        "optimum_penalty": 0.46,
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row, sort_keys=True) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_geojson(path: Path) -> None:
    _write_json(
        path,
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": "Synthetic corridor AOI"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [[0.0, 0.0], [300.0, 0.0], [300.0, 100.0], [0.0, 100.0], [0.0, 0.0]]
                        ],
                    },
                }
            ],
        },
    )


def _canonical_digest(artifacts: list[dict[str, str]]) -> str:
    encoded = json.dumps(artifacts, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _media_type(path: str) -> str:
    if path.endswith(".json"):
        return "application/json"
    if path.endswith(".jsonl"):
        return "application/jsonl"
    if path.endswith(".csv"):
        return "text/csv"
    if path.endswith(".geojson"):
        return "application/geo+json"
    return "text/plain"


def _report_text(plan: Plan) -> str:
    return (
        "# Synthetic corridor run report\n\n"
        f"- Plan: {plan.header.plan_id} v{plan.header.version}\n"
        f"- Actions: {len(plan.actions)}\n"
        f"- Total cost: {plan.total_cost:.2f} {plan.header.currency}\n"
        "- Caveat: synthetic data and synthetic costs.\n"
    )


def _pilot_text() -> str:
    return (
        "# Synthetic corridor pilot brief\n\n"
        "This fixture is a public-safe demonstration. A real pilot would replace the synthetic\n"
        "geometry, costs, and observations with the owner's corridor data and a reviewed "
        "model card.\n"
    )


def _readme_text() -> str:
    return (
        "# Synthetic corridor fixture\n\n"
        "Generated by `brushline.fixtures.synthetic.generate_fixture`. Do not edit by hand.\n\n"
        "The fixture covers two corridors, five segments, five state groups, one access gap,\n"
        "one monitoring gap, one structure, a plan, a Pareto archive, an operations timeline,\n"
        "a demo manifest, and a tiny known-optimum case.\n\n"
        "Validate the dataset with:\n\n"
        "```bash\n"
        "brushline validate --dataset examples/synthetic-corridor/dataset\n"
        "```\n"
    )


__all__ = [
    "DEFAULT_SEED",
    "FIXED_CREATED_UTC",
    "FIXTURE_SCHEMA_VERSION",
    "TINY_SCHEMA_VERSION",
    "FixtureResult",
    "generate_fixture",
    "load_fixture_manifest",
]

"""Tests for the plan-only fetch, materialization, coverage, and gap contracts."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from brushline.integrations.catalogue import (
    ConnectorApproval,
    DataCatalogue,
    UnknownCatalogueReferenceError,
)
from brushline.integrations.fetch import (
    CoverageEntry,
    CoverageReport,
    FetchApproval,
    FetchEstimate,
    FetchPlan,
    FetchRequest,
    GapRecord,
    MaterializationManifest,
    MaterializedItem,
    build_gap_report,
    coverage_counts,
    default_estimate,
    file_sha256,
    materialization_decision,
    plan_fetch,
    validate_coverage,
    validate_fetch_plan,
    validate_gap_report,
    validate_materialization,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE_PATH = ROOT / "notes" / "reference" / "data-catalogue.v1.json"
NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _catalogue() -> DataCatalogue:
    return DataCatalogue.model_validate_json(CATALOGUE_PATH.read_text(encoding="utf-8"))


def _approved_catalogue() -> DataCatalogue:
    catalogue = _catalogue()
    connector = catalogue.connectors[0]
    approval = ConnectorApproval(
        approved_by="owner",
        approved_utc=NOW,
        data_sharing_record="data-sharing-record-1",
    )
    connectors = [
        connector.model_copy(update={"approval": approval}) if item.id == "asset-registry" else item
        for item in catalogue.connectors
    ]
    return catalogue.model_copy(update={"connectors": connectors})


def _request(**updates: object) -> FetchRequest:
    values: dict[str, object] = {
        "aoi": "aoi.geojson",
        "source_ids": ["vri"],
    }
    values.update(updates)
    return FetchRequest(**values)  # type: ignore[arg-type]  # Explicit test overrides mirror fields.


def _plan(**updates: object) -> FetchPlan:
    return plan_fetch(
        _catalogue(),
        _request(**updates),
        plan_id="plan-1",
        created_utc=NOW,
    )


def _replace_item(plan: FetchPlan, **updates: object) -> FetchPlan:
    item = plan.items[0].model_copy(update=updates)
    return plan.model_copy(update={"items": [item, *plan.items[1:]]})


def _manifest(root: Path, **updates: object) -> MaterializationManifest:
    payload = root / "data" / "vri.txt"
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_text("vri payload\n", encoding="utf-8")
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    values: dict[str, object] = {
        "id": "vri",
        "source_id": "vri",
        "path": "data/vri.txt",
        "sha256": digest,
        "size_bytes": payload.stat().st_size,
        "retrieved_utc": NOW,
        "licence": "OGL-BC",
        "pointer": "public_mirror:inputs/vri",
    }
    values.update(updates)
    return MaterializationManifest(
        plan_id="plan-1",
        created_utc=NOW,
        items=[MaterializedItem(**values)],  # type: ignore[arg-type]  # Dynamic test overrides.
    )


def _coverage(*entries: CoverageEntry) -> CoverageReport:
    return CoverageReport(
        plan_id="plan-1",
        created_utc=NOW,
        aoi="aoi.geojson",
        entries=list(entries),
    )


def test_plan_fetch_copies_catalogue_metadata_and_estimates() -> None:
    """A plan-only request resolves sources, defaults, pointers, and totals."""
    plan = plan_fetch(
        _catalogue(),
        FetchRequest(
            aoi="aoi.geojson",
            source_ids=["vri", "lidarbc"],
            queries={"vri": "VRI in the AOI"},
            estimates={"lidarbc": FetchEstimate(size_mb=12, seconds=9, basis="user")},
            optional_ids=["lidarbc"],
        ),
        plan_id="plan-1",
        created_utc=NOW,
    )
    assert plan.mode == "plan_only"
    assert plan.total_size_mb == 62
    assert plan.total_seconds == 69
    assert plan.network_items == 2
    vri, lidar = plan.items
    assert vri.query == "VRI in the AOI"
    assert vri.estimated_size_mb == 50
    assert vri.estimate_basis == "planning_default"
    assert vri.materialization == "public_mirror"
    assert vri.materialization_pointer == "public_mirror:inputs/vri"
    assert vri.required is True
    assert lidar.estimated_size_mb == 12
    assert lidar.estimate_basis == "user"
    assert lidar.materialization == "data_lad"
    assert lidar.materialization_pointer == "data_lad:inputs/lidarbc"
    assert lidar.required is False
    report = validate_fetch_plan(plan, _catalogue())
    assert report.is_valid
    assert report.counts["sources"] == 2
    assert report.counts["bulk_items"] == 0


def test_plan_fetch_uses_defaults_for_every_access_method() -> None:
    """The default estimate table covers the public access methods."""
    expected = {
        "bulk_download": (5000, 3600, "planning_default"),
        "stac": (200, 120, "planning_default"),
        "wfs": (50, 60, "planning_default"),
        "wms": (10, 30, "planning_default"),
        "api": (50, 60, "planning_default"),
        "rest": (50, 60, "planning_default"),
        "manual": (0, 0, "manual"),
        "unknown": (0, 0, "unknown"),
        "other": (0, 0, "unknown"),
    }
    for method, (size, seconds, basis) in expected.items():
        estimate = default_estimate(method)
        assert (estimate.size_mb, estimate.seconds, estimate.basis) == (
            size,
            seconds,
            basis,
        )


def test_unapproved_connector_is_blocked_in_the_plan() -> None:
    """A private connector without owner approval is planned but blocked."""
    plan = plan_fetch(
        _catalogue(),
        FetchRequest(aoi="aoi.geojson", connector_ids=["asset-registry"]),
        plan_id="plan-1",
        created_utc=NOW,
    )
    item = plan.items[0]
    assert item.kind == "connector"
    assert item.access_status == "blocked"
    assert item.materialization == "owner_store"
    assert item.materialization_pointer == "owner_store:asset-registry"
    report = validate_fetch_plan(plan, _catalogue())
    assert any(error.startswith("FETCH-CONNECTOR") for error in report.errors)


def test_approved_connector_is_available_in_the_plan() -> None:
    """An approved connector is available and carries the sharing record."""
    catalogue = _approved_catalogue()
    plan = plan_fetch(
        catalogue,
        FetchRequest(aoi="aoi.geojson", connector_ids=["asset-registry"]),
        plan_id="plan-1",
        created_utc=NOW,
    )
    item = plan.items[0]
    assert item.access_status == "available"
    assert item.licence == "data-sharing-record-1"
    report = validate_fetch_plan(plan, catalogue)
    assert report.is_valid
    assert report.counts["connectors"] == 1


def test_unknown_source_and_connector_raise() -> None:
    """A request for an unregistered id fails before a plan is built."""
    with pytest.raises(UnknownCatalogueReferenceError, match="unknown source"):
        plan_fetch(
            _catalogue(),
            FetchRequest(aoi="aoi.geojson", source_ids=["missing"]),
            plan_id="plan-1",
            created_utc=NOW,
        )
    with pytest.raises(UnknownCatalogueReferenceError, match="unknown connector"):
        plan_fetch(
            _catalogue(),
            FetchRequest(aoi="aoi.geojson", connector_ids=["missing"]),
            plan_id="plan-1",
            created_utc=NOW,
        )


def test_bulk_fetch_requires_explicit_bulk_approval() -> None:
    """A bulk item without a bulk approval fails; a complete one passes."""
    missing = _plan(bulk=True)
    missing_report = validate_fetch_plan(missing, _catalogue())
    assert any(error.startswith("FETCH-APPROVAL") for error in missing_report.errors)

    wrong_scope = _plan(
        bulk=True,
        approvals={
            "vri": FetchApproval(
                approved_by="owner",
                approved_utc=NOW,
                scope="single",
                record="approval-1",
            )
        },
    )
    wrong_report = validate_fetch_plan(wrong_scope, _catalogue())
    assert any(error.startswith("FETCH-APPROVAL") for error in wrong_report.errors)

    approved = _plan(
        bulk=True,
        approvals={
            "vri": FetchApproval(
                approved_by="owner",
                approved_utc=NOW,
                scope="bulk",
                record="approval-1",
            )
        },
    )
    approved_report = validate_fetch_plan(approved, _catalogue())
    assert approved_report.is_valid
    assert approved_report.counts["bulk_items"] == 1


def test_incomplete_approval_fails() -> None:
    """An approval without an approver, record, or timezone fails."""
    plan = _plan(
        bulk=True,
        approvals={
            "vri": FetchApproval(
                approved_by="",
                approved_utc=datetime(2026, 11, 14),
                scope="bulk",
                record="",
            )
        },
    )
    report = validate_fetch_plan(plan, _catalogue())
    errors = [error for error in report.errors if error.startswith("FETCH-APPROVAL")]
    assert len(errors) == 3


def test_plan_validation_names_bad_items_and_metadata() -> None:
    """Unknown kind, licence, classification, access, estimate, and pointer fail."""
    plan = _plan()
    item = plan.items[0].model_copy(
        update={
            "kind": "unknown",
            "licence": "",
            "classification": "alien",
            "access_status": "maybe",
            "estimated_size_mb": -1,
            "materialization": "unknown",
            "materialization_pointer": "wrong:pointer",
        }
    )
    report = validate_fetch_plan(
        plan.model_copy(update={"items": [item]}),
        _catalogue(),
    )
    prefixes = {error.split(":", 1)[0] for error in report.errors}
    for prefix in (
        "FETCH-KIND",
        "FETCH-LICENCE",
        "FETCH-CLASSIFICATION",
        "FETCH-ACCESS",
        "FETCH-ESTIMATE",
        "FETCH-MATERIALIZATION",
    ):
        assert prefix in prefixes


def test_plan_validation_rejects_duplicates_and_naive_time() -> None:
    """A duplicate item and a naive creation time fail."""
    plan = _plan()
    duplicate = plan.model_copy(update={"items": [plan.items[0], plan.items[0]]})
    naive = plan.model_copy(update={"created_utc": datetime(2026, 11, 14)})
    assert any(error.startswith("FETCH-ID") for error in validate_fetch_plan(duplicate).errors)
    assert any(error.startswith("FETCH-TIME") for error in validate_fetch_plan(naive).errors)


def test_plan_validation_warns_for_an_empty_plan_and_uncertain_access() -> None:
    """An empty plan and an uncertain source are warnings, not errors."""
    empty = FetchPlan(plan_id="plan-1", created_utc=NOW, aoi="aoi.geojson")
    empty_report = validate_fetch_plan(empty)
    assert empty_report.is_valid
    assert any(warning.startswith("FETCH-EMPTY") for warning in empty_report.warnings)
    request = plan_fetch(
        _catalogue(),
        FetchRequest(aoi="aoi.geojson", source_ids=["vdyp"]),
        plan_id="plan-1",
        created_utc=NOW,
    )
    request_report = validate_fetch_plan(request, _catalogue())
    assert any(warning.startswith("FETCH-ACCESS") for warning in request_report.warnings)


def test_plan_validation_checks_catalogue_drift_and_unknown_items() -> None:
    """A changed licence or classification is a drift error; unknown ids fail."""
    plan = _plan()
    drift = _replace_item(plan, licence="different-licence")
    drift_report = validate_fetch_plan(drift, _catalogue())
    assert any(error.startswith("FETCH-DRIFT") for error in drift_report.errors)
    unknown = _replace_item(plan, reference_id="missing")
    unknown_report = validate_fetch_plan(unknown, _catalogue())
    assert any(error.startswith("FETCH-SOURCE") for error in unknown_report.errors)
    connector_plan = plan_fetch(
        _catalogue(),
        FetchRequest(aoi="aoi.geojson", connector_ids=["asset-registry"]),
        plan_id="plan-1",
        created_utc=NOW,
    )
    unknown_connector = _replace_item(connector_plan, reference_id="missing")
    unknown_connector_report = validate_fetch_plan(unknown_connector, _catalogue())
    assert any(error.startswith("FETCH-CONNECTOR") for error in unknown_connector_report.errors)


def test_materialization_valid_manifest_continues(tmp_path: Path) -> None:
    """A matching file, checksum, size, licence, and pointer continues."""
    manifest = _manifest(tmp_path)
    report = validate_materialization(manifest, tmp_path)
    assert report.is_valid
    assert report.counts["materialized"] == 1
    assert materialization_decision(manifest, tmp_path) == "continue"


def test_materialization_checksum_and_size_mismatch_stop(tmp_path: Path) -> None:
    """A checksum or size mismatch stops materialization."""
    manifest = _manifest(tmp_path)
    bad_checksum = manifest.items[0].model_copy(update={"sha256": "0" * 64})
    bad_size = manifest.items[0].model_copy(update={"size_bytes": 1})
    for item, prefix in (
        (bad_checksum, "MATERIALIZATION-CHECKSUM"),
        (bad_size, "MATERIALIZATION-SIZE"),
    ):
        report = validate_materialization(
            manifest.model_copy(update={"items": [item]}),
            tmp_path,
        )
        assert any(error.startswith(prefix) for error in report.errors)
        assert (
            materialization_decision(
                manifest.model_copy(update={"items": [item]}),
                tmp_path,
            )
            == "stop"
        )


def test_materialization_path_and_file_checks_stop(tmp_path: Path) -> None:
    """An escaped path, an absolute path, or a missing file stops."""
    manifest = _manifest(tmp_path)
    for path, message in (
        ("../outside.txt", "relative"),
        (str(tmp_path / "data" / "vri.txt"), "relative"),
        ("data/missing.txt", "does not exist"),
    ):
        item = manifest.items[0].model_copy(update={"path": path})
        report = validate_materialization(
            manifest.model_copy(update={"items": [item]}),
            tmp_path,
        )
        assert any(
            error.startswith("MATERIALIZATION-PATH") and message in error for error in report.errors
        )


def test_materialization_required_fields_and_missing_reason(tmp_path: Path) -> None:
    """A materialized item needs all fields; a non-materialized one needs a reason."""
    manifest = _manifest(tmp_path)
    empty = manifest.items[0].model_copy(
        update={
            "path": "",
            "sha256": "",
            "licence": "",
            "pointer": "",
            "retrieved_utc": None,
        }
    )
    report = validate_materialization(
        manifest.model_copy(update={"items": [empty]}),
    )
    prefixes = {error.split(":", 1)[0] for error in report.errors}
    for prefix in (
        "MATERIALIZATION-PATH",
        "MATERIALIZATION-CHECKSUM",
        "MATERIALIZATION-LICENCE",
        "MATERIALIZATION-TIME",
        "MATERIALIZATION-POINTER",
    ):
        assert prefix in prefixes
    missing = manifest.items[0].model_copy(update={"status": "missing", "path": "", "reason": ""})
    missing_report = validate_materialization(
        manifest.model_copy(update={"items": [missing]}),
    )
    assert any(error.startswith("MATERIALIZATION-REASON") for error in missing_report.errors)
    okay = manifest.items[0].model_copy(
        update={"status": "missing", "path": "", "reason": "not available"}
    )
    assert validate_materialization(
        manifest.model_copy(update={"items": [okay]}),
    ).is_valid


def test_materialization_rejects_bad_pointer_checksum_status_and_time(
    tmp_path: Path,
) -> None:
    """Bad pointer, checksum shape, status, retrieval time, duplicates, and empty items fail."""
    manifest = _manifest(tmp_path)
    item = manifest.items[0].model_copy(
        update={
            "pointer": "wrong:pointer",
            "sha256": "not-a-checksum",
            "status": "unknown",
            "retrieved_utc": datetime(2026, 11, 14),
        }
    )
    report = validate_materialization(
        manifest.model_copy(update={"items": [item]}),
    )
    prefixes = {error.split(":", 1)[0] for error in report.errors}
    assert "MATERIALIZATION-POINTER" in prefixes
    assert "MATERIALIZATION-CHECKSUM" in prefixes
    assert "MATERIALIZATION-STATUS" in prefixes
    assert "MATERIALIZATION-TIME" in prefixes
    duplicate = manifest.model_copy(update={"items": [manifest.items[0], manifest.items[0]]})
    assert any(
        error.startswith("MATERIALIZATION-ID")
        for error in validate_materialization(duplicate).errors
    )
    empty = MaterializationManifest(plan_id="plan-1", created_utc=NOW)
    assert validate_materialization(empty).is_valid
    assert any(
        warning.startswith("MATERIALIZATION-EMPTY")
        for warning in validate_materialization(empty).warnings
    )
    naive = manifest.model_copy(update={"created_utc": datetime(2026, 11, 14)})
    assert any(
        error.startswith("MATERIALIZATION-TIME") for error in validate_materialization(naive).errors
    )


def test_materialization_accepts_other_pointers(tmp_path: Path) -> None:
    """An annex or DataLad pointer is accepted for a materialized item."""
    manifest = _manifest(tmp_path, pointer="annex:inputs/vri")
    assert validate_materialization(manifest, tmp_path).is_valid


def test_file_sha256_matches_hashlib(tmp_path: Path) -> None:
    """The file digest helper returns the standard SHA-256 value."""
    path = tmp_path / "file.txt"
    path.write_text("content\n", encoding="utf-8")
    assert file_sha256(path) == hashlib.sha256(b"content\n").hexdigest()


def test_coverage_report_accepts_every_state() -> None:
    """All six coverage states validate with their required evidence."""
    report = _coverage(
        CoverageEntry(
            source_id="lidarbc",
            state="observed",
            coverage_pct=100,
            evidence="bundle-1",
        ),
        CoverageEntry(
            source_id="vri",
            state="stale",
            coverage_pct=50,
            vintage="2020",
            evidence="inventory-1",
        ),
        CoverageEntry(
            source_id="dra",
            state="partial",
            coverage_pct=50,
            evidence="tile-1",
        ),
        CoverageEntry(source_id="bec", state="missing", reason="outside the province"),
        CoverageEntry(
            source_id="sibec",
            state="out_of_domain",
            reason="no matching BEC unit",
        ),
        CoverageEntry(source_id="climate", state="excluded", reason="not in scope"),
    )
    result = validate_coverage(report)
    assert result.is_valid
    counts = coverage_counts(report)
    assert counts["total"] == 6
    assert counts["observed"] == 1
    assert counts["missing"] == 1


def test_coverage_validation_names_state_and_evidence_errors() -> None:
    """Observed, partial, stale, missing, and reason rules are enforced."""
    entries = [
        CoverageEntry(source_id="a", state="observed", coverage_pct=0),
        CoverageEntry(source_id="b", state="observed", coverage_pct=50),
        CoverageEntry(source_id="c", state="partial", coverage_pct=0),
        CoverageEntry(source_id="d", state="partial", coverage_pct=100),
        CoverageEntry(source_id="e", state="stale", coverage_pct=50),
        CoverageEntry(source_id="f", state="missing", coverage_pct=50),
        CoverageEntry(source_id="g", state="out_of_domain"),
        CoverageEntry(source_id="h", state="excluded"),
    ]
    report = validate_coverage(_coverage(*entries))
    prefixes = {error.split(":", 1)[0] for error in report.errors}
    for prefix in (
        "COVERAGE-STATE",
        "COVERAGE-EVIDENCE",
        "COVERAGE-PARTIAL",
        "COVERAGE-STALE",
        "COVERAGE-MISSING",
        "COVERAGE-REASON",
    ):
        assert prefix in prefixes


def test_coverage_rejects_unknown_duplicate_and_naive_entries() -> None:
    """Unknown state, duplicate key, naive time, and empty report are handled."""
    unknown = _coverage(CoverageEntry(source_id="a", state="unknown", reason="x"))
    assert any(error.startswith("COVERAGE-STATE") for error in validate_coverage(unknown).errors)
    duplicate = _coverage(
        CoverageEntry(source_id="a", state="missing", reason="x"),
        CoverageEntry(source_id="a", state="missing", reason="x"),
    )
    assert any(error.startswith("COVERAGE-ID") for error in validate_coverage(duplicate).errors)
    naive = _coverage().model_copy(update={"created_utc": datetime(2026, 11, 14)})
    assert any(error.startswith("COVERAGE-TIME") for error in validate_coverage(naive).errors)
    empty = _coverage()
    assert validate_coverage(empty).is_valid
    assert any(
        warning.startswith("COVERAGE-EMPTY") for warning in validate_coverage(empty).warnings
    )


def test_gap_report_stops_on_a_required_missing_source() -> None:
    """A required missing source stops and names the acquisition action."""
    coverage = _coverage(
        CoverageEntry(source_id="lidarbc", state="observed", coverage_pct=100, evidence="b"),
        CoverageEntry(source_id="vri", state="missing", reason="not available"),
    )
    gap = build_gap_report(coverage)
    assert gap.decision == "stop"
    assert gap.next_action == "request or acquire the source, or mark the affected segments unknown"
    assert gap.gaps[0].decision == "stop"
    assert validate_gap_report(gap).is_valid


def test_gap_report_continues_with_caveats_for_partial_stale_and_excluded() -> None:
    """A partial, stale, excluded, or optional gap continues with a caveat."""
    coverage = _coverage(
        CoverageEntry(source_id="vri", state="partial", coverage_pct=50, evidence="tile"),
        CoverageEntry(
            source_id="dra",
            state="stale",
            coverage_pct=50,
            vintage="2020",
            evidence="inventory",
        ),
        CoverageEntry(source_id="climate", state="excluded", reason="not in scope"),
        CoverageEntry(
            source_id="ntems",
            state="out_of_domain",
            required=False,
            reason="outside the product",
        ),
    )
    gap = build_gap_report(coverage)
    assert gap.decision == "continue_with_caveat"
    assert len(gap.gaps) == 4
    assert all(gap.gaps[index].decision == "continue_with_caveat" for index in range(4))
    assert validate_gap_report(gap).is_valid


def test_gap_report_with_no_gaps_continues() -> None:
    """A fully observed report continues with no next action."""
    coverage = _coverage(
        CoverageEntry(source_id="lidarbc", state="observed", coverage_pct=100, evidence="b")
    )
    gap = build_gap_report(coverage)
    assert gap.decision == "continue"
    assert gap.next_action == "none"
    assert gap.gaps == []
    assert validate_gap_report(gap).is_valid


def test_gap_validation_names_decision_and_action_errors() -> None:
    """Unknown decisions, empty actions, duplicates, and naive time fail."""
    coverage = _coverage(CoverageEntry(source_id="vri", state="missing", reason="x"))
    gap = build_gap_report(coverage)
    bad_decision = gap.model_copy(update={"decision": "maybe"})
    assert any(
        error.startswith("GAP-DECISION") for error in validate_gap_report(bad_decision).errors
    )
    empty_action = gap.model_copy(update={"next_action": ""})
    assert any(error.startswith("GAP-ACTION") for error in validate_gap_report(empty_action).errors)
    duplicate = gap.model_copy(update={"gaps": [gap.gaps[0], gap.gaps[0]]})
    assert any(error.startswith("GAP-ID") for error in validate_gap_report(duplicate).errors)
    naive = gap.model_copy(update={"created_utc": datetime(2026, 11, 14)})
    assert any(error.startswith("GAP-TIME") for error in validate_gap_report(naive).errors)


def test_gap_validation_rejects_inconsistent_decisions() -> None:
    """A stop without a stop, continue with gaps, and caveat with stop fail."""
    gap = build_gap_report(_coverage(CoverageEntry(source_id="vri", state="missing", reason="x")))
    stop_without_stop = gap.model_copy(
        update={
            "gaps": [
                GapRecord(
                    gap_id="vri:aoi",
                    source_id="vri",
                    target_id="aoi",
                    state="missing",
                    decision="continue_with_caveat",
                    recommended_action="request",
                )
            ]
        }
    )
    continue_with_gap = gap.model_copy(update={"decision": "continue"})
    caveat_with_stop = gap.model_copy(update={"decision": "continue_with_caveat"})
    unknown_gap_decision = gap.model_copy(
        update={"gaps": [gap.gaps[0].model_copy(update={"decision": "maybe"})]}
    )
    unknown_state = gap.model_copy(
        update={"gaps": [gap.gaps[0].model_copy(update={"state": "unknown"})]}
    )
    for report in (
        stop_without_stop,
        continue_with_gap,
        caveat_with_stop,
        unknown_gap_decision,
        unknown_state,
    ):
        assert validate_gap_report(report).errors
    assert any(
        warning.startswith("GAP-CAVEAT")
        for warning in validate_gap_report(
            gap.model_copy(
                update={
                    "decision": "continue_with_caveat",
                    "gaps": [gap.gaps[0].model_copy(update={"decision": "continue_with_caveat"})],
                }
            )
        ).warnings
    )


def test_plan_validation_rejects_a_pointer_mismatch() -> None:
    """A known materialization target with the wrong pointer fails."""
    plan = _replace_item(
        _plan(),
        materialization="public_mirror",
        materialization_pointer="data_lad:inputs/vri",
    )
    report = validate_fetch_plan(plan)
    assert any(error.startswith("FETCH-MATERIALIZATION") for error in report.errors)


def test_approval_rejects_an_unknown_scope() -> None:
    """An approval scope outside single or bulk fails."""
    plan = _plan(
        approvals={
            "vri": FetchApproval(
                approved_by="owner",
                approved_utc=NOW,
                scope="team",
                record="approval-1",
            )
        }
    )
    report = validate_fetch_plan(plan)
    assert any(
        error.startswith("FETCH-APPROVAL") and "unknown approval scope" in error
        for error in report.errors
    )


def test_connector_classification_drift_fails() -> None:
    """A connector whose classification changed since planning fails."""
    catalogue = _approved_catalogue()
    plan = plan_fetch(
        catalogue,
        FetchRequest(aoi="aoi.geojson", connector_ids=["asset-registry"]),
        plan_id="plan-1",
        created_utc=NOW,
    )
    item = plan.items[0].model_copy(update={"classification": "public"})
    report = validate_fetch_plan(plan.model_copy(update={"items": [item]}), catalogue)
    assert any(error.startswith("FETCH-DRIFT") for error in report.errors)


def test_materialization_path_symlink_escape_stops(tmp_path: Path) -> None:
    """A symlink that resolves outside the workspace root stops."""
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    try:
        link = tmp_path / "data" / "link.txt"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(outside)
        manifest = _manifest(
            tmp_path,
            path="data/link.txt",
            sha256=hashlib.sha256(b"outside\n").hexdigest(),
            size_bytes=len(b"outside\n"),
        )
        report = validate_materialization(manifest, tmp_path)
        assert any(
            error.startswith("MATERIALIZATION-PATH") and "outside" in error
            for error in report.errors
        )
        assert materialization_decision(manifest, tmp_path) == "stop"
    finally:
        outside.unlink(missing_ok=True)


def test_materialization_nonmaterialized_path_skips_file_check(tmp_path: Path) -> None:
    """A missing item with a path does not require the file to exist."""
    manifest = _manifest(
        tmp_path,
        status="missing",
        reason="not retrieved",
        pointer="",
        sha256="",
        retrieved_utc=None,
        licence="",
    )
    report = validate_materialization(manifest, tmp_path)
    assert report.is_valid

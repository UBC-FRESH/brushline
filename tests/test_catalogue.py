"""Contract tests for the public catalogue and private connector registry."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from brushline.integrations.catalogue import (
    AuditRule,
    ConnectionTest,
    ConnectorApproval,
    ConnectorRecord,
    DataCatalogue,
    ReadScope,
    UnknownCatalogueReferenceError,
    agent_can_read,
    agent_metadata,
    approved_connector_ids,
    connector_agent_metadata,
    resolve_connector,
    resolve_source,
    run_connection_test,
    scan_for_secrets,
    validate_catalogue,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE_PATH = ROOT / "notes" / "reference" / "data-catalogue.v1.json"


def _catalogue() -> DataCatalogue:
    return DataCatalogue.model_validate_json(CATALOGUE_PATH.read_text(encoding="utf-8"))


def _replace_source(catalogue: DataCatalogue, **updates: object) -> DataCatalogue:
    source = catalogue.sources[0].model_copy(update=updates)
    return catalogue.model_copy(update={"sources": [source, *catalogue.sources[1:]]})


def _replace_connector(
    catalogue: DataCatalogue,
    connector_id: str = "asset-registry",
    **updates: object,
) -> DataCatalogue:
    connectors = [
        connector.model_copy(update=updates) if connector.id == connector_id else connector
        for connector in catalogue.connectors
    ]
    return catalogue.model_copy(update={"connectors": connectors})


def _approved_connector(
    connector: ConnectorRecord,
    *,
    approval: ConnectorApproval | None = None,
) -> ConnectorRecord:
    record = approval or ConnectorApproval(
        approved_by="owner",
        approved_utc=datetime(2026, 11, 14, tzinfo=UTC),
        data_sharing_record="data-sharing-record-1",
    )
    return connector.model_copy(update={"approval": record})


def _approved_catalogue(
    catalogue: DataCatalogue,
    connector_id: str = "asset-registry",
) -> DataCatalogue:
    connector = resolve_connector(catalogue, connector_id)
    return _replace_connector(
        catalogue,
        connector_id=connector_id,
        approval=_approved_connector(connector).approval,
    )


def test_committed_catalogue_is_valid() -> None:
    """The committed catalogue has the expected sources, connectors, and valid metadata."""
    catalogue = _catalogue()
    report = validate_catalogue(catalogue)
    assert report.is_valid
    assert report.counts == {
        "sources": 13,
        "connectors": 6,
        "approved_connectors": 0,
    }
    assert resolve_source(catalogue, "lidarbc").licence == "OGL-BC"
    assert resolve_connector(catalogue, "asset-registry").approved is False
    assert all(source.licence for source in catalogue.sources)
    assert all(source.coverage for source in catalogue.sources)


def test_source_requires_a_usable_licence() -> None:
    """An empty or unknown public licence fails with a named error."""
    for licence in ("", "unknown", "none", "proprietary"):
        report = validate_catalogue(_replace_source(_catalogue(), licence=licence))
        assert any(error.startswith("CATALOGUE-LICENCE") for error in report.errors)


def test_source_requires_coverage_crs_query_and_vintage() -> None:
    """A source without its coverage, CRS, query, or vintage fails."""
    report = validate_catalogue(
        _replace_source(_catalogue(), coverage="", crs="", query="", vintage="")
    )
    prefixes = {error.split(":", 1)[0] for error in report.errors}
    assert "CATALOGUE-COVERAGE" in prefixes
    assert "CATALOGUE-CRS" in prefixes
    assert "CATALOGUE-QUERY" in prefixes
    assert "CATALOGUE-VINTAGE" in prefixes


def test_public_source_rejects_private_classification() -> None:
    """A public source cannot claim a private classification."""
    report = validate_catalogue(_replace_source(_catalogue(), classification="private"))
    assert any(error.startswith("CATALOGUE-CLASSIFICATION") for error in report.errors)


def test_source_rejects_unknown_access_method_and_status() -> None:
    """An access method or status outside the contract fails."""
    report = validate_catalogue(
        _replace_source(_catalogue(), access_method="ftp", access_status="maybe")
    )
    access_errors = [error for error in report.errors if error.startswith("CATALOGUE-ACCESS")]
    assert len(access_errors) == 2


def test_duplicate_source_and_connector_ids_fail() -> None:
    """Duplicate ids fail for both collections."""
    catalogue = _catalogue()
    duplicate_sources = catalogue.model_copy(
        update={"sources": [*catalogue.sources, catalogue.sources[0]]}
    )
    duplicate_connectors = catalogue.model_copy(
        update={"connectors": [*catalogue.connectors, catalogue.connectors[0]]}
    )
    source_errors = validate_catalogue(duplicate_sources).errors
    connector_errors = validate_catalogue(duplicate_connectors).errors
    assert any(error.startswith("CATALOGUE-ID: duplicate source") for error in source_errors)
    assert any(error.startswith("CATALOGUE-ID: duplicate connector") for error in connector_errors)


def test_connector_requires_a_non_secret_auth_reference() -> None:
    """A missing, raw, or mismatched authentication reference fails."""
    catalogue = _catalogue()
    missing = validate_catalogue(_replace_connector(catalogue, authentication_reference=""))
    raw = validate_catalogue(
        _replace_connector(
            catalogue,
            authentication_reference="postgres://user:password@example/db",
        )
    )
    mismatch = validate_catalogue(
        _replace_connector(
            catalogue,
            authentication_method="secret_store",
            authentication_reference="env:ASSET_TOKEN",
        )
    )
    assert any(error.startswith("CATALOGUE-AUTH") for error in missing.errors)
    assert any(error.startswith("CATALOGUE-AUTH") for error in raw.errors)
    assert any(error.startswith("CATALOGUE-AUTH") for error in mismatch.errors)


def test_connector_rejects_unknown_auth_method() -> None:
    """An unknown authentication method fails with a named error."""
    report = validate_catalogue(_replace_connector(_catalogue(), authentication_method="oauth"))
    assert any(error.startswith("CATALOGUE-AUTH") for error in report.errors)


def test_connector_rejects_an_unknown_linked_source() -> None:
    """A connector can link only registered public sources."""
    report = validate_catalogue(
        _replace_connector(_catalogue(), linked_source_ids=["missing-source"])
    )
    assert any(error.startswith("CATALOGUE-SOURCE") for error in report.errors)


def test_connector_requires_scope_outputs_audit_and_test() -> None:
    """A connector without scope, outputs, audit, or a test reference fails."""
    catalogue = _catalogue()
    connector = resolve_connector(catalogue, "asset-registry")
    report = validate_catalogue(
        _replace_connector(
            catalogue,
            read_scope=ReadScope(tables=[], max_rows=0),
            allowed_outputs=[],
            audit=AuditRule(record_location=""),
            test_connection=ConnectionTest(method="environment", reference=""),
        )
    )
    prefixes = {error.split(":", 1)[0] for error in report.errors}
    assert "CATALOGUE-SCOPE" in prefixes
    assert "CATALOGUE-OUTPUT" in prefixes
    assert "CATALOGUE-AUDIT" in prefixes
    assert "CATALOGUE-TEST" in prefixes
    assert connector.approved is False


def test_connector_rejects_bad_scope_and_output_details() -> None:
    """Unknown tables, columns, outputs, max rows, and test methods fail."""
    catalogue = _catalogue()
    connector = resolve_connector(catalogue, "asset-registry")
    bad_scope = connector.read_scope.model_copy(
        update={"columns": {"missing-table": ["column"]}, "max_rows": 0}
    )
    report = validate_catalogue(
        _replace_connector(
            catalogue,
            read_scope=bad_scope,
            allowed_outputs=["model"],
            test_connection=ConnectionTest(method="oauth", reference="env:TOKEN"),
        )
    )
    prefixes = {error.split(":", 1)[0] for error in report.errors}
    assert "CATALOGUE-SCOPE" in prefixes
    assert "CATALOGUE-OUTPUT" in prefixes
    assert "CATALOGUE-TEST" in prefixes
    raw_test = validate_catalogue(
        _replace_connector(
            catalogue,
            test_connection=ConnectionTest(
                method="environment",
                reference="postgres://user:password@example/db",
            ),
        )
    )
    mismatched_test = validate_catalogue(
        _replace_connector(
            catalogue,
            test_connection=ConnectionTest(
                method="environment",
                reference="secret_store:brushline/asset-registry",
            ),
        )
    )
    assert any(error.startswith("CATALOGUE-TEST") for error in raw_test.errors)
    assert any(error.startswith("CATALOGUE-TEST") for error in mismatched_test.errors)


def test_connector_rejects_public_classification() -> None:
    """A private connector cannot be classified as public."""
    report = validate_catalogue(_replace_connector(_catalogue(), classification="public"))
    assert any(error.startswith("CATALOGUE-CLASSIFICATION") for error in report.errors)


def test_approval_requires_owner_record_and_timezone() -> None:
    """An incomplete approval fails with clear errors."""
    approval = ConnectorApproval(
        approved_by="",
        approved_utc=datetime(2026, 11, 14),
        data_sharing_record="",
    )
    report = validate_catalogue(_replace_connector(_catalogue(), approval=approval))
    approval_errors = [error for error in report.errors if error.startswith("CATALOGUE-APPROVAL")]
    assert len(approval_errors) == 3


def test_agent_view_hides_authentication_and_private_references() -> None:
    """The agent sees safe connector metadata but no auth or test reference."""
    catalogue = _catalogue()
    view = agent_metadata(catalogue)
    serialized = json.dumps(view)
    assert "BRUSHLINE_ASSET_REGISTRY_TOKEN" not in serialized
    assert "authentication_reference" not in serialized
    assert "secret_store:" not in serialized
    connector = resolve_connector(catalogue, "asset-registry")
    safe = connector_agent_metadata(connector)
    assert safe["approved"] is False
    assert safe["authentication_method"] == "environment"
    assert agent_can_read(connector) is False
    assert approved_connector_ids(catalogue) == ()


def test_approval_unlocks_the_connector_for_the_agent() -> None:
    """A complete owner approval makes the connector readable by the agent."""
    catalogue = _approved_catalogue(_catalogue())
    connector = resolve_connector(catalogue, "asset-registry")
    report = validate_catalogue(catalogue)
    assert report.is_valid
    assert report.counts["approved_connectors"] == 1
    assert agent_can_read(connector) is True
    assert approved_connector_ids(catalogue) == ("asset-registry",)
    safe = connector_agent_metadata(connector)
    assert safe["approved"] is True
    assert "BRUSHLINE_ASSET_REGISTRY_TOKEN" not in json.dumps(safe)


def test_connection_is_blocked_without_approval() -> None:
    """An unapproved connector cannot be tested or reveal sample metadata."""
    result = run_connection_test(_catalogue(), "asset-registry")
    assert result.status == "blocked"
    assert result.ok is False
    assert result.sample_metadata == {}
    assert result.to_dict()["connector_id"] == "asset-registry"


def test_connection_probe_success_and_failure() -> None:
    """An approved connector uses the probe and reports its sample metadata."""
    catalogue = _approved_catalogue(_catalogue())
    seen: list[str] = []

    def success(reference: str) -> bool:
        seen.append(reference)
        return True

    ok = run_connection_test(catalogue, "asset-registry", probe=success)
    failed = run_connection_test(catalogue, "asset-registry", probe=lambda _reference: False)
    assert ok.ok is True
    assert ok.status == "ok"
    assert ok.sample_metadata["row_count_class"] == "metadata_only"
    assert seen == ["env:BRUSHLINE_ASSET_REGISTRY_TOKEN"]
    assert failed.status == "failed"
    assert failed.sample_metadata == {}


def test_connection_environment_presence() -> None:
    """An approved environment test checks the variable without reading its value."""
    catalogue = _approved_catalogue(_catalogue())
    variable = resolve_connector(
        catalogue, "asset-registry"
    ).test_connection.reference.removeprefix("env:")
    present = run_connection_test(catalogue, "asset-registry", environ={variable: "set"})
    absent = run_connection_test(catalogue, "asset-registry", environ={})
    assert present.ok is True
    assert "is present" in present.message
    assert absent.status == "failed"
    assert "is not present" in absent.message


def test_connection_not_configured_for_owner_side_secret_store() -> None:
    """A managed-identity connector needs an owner-side probe."""
    catalogue = _approved_catalogue(_catalogue(), connector_id="costs")
    result = run_connection_test(catalogue, "costs")
    assert result.status == "not_configured"
    assert "managed_identity" in result.message


def test_unknown_source_and_connector_raise() -> None:
    """Unknown references raise a typed exception with the requested kind and id."""
    catalogue = _catalogue()
    with pytest.raises(UnknownCatalogueReferenceError) as source_error:
        resolve_source(catalogue, "missing")
    with pytest.raises(UnknownCatalogueReferenceError) as connector_error:
        resolve_connector(catalogue, "missing")
    assert source_error.value.kind == "source"
    assert connector_error.value.kind == "connector"
    assert "unknown source: missing" in str(source_error.value)
    assert "unknown connector: missing" in str(connector_error.value)


def test_unknown_connector_fails_a_connection_test() -> None:
    """A test for an unregistered connector raises the same typed error."""
    with pytest.raises(UnknownCatalogueReferenceError):
        run_connection_test(_catalogue(), "missing")


def test_secret_scan_detects_value_patterns() -> None:
    """Common token, key, JWT, bearer, and connection-string shapes are rejected."""
    samples = [
        "-----BEGIN PRIVATE KEY-----",
        "AKIAABCDEFGHIJKLMNOP",
        "ghp_abcdefghijklmnopqrstuvwx",
        "pypi-" + "a" * 40,
        "Bearer abcdefghijklmnop",
        "postgres://user:password@example/db",
        "eyJabcdefghij.abcdefghij.abcdefghij",
    ]
    for sample in samples:
        findings = scan_for_secrets(sample)
        assert findings
        assert all(finding.startswith("CATALOGUE-SECRET") for finding in findings)
        assert sample not in " ".join(findings)


def test_secret_scan_rejects_a_secret_json_key_and_allows_a_reference() -> None:
    """A secret-shaped key fails, while an env reference is not a secret."""
    assert scan_for_secrets('{"api_key": "not-a-reference"}')
    assert scan_for_secrets('{"authentication_reference": "env:ASSET_TOKEN"}') == ()
    assert scan_for_secrets('{"token": ""}') == ()


def test_validation_scans_free_text_for_secrets() -> None:
    """A secret in a description fails the catalogue validator."""
    report = validate_catalogue(
        _replace_connector(
            _catalogue(),
            description="owner pasted Bearer abcdefghijklmnop into the note",
        )
    )
    assert any(error.startswith("CATALOGUE-SECRET") for error in report.errors)


def test_empty_catalogue_warns_and_naive_time_fails() -> None:
    """An empty catalogue is a warning; a naive timestamp is an error."""
    empty = DataCatalogue(created_utc=datetime(2026, 11, 14, tzinfo=UTC))
    report = validate_catalogue(empty)
    assert report.is_valid
    assert any(warning.startswith("CATALOGUE-EMPTY") for warning in report.warnings)
    assert report.counts == {
        "sources": 0,
        "connectors": 0,
        "approved_connectors": 0,
    }
    naive = _catalogue().model_copy(update={"created_utc": datetime(2026, 11, 14)})
    naive_report = validate_catalogue(naive)
    assert any(error.startswith("CATALOGUE-TIME") for error in naive_report.errors)


def test_catalogue_round_trips_through_json() -> None:
    """The committed catalogue serializes and validates without a semantic change."""
    catalogue = _catalogue()
    loaded = DataCatalogue.model_validate_json(catalogue.model_dump_json())
    assert loaded == catalogue
    assert validate_catalogue(loaded).is_valid

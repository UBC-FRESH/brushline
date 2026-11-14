"""Data catalogue and connector registry for public and private sources.

The catalogue is metadata-only. It records what a source is, which licence governs it, where it
covers, and how it may be read. Private connectors add an approval gate: the agent sees connector
metadata, never an authentication value or private rows, until an owner approval exists.

No field stores a credential. An authentication reference names an environment variable, a
secret-store item, or a managed identity. The validator rejects a raw secret-shaped value, and the
text scanner is a second line of defence for descriptions and sample metadata.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from brushline.model.validation import ContractValidation, check_duplicates

CATALOGUE_SCHEMA_VERSION: Literal["brushline.catalogue.v1"] = "brushline.catalogue.v1"
PUBLIC_CLASSIFICATIONS: tuple[str, ...] = ("public", "synthetic")
PRIVATE_CLASSIFICATIONS: tuple[str, ...] = ("private", "restricted")
ACCESS_METHODS: tuple[str, ...] = (
    "bulk_download",
    "wms",
    "wfs",
    "rest",
    "stac",
    "api",
    "manual",
    "unknown",
)
ACCESS_STATUSES: tuple[str, ...] = ("available", "request", "unknown", "unavailable")
ALLOWED_OUTPUTS: tuple[str, ...] = ("raw", "derived", "aggregate")
AUTH_METHODS: tuple[str, ...] = ("environment", "secret_store", "managed_identity")
AUTH_METHOD_PREFIXES: dict[str, str] = {
    "environment": "env:",
    "secret_store": "secret_store:",
    "managed_identity": "managed_identity:",
}
AUTH_REFERENCE_PATTERN: re.Pattern[str] = re.compile(
    r"^(?:env|secret_store|managed_identity):[A-Za-z0-9_.:/-]+$"
)
UNUSABLE_PUBLIC_LICENCES: tuple[str, ...] = ("", "unknown", "none", "proprietary")

SECRET_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("PyPI token", re.compile(r"\bpypi-[A-Za-z0-9_-]{40,}\b")),
    (
        "bearer token",
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{12,}", re.IGNORECASE),
    ),
    (
        "connection-string password",
        re.compile(r"://[^/\s:@]+:[^/\s@]+@"),
    ),
    (
        "JWT",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
)
SECRET_KEY_PATTERN: re.Pattern[str] = re.compile(
    r'"(?:password|passwd|secret|token|api[_-]?key|apikey|authorization|credential|'
    r'private[_-]?key|client[_-]?secret)"\s*:\s*"([^"]*)"',
    re.IGNORECASE,
)


class SourceRecord(BaseModel):
    """One public or synthetic source in the catalogue.

    Parameters
    ----------
    id : str
        Stable source identifier.
    name : str
        Human-readable source name.
    provider : str
        Data provider or agency.
    dataset : str
        Dataset or product name.
    query : str
        Query or selection rule used to read the source.
    vintage : str
        Data vintage or version.
    crs : str
        Native coordinate reference system.
    licence : str
        Licence identifier. Empty and unknown values are rejected.
    classification : str
        ``public`` or ``synthetic`` for the public catalogue.
    coverage : str
        Geographic and thematic coverage note.
    access_method : str
        Access method, such as ``wfs``, ``stac``, ``bulk_download``, or ``manual``.
    access_status : str
        ``available``, ``request``, ``unknown``, or ``unavailable``.
    url : str, optional
        Public landing page or service URL.
    description : str, optional
        Short description and caveats.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,63}$")
    name: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    dataset: str = Field(min_length=1)
    query: str = ""
    vintage: str = ""
    crs: str = ""
    licence: str = ""
    classification: str = "public"
    coverage: str = ""
    access_method: str = "unknown"
    access_status: str = "unknown"
    url: str = ""
    description: str = ""


class ReadScope(BaseModel):
    """The row and column scope of a private connector.

    Parameters
    ----------
    tables : list of str
        Tables or views the connector may read.
    columns : dict of str to list of str, optional
        Per-table column allowlist.
    row_filters : list of str, optional
        Required row filters, expressed as policy text.
    max_rows : int, optional
        Maximum rows returned in one call. Defaults to ``1000``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tables: list[str] = Field(default_factory=list)
    columns: dict[str, list[str]] = Field(default_factory=dict)
    row_filters: list[str] = Field(default_factory=list)
    max_rows: int = Field(default=1000, ge=0)


class AuditRule(BaseModel):
    """The audit and retention rule for a private connector.

    Parameters
    ----------
    log_access : bool, optional
        Whether every read is logged. Defaults to ``True``.
    retention_days : int, optional
        Audit-log retention in days. Defaults to ``365``.
    review_required : bool, optional
        Whether a derived output needs review before release. Defaults to ``True``.
    record_location : str, optional
        Where the audit record lives. Required by the validator.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    log_access: bool = True
    retention_days: int = Field(default=365, ge=1)
    review_required: bool = True
    record_location: str = ""


class ConnectionTest(BaseModel):
    """A non-secret connection test and its expected metadata response.

    Parameters
    ----------
    method : str, optional
        ``environment``, ``secret_store``, or ``managed_identity``.
    reference : str, optional
        Non-secret reference used by the test.
    sample_metadata : dict of str to object, optional
        Expected metadata keys, never rows or credentials.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: str = "environment"
    reference: str = ""
    sample_metadata: dict[str, object] = Field(default_factory=dict)


class ConnectorApproval(BaseModel):
    """An owner approval for one private connector.

    Parameters
    ----------
    approved_by : str
        Owner or role that approved the connector.
    approved_utc : datetime
        Timezone-aware approval time.
    data_sharing_record : str
        Reference to the data-sharing or access record.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    approved_by: str = ""
    approved_utc: datetime
    data_sharing_record: str = ""


class ConnectorRecord(BaseModel):
    """One private or restricted data connector.

    Parameters
    ----------
    id : str
        Stable connector identifier.
    name : str
        Human-readable connector name.
    owner : str
        Data owner or responsible role.
    description : str
        What the connector reads and why.
    classification : str
        ``private`` or ``restricted``.
    linked_source_ids : list of str, optional
        Public catalogue sources that provide context for this connector.
    authentication_method : str, optional
        ``environment``, ``secret_store``, or ``managed_identity``.
    authentication_reference : str, optional
        Non-secret reference such as ``env:ASSET_REGISTRY_TOKEN``.
    read_scope : ReadScope, optional
        Tables, columns, filters, and row limit.
    allowed_outputs : list of str, optional
        ``raw``, ``derived``, and/or ``aggregate``.
    audit : AuditRule, optional
        Audit and retention rule.
    test_connection : ConnectionTest, optional
        Offline or owner-run connection test and sample metadata.
    approval : ConnectorApproval or None, optional
        Owner approval. The agent cannot read the connector without it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,63}$")
    name: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    description: str = Field(min_length=1)
    classification: str = "private"
    linked_source_ids: list[str] = Field(default_factory=list)
    authentication_method: str = "environment"
    authentication_reference: str = ""
    read_scope: ReadScope = Field(default_factory=ReadScope)
    allowed_outputs: list[str] = Field(default_factory=list)
    audit: AuditRule = Field(default_factory=AuditRule)
    test_connection: ConnectionTest = Field(default_factory=ConnectionTest)
    approval: ConnectorApproval | None = None

    @property
    def approved(self) -> bool:
        """Return whether the owner has approved the connector.

        Returns
        -------
        bool
            ``True`` when an approval record exists.
        """
        return self.approval is not None


class DataCatalogue(BaseModel):
    """The versioned public catalogue and private connector registry.

    Parameters
    ----------
    schema_version : {"brushline.catalogue.v1"}
        Catalogue schema version.
    name : str
        Catalogue name.
    created_utc : datetime
        Timezone-aware creation time.
    sources : list of SourceRecord
        Public and synthetic sources.
    connectors : list of ConnectorRecord
        Private and restricted connectors.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.catalogue.v1"] = CATALOGUE_SCHEMA_VERSION
    name: str = Field(default="Brushline data catalogue", min_length=1)
    created_utc: datetime
    sources: list[SourceRecord] = Field(default_factory=list)
    connectors: list[ConnectorRecord] = Field(default_factory=list)


@dataclass(frozen=True)
class ConnectionTestResult:
    """The outcome of a connector test.

    Parameters
    ----------
    connector_id : str
        Connector that was tested.
    status : str
        ``blocked``, ``ok``, ``failed``, or ``not_configured``.
    message : str
        Human-readable explanation.
    sample_metadata : dict of str to object
        Expected metadata response; empty when blocked.
    """

    connector_id: str
    status: str
    message: str
    sample_metadata: dict[str, object]

    @property
    def ok(self) -> bool:
        """Return whether the test completed successfully.

        Returns
        -------
        bool
            ``True`` only for the ``ok`` status.
        """
        return self.status == "ok"

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-ready test result.

        Returns
        -------
        dict of str to object
            Connector id, status, message, and sample metadata.
        """
        return {
            "connector_id": self.connector_id,
            "status": self.status,
            "message": self.message,
            "sample_metadata": dict(sorted(self.sample_metadata.items())),
        }


class UnknownCatalogueReferenceError(KeyError):
    """Raised when a catalogue source or connector id is not registered."""

    def __init__(self, kind: str, reference: str) -> None:
        self.kind = kind
        self.reference = reference
        super().__init__(f"unknown {kind}: {reference}")


def resolve_source(catalogue: DataCatalogue, source_id: str) -> SourceRecord:
    """Return one source by id.

    Parameters
    ----------
    catalogue : DataCatalogue
        Catalogue to search.
    source_id : str
        Source identifier.

    Returns
    -------
    SourceRecord
        The matching source.

    Raises
    ------
    UnknownCatalogueReferenceError
        When the source is not registered.
    """
    for source in catalogue.sources:
        if source.id == source_id:
            return source
    raise UnknownCatalogueReferenceError("source", source_id)


def resolve_connector(catalogue: DataCatalogue, connector_id: str) -> ConnectorRecord:
    """Return one connector by id.

    Parameters
    ----------
    catalogue : DataCatalogue
        Catalogue to search.
    connector_id : str
        Connector identifier.

    Returns
    -------
    ConnectorRecord
        The matching connector.

    Raises
    ------
    UnknownCatalogueReferenceError
        When the connector is not registered.
    """
    for connector in catalogue.connectors:
        if connector.id == connector_id:
            return connector
    raise UnknownCatalogueReferenceError("connector", connector_id)


def connector_agent_metadata(connector: ConnectorRecord) -> dict[str, object]:
    """Return the connector metadata that the agent may see.

    The authentication reference and test reference are omitted. The approval flag is included so
    the agent can ask for approval without inventing access.

    Parameters
    ----------
    connector : ConnectorRecord
        Connector to expose.

    Returns
    -------
    dict of str to object
        Safe connector metadata.
    """
    return {
        "id": connector.id,
        "name": connector.name,
        "owner": connector.owner,
        "description": connector.description,
        "classification": connector.classification,
        "linked_source_ids": list(connector.linked_source_ids),
        "authentication_method": connector.authentication_method,
        "read_scope": connector.read_scope.model_dump(mode="json"),
        "allowed_outputs": list(connector.allowed_outputs),
        "audit": connector.audit.model_dump(mode="json"),
        "test_connection": {
            "method": connector.test_connection.method,
            "sample_metadata": dict(connector.test_connection.sample_metadata),
        },
        "approved": connector.approved,
    }


def agent_metadata(catalogue: DataCatalogue) -> dict[str, object]:
    """Return the catalogue view that the agent may see.

    Public sources remain visible. Private connectors are reduced to safe metadata, and no
    authentication reference or private row is included.

    Parameters
    ----------
    catalogue : DataCatalogue
        Catalogue to expose.

    Returns
    -------
    dict of str to object
        Public source metadata and safe connector metadata.
    """
    sources = [
        cast("dict[str, object]", source.model_dump(mode="json")) for source in catalogue.sources
    ]
    return {
        "schema_version": catalogue.schema_version,
        "name": catalogue.name,
        "created_utc": catalogue.created_utc.isoformat(),
        "sources": sources,
        "connectors": [connector_agent_metadata(connector) for connector in catalogue.connectors],
    }


def agent_can_read(connector: ConnectorRecord) -> bool:
    """Return whether the agent may read a connector.

    Parameters
    ----------
    connector : ConnectorRecord
        Connector to check.

    Returns
    -------
    bool
        ``True`` only when an approval record exists.
    """
    return connector.approved


def approved_connector_ids(catalogue: DataCatalogue) -> tuple[str, ...]:
    """Return the ids of approved connectors.

    Parameters
    ----------
    catalogue : DataCatalogue
        Catalogue to search.

    Returns
    -------
    tuple of str
        Approved connector ids in catalogue order.
    """
    return tuple(connector.id for connector in catalogue.connectors if connector.approved)


def run_connection_test(
    catalogue: DataCatalogue,
    connector_id: str,
    *,
    probe: Callable[[str], bool] | None = None,
    environ: Mapping[str, str] | None = None,
) -> ConnectionTestResult:
    """Test one connector without returning a secret.

    An unapproved connector is always blocked. With a probe, the probe receives the non-secret
    authentication reference. Without a probe, an ``environment`` test checks whether the named
    environment variable is present; other methods are ``not_configured`` because this process
    cannot reach the owner's secret store or managed identity.

    Parameters
    ----------
    catalogue : DataCatalogue
        Catalogue that owns the connector.
    connector_id : str
        Connector to test.
    probe : callable, optional
        Test hook that receives the authentication reference and returns success.
    environ : mapping of str to str, optional
        Environment source. Defaults to ``os.environ``.

    Returns
    -------
    ConnectionTestResult
        Status, message, and sample metadata.

    Raises
    ------
    UnknownCatalogueReferenceError
        When the connector is not registered.
    """
    connector = resolve_connector(catalogue, connector_id)
    if not connector.approved:
        return ConnectionTestResult(
            connector_id=connector.id,
            status="blocked",
            message="the connector has no owner approval",
            sample_metadata={},
        )
    if probe is not None:
        if probe(connector.authentication_reference):
            return ConnectionTestResult(
                connector_id=connector.id,
                status="ok",
                message="the connection probe succeeded",
                sample_metadata=dict(connector.test_connection.sample_metadata),
            )
        return ConnectionTestResult(
            connector_id=connector.id,
            status="failed",
            message="the connection probe failed",
            sample_metadata={},
        )
    if connector.test_connection.method == "environment":
        source = environ if environ is not None else os.environ
        variable = connector.test_connection.reference.removeprefix("env:")
        if source.get(variable):
            return ConnectionTestResult(
                connector_id=connector.id,
                status="ok",
                message=f"environment variable {variable} is present",
                sample_metadata=dict(connector.test_connection.sample_metadata),
            )
        return ConnectionTestResult(
            connector_id=connector.id,
            status="failed",
            message=f"environment variable {variable} is not present",
            sample_metadata={},
        )
    return ConnectionTestResult(
        connector_id=connector.id,
        status="not_configured",
        message=(
            "the connector needs an owner-side probe; this process cannot reach its "
            f"{connector.authentication_method} reference"
        ),
        sample_metadata=dict(connector.test_connection.sample_metadata),
    )


def scan_for_secrets(text: str) -> tuple[str, ...]:
    """Scan catalogue text for secret-shaped values.

    Parameters
    ----------
    text : str
        Serialized catalogue, connector, or free text.

    Returns
    -------
    tuple of str
        Stable ``CATALOGUE-SECRET`` findings. The secret value is never echoed.
    """
    findings: list[str] = []
    for label, pattern in SECRET_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append(f"CATALOGUE-SECRET: {label} pattern found")
    for match in SECRET_KEY_PATTERN.finditer(text):
        value = match.group(1)
        if value and not value.startswith(("env:", "secret_store:", "managed_identity:")):
            findings.append("CATALOGUE-SECRET: secret-shaped JSON key found")
            break
    return tuple(dict.fromkeys(findings))


def validate_catalogue(catalogue: DataCatalogue) -> ContractValidation:
    """Validate the public sources, private connectors, and approval metadata.

    Parameters
    ----------
    catalogue : DataCatalogue
        Catalogue to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates(
        "CATALOGUE",
        "source",
        [source.id for source in catalogue.sources],
        errors,
    )
    check_duplicates(
        "CATALOGUE",
        "connector",
        [connector.id for connector in catalogue.connectors],
        errors,
    )
    source_ids = {source.id for source in catalogue.sources}
    for source in catalogue.sources:
        if source.classification not in PUBLIC_CLASSIFICATIONS:
            errors.append(
                f"CATALOGUE-CLASSIFICATION: source {source.id} has classification "
                f"{source.classification!r}, expected public or synthetic"
            )
        if source.licence.strip().casefold() in UNUSABLE_PUBLIC_LICENCES:
            errors.append(f"CATALOGUE-LICENCE: source {source.id} has no usable licence")
        if not source.coverage.strip():
            errors.append(f"CATALOGUE-COVERAGE: source {source.id} has no coverage note")
        if not source.crs.strip():
            errors.append(f"CATALOGUE-CRS: source {source.id} has no CRS")
        if not source.query.strip():
            errors.append(f"CATALOGUE-QUERY: source {source.id} has no query")
        if not source.vintage.strip():
            errors.append(f"CATALOGUE-VINTAGE: source {source.id} has no vintage")
        if source.access_method not in ACCESS_METHODS:
            errors.append(
                f"CATALOGUE-ACCESS: source {source.id} has unknown access method "
                f"{source.access_method!r}"
            )
        if source.access_status not in ACCESS_STATUSES:
            errors.append(
                f"CATALOGUE-ACCESS: source {source.id} has unknown access status "
                f"{source.access_status!r}"
            )
    for connector in catalogue.connectors:
        if connector.classification not in PRIVATE_CLASSIFICATIONS:
            errors.append(
                f"CATALOGUE-CLASSIFICATION: connector {connector.id} has classification "
                f"{connector.classification!r}, expected private or restricted"
            )
        for linked_id in connector.linked_source_ids:
            if linked_id not in source_ids:
                errors.append(
                    f"CATALOGUE-SOURCE: connector {connector.id} links unknown source {linked_id}"
                )
        expected_prefix = AUTH_METHOD_PREFIXES.get(connector.authentication_method)
        if expected_prefix is None:
            errors.append(
                f"CATALOGUE-AUTH: connector {connector.id} has unknown authentication method "
                f"{connector.authentication_method!r}"
            )
        if not connector.authentication_reference.strip():
            errors.append(
                f"CATALOGUE-AUTH: connector {connector.id} has no authentication reference"
            )
        elif not AUTH_REFERENCE_PATTERN.fullmatch(connector.authentication_reference):
            errors.append(
                f"CATALOGUE-AUTH: connector {connector.id} authentication reference is not "
                "a non-secret env, secret_store, or managed_identity reference"
            )
        elif expected_prefix is not None and not connector.authentication_reference.startswith(
            expected_prefix
        ):
            errors.append(
                f"CATALOGUE-AUTH: connector {connector.id} reference does not match "
                f"{connector.authentication_method}"
            )
        tables = set(connector.read_scope.tables)
        if not tables:
            errors.append(f"CATALOGUE-SCOPE: connector {connector.id} has no read-scope tables")
        if connector.read_scope.max_rows <= 0:
            errors.append(f"CATALOGUE-SCOPE: connector {connector.id} max_rows must be positive")
        for table in connector.read_scope.columns:
            if table not in tables:
                errors.append(
                    f"CATALOGUE-SCOPE: connector {connector.id} has columns for unknown table "
                    f"{table}"
                )
        if not connector.allowed_outputs:
            errors.append(f"CATALOGUE-OUTPUT: connector {connector.id} has no allowed outputs")
        for output in connector.allowed_outputs:
            if output not in ALLOWED_OUTPUTS:
                errors.append(
                    f"CATALOGUE-OUTPUT: connector {connector.id} has unknown allowed output "
                    f"{output!r}"
                )
        if not connector.audit.record_location.strip():
            errors.append(f"CATALOGUE-AUDIT: connector {connector.id} has no audit record location")
        if not connector.test_connection.reference.strip():
            errors.append(
                f"CATALOGUE-TEST: connector {connector.id} has no test-connection reference"
            )
        elif not AUTH_REFERENCE_PATTERN.fullmatch(connector.test_connection.reference):
            errors.append(
                f"CATALOGUE-TEST: connector {connector.id} test reference is not "
                "a non-secret env, secret_store, or managed_identity reference"
            )
        if connector.test_connection.method not in AUTH_METHODS:
            errors.append(
                f"CATALOGUE-TEST: connector {connector.id} has unknown test method "
                f"{connector.test_connection.method!r}"
            )
        test_prefix = AUTH_METHOD_PREFIXES.get(connector.test_connection.method)
        if (
            test_prefix is not None
            and connector.test_connection.reference.startswith(
                ("env:", "secret_store:", "managed_identity:")
            )
            and not connector.test_connection.reference.startswith(test_prefix)
        ):
            errors.append(
                f"CATALOGUE-TEST: connector {connector.id} test reference does not match "
                f"{connector.test_connection.method}"
            )
        if connector.approval is not None:
            if not connector.approval.approved_by.strip():
                errors.append(
                    f"CATALOGUE-APPROVAL: connector {connector.id} approval has no approver"
                )
            if not connector.approval.data_sharing_record.strip():
                errors.append(
                    f"CATALOGUE-APPROVAL: connector {connector.id} approval has no "
                    "data-sharing record"
                )
            if connector.approval.approved_utc.tzinfo is None:
                errors.append(
                    f"CATALOGUE-APPROVAL: connector {connector.id} approval time is not "
                    "timezone-aware"
                )
    errors.extend(scan_for_secrets(catalogue.model_dump_json()))
    if catalogue.created_utc.tzinfo is None:
        errors.append("CATALOGUE-TIME: created_utc is not timezone-aware")
    if not catalogue.sources:
        warnings.append("CATALOGUE-EMPTY: the catalogue has no public sources")
    if not catalogue.connectors:
        warnings.append("CATALOGUE-EMPTY: the catalogue has no private connectors")
    counts: dict[str, int | float] = {
        "sources": len(catalogue.sources),
        "connectors": len(catalogue.connectors),
        "approved_connectors": len(approved_connector_ids(catalogue)),
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


__all__ = [
    "ACCESS_METHODS",
    "ACCESS_STATUSES",
    "ALLOWED_OUTPUTS",
    "AUTH_METHODS",
    "CATALOGUE_SCHEMA_VERSION",
    "PRIVATE_CLASSIFICATIONS",
    "PUBLIC_CLASSIFICATIONS",
    "AuditRule",
    "ConnectionTest",
    "ConnectionTestResult",
    "ConnectorApproval",
    "ConnectorRecord",
    "DataCatalogue",
    "ReadScope",
    "SourceRecord",
    "UnknownCatalogueReferenceError",
    "agent_can_read",
    "agent_metadata",
    "approved_connector_ids",
    "connector_agent_metadata",
    "resolve_connector",
    "resolve_source",
    "run_connection_test",
    "scan_for_secrets",
    "validate_catalogue",
]

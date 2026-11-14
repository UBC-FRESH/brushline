"""Minimal map-to-instance model-builder service.

The service is a prototype over the P2 catalogue, fetch plan, coverage, and gap contracts. It has
no network fetch, no private-data read, and no full planning studio. A dry run writes the fetch plan
and the review metadata, not a dataset payload. A synthetic local build is available for the
committed fixture; a custom AOI stays blocked until a real provider stage exists.
"""

from __future__ import annotations

import json
import shutil
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from brushline.build.compiler import compile_fixture
from brushline.instance_ops import seed_state_file, validate_scenario_file
from brushline.instance_template import TEMPLATE_ROOT
from brushline.integrations.catalogue import (
    ConnectorApproval,
    DataCatalogue,
    agent_metadata,
    resolve_source,
)
from brushline.integrations.fetch import (
    CoverageEntry,
    CoverageReport,
    FetchApproval,
    FetchPlan,
    FetchRequest,
    GapRecord,
    GapReport,
    build_gap_report,
    coverage_counts,
    plan_fetch,
    validate_fetch_plan,
)
from brushline.model.corridor import CorridorNetwork, validate_corridor_network
from brushline.model.schema import DatasetManifest
from brushline.model.state import StateContract, validate_state_contract

MODEL_BUILDER_SCHEMA_VERSION: Literal["brushline.model-builder-session.v1"] = (
    "brushline.model-builder-session.v1"
)
REVIEW_SCHEMA_VERSION: Literal["brushline.model-builder-review.v1"] = (
    "brushline.model-builder-review.v1"
)
HANDOFF_SCHEMA_VERSION: Literal["brushline.handoff.v1"] = "brushline.handoff.v1"
DEFAULT_RUNTIME_ROOT = Path("runtime/model-builder")
DEFAULT_CATALOGUE_PATH = (
    Path(__file__).resolve().parents[2] / "notes" / "reference" / "data-catalogue.v1.json"
)
DEFAULT_FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "examples" / "synthetic-corridor"
STATIC_ROOT = Path(__file__).resolve().with_name("static")
DEFAULT_SOURCE_IDS: tuple[str, ...] = (
    "lidarbc",
    "vri",
    "dra",
    "ften",
    "bec",
    "boundaries",
)
SYNTHETIC_OBSERVED: frozenset[str] = frozenset(DEFAULT_SOURCE_IDS)
ASSET_TYPES: tuple[str, ...] = ("transmission", "pipeline", "railway", "road", "other")
MANAGEMENT_STANDARDS: tuple[str, ...] = (
    "clearance",
    "reliability",
    "fire_safety",
    "access",
)
DEFAULT_AOI_ID = "synthetic-corridor"


class AoiOption(BaseModel):
    """One selectable AOI in the prototype.

    Parameters
    ----------
    id : str
        Stable AOI id.
    name : str
        Human name.
    asset_type : str
        Linear asset type.
    management_standard : str
        Management standard.
    geometry : dict of str to object
        GeoJSON geometry.
    bbox : list of float
        Bounding box in ``minx, miny, maxx, maxy`` order.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    asset_type: str = "transmission"
    management_standard: str = "clearance"
    geometry: dict[str, object]
    bbox: list[float] = Field(min_length=4, max_length=4)


class SessionCreate(BaseModel):
    """Request to create a model-builder session.

    Parameters
    ----------
    aoi_id : str, optional
        Selectable AOI id. Defaults to the synthetic corridor.
    geometry : dict of str to object or None, optional
        A drawn GeoJSON Polygon or MultiPolygon. Overrides ``aoi_id``.
    name : str or None, optional
        Name for a drawn AOI.
    asset_type : str, optional
        Linear asset type.
    management_standard : str, optional
        Management standard.
    horizon_years : int, optional
        Planning horizon.
    currency : str, optional
        Cost currency.
    source_ids : list of str or None, optional
        Public source ids. Defaults to the six observed synthetic sources.
    connector_ids : list of str, optional
        Private connector ids.
    bulk_fetch : bool, optional
        Whether the plan is a bulk fetch.
    dry_run : bool, optional
        Whether the build is a dry run. Defaults to ``True``.
    """

    model_config = ConfigDict(extra="forbid")

    aoi_id: str = DEFAULT_AOI_ID
    geometry: dict[str, object] | None = None
    name: str = "Drawn AOI"
    asset_type: str = "transmission"
    management_standard: str = "clearance"
    horizon_years: int = Field(default=5, ge=1, le=50)
    currency: str = "CAD"
    source_ids: list[str] | None = None
    connector_ids: list[str] = Field(default_factory=list)
    bulk_fetch: bool = False
    dry_run: bool = True


class SourceAvailability(BaseModel):
    """One source availability row.

    Parameters
    ----------
    source_id : str
        Source id.
    name : str
        Human name.
    provider : str
        Provider.
    licence : str
        Licence.
    access_status : str
        Catalogue access status.
    coverage_state : str
        One of the six coverage states.
    coverage_pct : float
        Coverage percentage.
    evidence : str
        Evidence reference.
    reason : str
        Missing or non-observed reason.
    selected : bool
        Whether the session requests the source.
    required : bool
        Whether a gap stops the build.
    """

    model_config = ConfigDict(extra="forbid")

    source_id: str
    name: str
    provider: str
    licence: str
    access_status: str
    coverage_state: str
    coverage_pct: float
    evidence: str = ""
    reason: str = ""
    selected: bool
    required: bool


class BuildStage(BaseModel):
    """One build progress event.

    Parameters
    ----------
    name : str
        Stage name.
    validator : str
        Validator that decides the stage.
    status : str
        ``pending``, ``running``, ``passed``, ``failed``, or ``skipped``.
    detail : str
        Short evidence or reason.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    validator: str = Field(min_length=1)
    status: str = "pending"
    detail: str = ""


class ApprovalRequest(BaseModel):
    """A user approval for a session.

    Parameters
    ----------
    public_sources : bool, optional
        Approve the selected public sources.
    bulk_fetch : bool, optional
        Approve the bulk scope.
    connector_ids : list of str, optional
        Private connector ids to approve.
    approved_by : str, optional
        Who approved the session.
    """

    model_config = ConfigDict(extra="forbid")

    public_sources: bool = False
    bulk_fetch: bool = False
    connector_ids: list[str] = Field(default_factory=list)
    approved_by: str = "model-builder-user"


class BuildRequest(BaseModel):
    """A request to run the build stages.

    Parameters
    ----------
    dry_run : bool or None, optional
        Override the session dry-run flag.
    """

    model_config = ConfigDict(extra="forbid")

    dry_run: bool | None = None


class ReviewSummary(BaseModel):
    """The review screen for a completed dry run.

    Parameters
    ----------
    schema_version : {"brushline.model-builder-review.v1"}
        Review schema version.
    instance_id : str
        Session id.
    aoi_name : str
        AOI name.
    segment_count : int
        Segment count.
    state_distribution : dict of str to int
        Initial state class counts.
    model_cards : list of str
        Model cards available in the fixture.
    coverage_counts : dict of str to int or float
        Coverage state counts.
    gaps : list of GapRecord
        Non-observed coverage entries.
    open_questions : list of str
        Questions the reviewer must see.
    licences : list of str
        Licences in the selected sources and fixture.
    provenance : dict of str to object
        Dataset provenance references.
    source : str
        Data source description.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.model-builder-review.v1"] = REVIEW_SCHEMA_VERSION
    instance_id: str
    aoi_name: str
    segment_count: int = Field(ge=0)
    state_distribution: dict[str, int] = Field(default_factory=dict)
    model_cards: list[str] = Field(default_factory=list)
    coverage_counts: dict[str, int | float] = Field(default_factory=dict)
    gaps: list[GapRecord] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    licences: list[str] = Field(default_factory=list)
    provenance: dict[str, object] = Field(default_factory=dict)
    source: str = "synthetic-fixture"


class HandoffRecord(BaseModel):
    """A linked instance handoff record.

    Parameters
    ----------
    schema_version : {"brushline.handoff.v1"}
        Handoff schema version.
    session_id : str
        Session id.
    instance_root : str
        Linked instance path.
    status : str
        Handoff status.
    dry_run : bool
        Whether the handoff points at a dry run.
    created_utc : datetime
        Timezone-aware creation time.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.handoff.v1"] = HANDOFF_SCHEMA_VERSION
    session_id: str
    instance_root: str
    status: str = "linked"
    dry_run: bool
    created_utc: datetime


class BuilderSession(BaseModel):
    """One model-builder session.

    Parameters
    ----------
    schema_version : {"brushline.model-builder-session.v1"}
        Session schema version.
    session_id : str
        Session id.
    aoi : AoiOption
        Selected AOI.
    asset_type : str
        Linear asset type.
    management_standard : str
        Management standard.
    horizon_years : int
        Planning horizon.
    currency : str
        Cost currency.
    source_ids : list of str
        Selected public sources.
    connector_ids : list of str
        Selected private connectors.
    bulk_fetch : bool
        Whether the plan is a bulk request.
    dry_run : bool
        Whether the build is a dry run.
    public_approved : bool
        Whether public sources are approved.
    bulk_approved : bool
        Whether bulk scope is approved.
    approved_connectors : list of str
        Explicitly approved private connectors.
    approved_by : str
        Approver label.
    approved_utc : datetime or None
        Approval time.
    plan : FetchPlan
        Plan-only fetch preview.
    availability : list of SourceAvailability
        Source availability.
    coverage : CoverageReport
        Coverage states.
    gap : GapReport
        Gap report.
    status : str
        Session status.
    stages : list of BuildStage
        Build progress.
    review : ReviewSummary or None
        Review summary after a build.
    handoff : HandoffRecord or None
        Handoff record.
    created_utc : datetime
        Session creation time.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.model-builder-session.v1"] = MODEL_BUILDER_SCHEMA_VERSION
    session_id: str
    aoi: AoiOption
    asset_type: str
    management_standard: str
    horizon_years: int
    currency: str
    source_ids: list[str]
    connector_ids: list[str]
    bulk_fetch: bool
    dry_run: bool
    public_approved: bool = False
    bulk_approved: bool = False
    approved_connectors: list[str] = Field(default_factory=list)
    approved_by: str = ""
    approved_utc: datetime | None = None
    plan: FetchPlan
    availability: list[SourceAvailability]
    coverage: CoverageReport
    gap: GapReport
    status: str = "planned"
    stages: list[BuildStage] = Field(default_factory=list)
    review: ReviewSummary | None = None
    handoff: HandoffRecord | None = None
    created_utc: datetime


class ModelBuilderStore:
    """In-memory sessions over the committed synthetic fixture.

    Parameters
    ----------
    catalogue : DataCatalogue or None, optional
        Catalogue. Defaults to the committed reference JSON.
    fixture_root : Path or None, optional
        Synthetic fixture root.
    runtime_root : Path or None, optional
        Runtime artifact root.
    """

    def __init__(
        self,
        *,
        catalogue: DataCatalogue | None = None,
        fixture_root: Path | None = None,
        runtime_root: Path | None = None,
    ) -> None:
        self.catalogue = catalogue or _load_catalogue()
        self.fixture_root = fixture_root or DEFAULT_FIXTURE_ROOT
        self.runtime_root = runtime_root or DEFAULT_RUNTIME_ROOT
        self.sessions: dict[str, BuilderSession] = {}

    def aoi_options(self) -> list[AoiOption]:
        """Return selectable AOIs.

        Returns
        -------
        list of AoiOption
            The synthetic corridor AOI.
        """
        aoi = _synthetic_aoi(self.fixture_root)
        return [aoi]

    def catalogue_view(self) -> dict[str, object]:
        """Return the agent-safe catalogue metadata.

        Returns
        -------
        dict of str to object
            Public sources and safe connector metadata.
        """
        return agent_metadata(self.catalogue)

    def create_session(self, request: SessionCreate) -> BuilderSession:
        """Create a plan-only session.

        Parameters
        ----------
        request : SessionCreate
            Session request.

        Returns
        -------
        BuilderSession
            New planned session.

        Raises
        ------
        ValueError
            When an AOI, source, or connector is invalid.
        """
        aoi = self._resolve_aoi(request)
        source_ids = list(
            dict.fromkeys(
                request.source_ids if request.source_ids is not None else DEFAULT_SOURCE_IDS
            )
        )
        connector_ids = list(dict.fromkeys(request.connector_ids))
        source_set = {source.id for source in self.catalogue.sources}
        connector_set = {connector.id for connector in self.catalogue.connectors}
        if unknown := sorted(set(source_ids) - source_set):
            raise ValueError(f"unknown sources: {', '.join(unknown)}")
        if unknown := sorted(set(connector_ids) - connector_set):
            raise ValueError(f"unknown connectors: {', '.join(unknown)}")
        created = datetime.now(UTC)
        session_id = f"mb-{created.strftime('%Y%m%d%H%M%S%f')}"
        coverage = self._coverage(session_id, created, aoi, source_ids)
        gap = build_gap_report(coverage)
        plan = self._plan(
            session_id,
            created,
            aoi,
            source_ids,
            connector_ids,
            request.bulk_fetch,
            {},
            self.catalogue,
        )
        session = BuilderSession(
            session_id=session_id,
            aoi=aoi,
            asset_type=request.asset_type,
            management_standard=request.management_standard,
            horizon_years=request.horizon_years,
            currency=request.currency,
            source_ids=source_ids,
            connector_ids=connector_ids,
            bulk_fetch=request.bulk_fetch,
            dry_run=request.dry_run,
            plan=plan,
            availability=self._availability(coverage, source_ids),
            coverage=coverage,
            gap=gap,
            status="planned",
            created_utc=created,
        )
        self._save_plan(session)
        self.sessions[session_id] = session
        return session

    def get(self, session_id: str) -> BuilderSession:
        """Return one session.

        Parameters
        ----------
        session_id : str
            Session id.

        Returns
        -------
        BuilderSession
            Session.

        Raises
        ------
        KeyError
            When the session does not exist.
        """
        return self.sessions[session_id]

    def approve(self, session_id: str, request: ApprovalRequest) -> BuilderSession:
        """Record approvals and rebuild the plan preview.

        Parameters
        ----------
        session_id : str
            Session id.
        request : ApprovalRequest
            Approval fields.

        Returns
        -------
        BuilderSession
            Updated session.

        Raises
        ------
        ValueError
            When a connector is not selected.
        """
        session = self.get(session_id)
        invalid = sorted(set(request.connector_ids) - set(session.connector_ids))
        if invalid:
            raise ValueError(f"connectors are not selected: {', '.join(invalid)}")
        approved = sorted(set(session.approved_connectors) | set(request.connector_ids))
        approved_utc = datetime.now(UTC)
        updated = session.model_copy(
            update={
                "public_approved": session.public_approved or request.public_sources,
                "bulk_approved": session.bulk_approved or request.bulk_fetch,
                "approved_connectors": approved,
                "approved_by": request.approved_by,
                "approved_utc": approved_utc,
            }
        )
        catalogue = self._catalogue_for_session(updated)
        plan = self._plan(
            session.session_id,
            session.created_utc,
            session.aoi,
            session.source_ids,
            session.connector_ids,
            session.bulk_fetch,
            self._approvals(updated),
            catalogue,
        )
        report = validate_fetch_plan(plan, catalogue)
        status = "approved" if report.is_valid else "blocked"
        updated = updated.model_copy(update={"plan": plan, "status": status})
        self._save_plan(updated)
        self.sessions[session_id] = updated
        return updated

    def build(self, session_id: str, request: BuildRequest) -> BuilderSession:
        """Run the build stages, defaulting to a dry run.

        Parameters
        ----------
        session_id : str
            Session id.
        request : BuildRequest
            Build options.

        Returns
        -------
        BuilderSession
            Updated session with progress and review.
        """
        session = self.get(session_id)
        dry_run = session.dry_run if request.dry_run is None else request.dry_run
        session = session.model_copy(update={"dry_run": dry_run})
        stages: list[BuildStage] = []
        catalogue = self._catalogue_for_session(session)
        plan = self._plan(
            session.session_id,
            session.created_utc,
            session.aoi,
            session.source_ids,
            session.connector_ids,
            session.bulk_fetch,
            self._approvals(session),
            catalogue,
        )
        session = session.model_copy(update={"plan": plan})
        self._save_plan(session)
        try:
            _bbox_from_geometry(session.aoi.geometry)
            stages.append(
                BuildStage(
                    name="validate_aoi",
                    validator="brushline.instance.validate-aoi",
                    status="passed",
                    detail=f"{session.aoi.name} is a valid polygon",
                )
            )
        except ValueError as exc:
            stages.append(
                BuildStage(
                    name="validate_aoi",
                    validator="brushline.instance.validate-aoi",
                    status="failed",
                    detail=str(exc),
                )
            )
            return self._finish(session, stages, "blocked", None)
        report = validate_fetch_plan(plan, catalogue)
        if not report.is_valid:
            stages.append(
                BuildStage(
                    name="fetch_plan",
                    validator="validate_fetch_plan",
                    status="failed",
                    detail="; ".join(report.errors),
                )
            )
            return self._finish(session, stages, "blocked", None)
        stages.append(
            BuildStage(
                name="fetch_plan",
                validator="validate_fetch_plan",
                status="passed",
                detail=f"{len(plan.items)} items, {len(report.warnings)} warnings",
            )
        )
        if dry_run:
            stages.append(
                BuildStage(
                    name="fetch",
                    validator="materialization_decision",
                    status="skipped",
                    detail="dry run: no network call",
                )
            )
        elif session.aoi.id == DEFAULT_AOI_ID:
            stages.append(
                BuildStage(
                    name="fetch",
                    validator="materialization_decision",
                    status="passed",
                    detail="synthetic local build: no network call",
                )
            )
        else:
            stages.append(
                BuildStage(
                    name="fetch",
                    validator="materialization_decision",
                    status="failed",
                    detail="a custom AOI has no materialization path in the prototype",
                )
            )
            return self._finish(session, stages, "blocked", None)
        if session.aoi.id == DEFAULT_AOI_ID:
            try:
                network = CorridorNetwork.model_validate_json(
                    (self.fixture_root / "corridor.json").read_text(encoding="utf-8")
                )
                corridor_report = validate_corridor_network(network)
                if not corridor_report.is_valid:
                    raise ValueError("; ".join(corridor_report.errors))
                stages.append(
                    BuildStage(
                        name="segment_corridor",
                        validator="validate_corridor_network",
                        status="passed",
                        detail=f"{len(network.segments)} segments",
                    )
                )
            except (OSError, ValueError) as exc:
                stages.append(
                    BuildStage(
                        name="segment_corridor",
                        validator="validate_corridor_network",
                        status="failed",
                        detail=str(exc),
                    )
                )
                return self._finish(session, stages, "blocked", None)
        else:
            stages.append(
                BuildStage(
                    name="segment_corridor",
                    validator="validate_corridor_network",
                    status="failed",
                    detail="the prototype has no segmenter for a custom AOI",
                )
            )
            return self._finish(session, stages, "blocked", None)
        if dry_run:
            for name, validator in (
                ("compile_dataset", "validate_dataset"),
                ("seed_vegetation_state", "validate_state_contract"),
                ("validate_scenario", "validate_scenario_file"),
                ("build_demo", "validate_demo_manifest"),
            ):
                stages.append(
                    BuildStage(
                        name=name,
                        validator=validator,
                        status="skipped",
                        detail="dry run: no payload written",
                    )
                )
            review = self._review(session)
            stages.append(
                BuildStage(
                    name="review",
                    validator="review_summary",
                    status="passed",
                    detail="synthetic fixture review",
                )
            )
            return self._finish(session, stages, "complete", review)
        try:
            compiled = compile_fixture(
                self.fixture_root,
                self.runtime_root / session.session_id / "dataset",
                force=True,
            )
            stages.append(
                BuildStage(
                    name="compile_dataset",
                    validator="validate_dataset",
                    status="passed",
                    detail=f"{len(compiled.manifest.tables)} tables",
                )
            )
            state = StateContract.model_validate_json(
                (self.fixture_root / "state.json").read_text(encoding="utf-8")
            )
            state_report = validate_state_contract(state)
            if not state_report.is_valid:
                raise ValueError("; ".join(state_report.errors))
            seed_state_file(
                self.fixture_root / "state.json",
                self.runtime_root / session.session_id,
            )
            stages.append(
                BuildStage(
                    name="seed_vegetation_state",
                    validator="validate_state_contract",
                    status="passed",
                    detail=f"{len(state.states)} states",
                )
            )
        except (OSError, ValueError) as exc:
            stages.append(
                BuildStage(
                    name="compile_dataset",
                    validator="validate_dataset",
                    status="failed",
                    detail=str(exc),
                )
            )
            return self._finish(session, stages, "blocked", None)
        scenario = TEMPLATE_ROOT / "config" / "brushline" / "scenario.yaml"
        targets = TEMPLATE_ROOT / "config" / "brushline" / "targets.yaml"
        try:
            validate_scenario_file(
                scenario,
                targets,
                self.runtime_root / session.session_id / "scenario",
            )
            stages.append(
                BuildStage(
                    name="validate_scenario",
                    validator="validate_scenario_file",
                    status="passed",
                    detail="scenario and targets are valid",
                )
            )
            shutil.copy2(
                self.fixture_root / "demo.json",
                self.runtime_root / session.session_id / "demo.json",
            )
            stages.append(
                BuildStage(
                    name="build_demo",
                    validator="validate_demo_manifest",
                    status="passed",
                    detail="synthetic demo manifest copied",
                )
            )
        except (OSError, ValueError) as exc:
            stages.append(
                BuildStage(
                    name="validate_scenario",
                    validator="validate_scenario_file",
                    status="failed",
                    detail=str(exc),
                )
            )
            return self._finish(session, stages, "blocked", None)
        review = self._review(session)
        stages.append(
            BuildStage(
                name="review",
                validator="review_summary",
                status="passed",
                detail="synthetic fixture review",
            )
        )
        return self._finish(session, stages, "complete", review)

    def review(self, session_id: str) -> ReviewSummary:
        """Return the review for a completed session.

        Parameters
        ----------
        session_id : str
            Session id.

        Returns
        -------
        ReviewSummary
            Review.

        Raises
        ------
        ValueError
            When no review is available.
        """
        session = self.get(session_id)
        if session.review is None:
            raise ValueError("review is not available until the build completes")
        return session.review

    def handoff(self, session_id: str) -> HandoffRecord:
        """Write a linked instance handoff record.

        Parameters
        ----------
        session_id : str
            Session id.

        Returns
        -------
        HandoffRecord
            Handoff record.

        Raises
        ------
        ValueError
            When the session has no completed review.
        """
        session = self.get(session_id)
        if session.review is None:
            raise ValueError("handoff requires a completed review")
        created = datetime.now(UTC)
        instance_root = self.runtime_root / session.session_id / "instance"
        instance_root.mkdir(parents=True, exist_ok=True)
        record = HandoffRecord(
            session_id=session.session_id,
            instance_root=str(instance_root),
            dry_run=session.dry_run,
            created_utc=created,
        )
        (self.runtime_root / session.session_id / "handoff.json").write_text(
            record.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        updated = session.model_copy(update={"handoff": record})
        self.sessions[session_id] = updated
        return record

    def _resolve_aoi(self, request: SessionCreate) -> AoiOption:
        if request.geometry is not None:
            bbox = _bbox_from_geometry(request.geometry)
            return AoiOption(
                id="custom",
                name=request.name,
                asset_type=request.asset_type,
                management_standard=request.management_standard,
                geometry=request.geometry,
                bbox=bbox,
            )
        if request.aoi_id != DEFAULT_AOI_ID:
            raise ValueError(f"unknown AOI: {request.aoi_id}")
        aoi = _synthetic_aoi(self.fixture_root)
        return aoi.model_copy(
            update={
                "asset_type": request.asset_type,
                "management_standard": request.management_standard,
            }
        )

    def _coverage(
        self,
        session_id: str,
        created: datetime,
        aoi: AoiOption,
        source_ids: list[str],
    ) -> CoverageReport:
        selected = set(source_ids)
        entries: list[CoverageEntry] = []
        for source in self.catalogue.sources:
            required = source.id in selected
            if aoi.id == DEFAULT_AOI_ID and source.id in SYNTHETIC_OBSERVED:
                entries.append(
                    CoverageEntry(
                        source_id=source.id,
                        state="observed",
                        coverage_pct=100,
                        evidence="synthetic-fixture:coverage",
                        required=required,
                    )
                )
            else:
                reason = (
                    "the custom AOI has no spatial coverage query in the prototype"
                    if aoi.id != DEFAULT_AOI_ID
                    else "not queried in the synthetic map-to-instance prototype"
                )
                entries.append(
                    CoverageEntry(
                        source_id=source.id,
                        state="missing",
                        coverage_pct=0,
                        reason=reason,
                        required=required,
                    )
                )
        return CoverageReport(
            plan_id=session_id,
            created_utc=created,
            aoi=aoi.name,
            entries=entries,
        )

    def _availability(
        self,
        coverage: CoverageReport,
        source_ids: list[str],
    ) -> list[SourceAvailability]:
        by_id = {entry.source_id: entry for entry in coverage.entries}
        selected = set(source_ids)
        values: list[SourceAvailability] = []
        for source in self.catalogue.sources:
            entry = by_id[source.id]
            values.append(
                SourceAvailability(
                    source_id=source.id,
                    name=source.name,
                    provider=source.provider,
                    licence=source.licence,
                    access_status=source.access_status,
                    coverage_state=entry.state,
                    coverage_pct=entry.coverage_pct,
                    evidence=entry.evidence,
                    reason=entry.reason,
                    selected=source.id in selected,
                    required=entry.required,
                )
            )
        return values

    def _plan(
        self,
        session_id: str,
        created: datetime,
        aoi: AoiOption,
        source_ids: list[str],
        connector_ids: list[str],
        bulk: bool,
        approvals: dict[str, FetchApproval],
        catalogue: DataCatalogue,
    ) -> FetchPlan:
        return plan_fetch(
            catalogue,
            FetchRequest(
                aoi=aoi.name,
                source_ids=source_ids,
                connector_ids=connector_ids,
                bulk=bulk,
                approvals=approvals,
            ),
            plan_id=session_id,
            created_utc=created,
        )

    def _approvals(self, session: BuilderSession) -> dict[str, FetchApproval]:
        approvals: dict[str, FetchApproval] = {}
        scope = "bulk" if session.bulk_approved else "single"
        approved_utc = session.approved_utc or datetime.now(UTC)
        if session.public_approved:
            for source_id in session.source_ids:
                approvals[source_id] = FetchApproval(
                    approved_by=session.approved_by or "model-builder-user",
                    approved_utc=approved_utc,
                    scope=scope,
                    record="model-builder-approval",
                )
        for connector_id in session.approved_connectors:
            approvals[connector_id] = FetchApproval(
                approved_by=session.approved_by or "model-builder-user",
                approved_utc=approved_utc,
                scope=scope,
                record="model-builder-approval",
            )
        return approvals

    def _catalogue_for_session(self, session: BuilderSession) -> DataCatalogue:
        if not session.approved_connectors:
            return self.catalogue
        approved = set(session.approved_connectors)
        approved_utc = session.approved_utc or datetime.now(UTC)
        connectors = []
        for connector in self.catalogue.connectors:
            if connector.id in approved:
                connector = connector.model_copy(
                    update={
                        "approval": ConnectorApproval(
                            approved_by=session.approved_by or "model-builder-user",
                            approved_utc=approved_utc,
                            data_sharing_record="model-builder-session",
                        )
                    }
                )
            connectors.append(connector)
        return self.catalogue.model_copy(update={"connectors": connectors})

    def _finish(
        self,
        session: BuilderSession,
        stages: list[BuildStage],
        status: str,
        review: ReviewSummary | None,
    ) -> BuilderSession:
        updated = session.model_copy(
            update={
                "stages": stages,
                "status": status,
                "review": review,
            }
        )
        self._save_plan(updated)
        if review is not None:
            (self.runtime_root / session.session_id / "review.json").write_text(
                review.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
            )
        self.sessions[session.session_id] = updated
        return updated

    def _review(self, session: BuilderSession) -> ReviewSummary:
        manifest = DatasetManifest.model_validate_json(
            (self.fixture_root / "dataset" / "manifest.json").read_text(encoding="utf-8")
        )
        state = StateContract.model_validate_json(
            (self.fixture_root / "state.json").read_text(encoding="utf-8")
        )
        segment_count = next(
            (table.row_count for table in manifest.tables if table.name == "segments"),
            0,
        )
        distribution = Counter(item.state_class for item in state.states)
        licences = sorted(
            {resolve_source(self.catalogue, source_id).licence for source_id in session.source_ids}
            | {manifest.provenance.licence}
        )
        questions = [
            "The synthetic fixture is not a real AOI; replace it before pilot use.",
            "No calibrated low-vegetation model card is attached; P4 will add it.",
            "Missing sources are optional in this prototype; P3 and P5 will attach real coverage.",
        ]
        if session.connector_ids and not session.approved_connectors:
            questions.append("The selected private connector has no explicit owner approval.")
        return ReviewSummary(
            instance_id=session.session_id,
            aoi_name=session.aoi.name,
            segment_count=segment_count,
            state_distribution=dict(sorted(distribution.items())),
            model_cards=list(manifest.provenance.model_cards),
            coverage_counts=coverage_counts(session.coverage),
            gaps=list(session.gap.gaps),
            open_questions=questions,
            licences=licences,
            provenance={
                "dataset_id": manifest.dataset_id,
                "content_digest": manifest.content_digest,
                "source": manifest.provenance.source,
                "source_version": manifest.provenance.source_version,
                "created_utc": manifest.created_utc.isoformat(),
            },
            source="synthetic-fixture",
        )

    def _save_plan(self, session: BuilderSession) -> None:
        target = self.runtime_root / session.session_id
        target.mkdir(parents=True, exist_ok=True)
        (target / "fetch_plan.json").write_text(
            session.plan.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )


def create_app(store: ModelBuilderStore | None = None) -> FastAPI:
    """Create the model-builder FastAPI application.

    Parameters
    ----------
    store : ModelBuilderStore, optional
        Store override, useful for tests and a different fixture.

    Returns
    -------
    FastAPI
        Application.
    """
    builder = store or ModelBuilderStore()
    app = FastAPI(
        title="Brushline model builder",
        version="0.1.2",
        description="Map-to-instance prototype: plan, approve, dry-run, review, and hand off.",
    )
    app.state.model_builder = builder
    app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_ROOT / "model-builder.html")

    @app.get("/api/model-builder/aois")
    def list_aois() -> dict[str, object]:
        return {
            "aois": [aoi.model_dump(mode="json") for aoi in builder.aoi_options()],
            "asset_types": list(ASSET_TYPES),
            "standards": list(MANAGEMENT_STANDARDS),
        }

    @app.get("/api/model-builder/catalogue")
    def get_catalogue() -> dict[str, object]:
        return builder.catalogue_view()

    @app.post("/api/model-builder/sessions", response_model=BuilderSession)
    def create_session(request: SessionCreate) -> BuilderSession:
        try:
            return builder.create_session(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/model-builder/sessions/{session_id}", response_model=BuilderSession)
    def get_session(session_id: str) -> BuilderSession:
        try:
            return builder.get(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="session not found") from exc

    @app.post(
        "/api/model-builder/sessions/{session_id}/approve",
        response_model=BuilderSession,
    )
    def approve_session(session_id: str, request: ApprovalRequest) -> BuilderSession:
        try:
            return builder.approve(session_id, request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="session not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/model-builder/sessions/{session_id}/build",
        response_model=BuilderSession,
    )
    def build_session(session_id: str, request: BuildRequest) -> BuilderSession:
        try:
            return builder.build(session_id, request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="session not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/model-builder/sessions/{session_id}/review",
        response_model=ReviewSummary,
    )
    def get_review(session_id: str) -> ReviewSummary:
        try:
            return builder.review(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="session not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/model-builder/sessions/{session_id}/handoff",
        response_model=HandoffRecord,
    )
    def handoff_session(session_id: str) -> HandoffRecord:
        try:
            return builder.handoff(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="session not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/model-builder/sessions/{session_id}/progress")
    def progress(session_id: str) -> StreamingResponse:
        try:
            session = builder.get(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="session not found") from exc
        return StreamingResponse(
            _progress_events(session),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


def _progress_events(session: BuilderSession) -> Iterator[str]:
    for stage in session.stages:
        yield f"event: stage\ndata: {json.dumps(stage.model_dump(mode='json'))}\n\n"
    yield (
        "event: done\ndata: "
        + json.dumps(
            {
                "session_id": session.session_id,
                "status": session.status,
            }
        )
        + "\n\n"
    )


def _synthetic_aoi(fixture_root: Path) -> AoiOption:
    payload = json.loads((fixture_root / "aoi.geojson").read_text(encoding="utf-8"))
    if payload.get("type") == "FeatureCollection":
        features = payload.get("features")
        if not isinstance(features, list) or not features:
            raise ValueError("synthetic AOI has no features")
        feature = features[0]
    elif payload.get("type") == "Feature":
        feature = payload
    else:
        raise ValueError("synthetic AOI must be a Feature or FeatureCollection")
    if not isinstance(feature, dict):
        raise ValueError("synthetic AOI feature is not an object")
    geometry = feature.get("geometry")
    if not isinstance(geometry, dict):
        raise ValueError("synthetic AOI has no geometry")
    return AoiOption(
        id=DEFAULT_AOI_ID,
        name="Synthetic corridor AOI",
        geometry=geometry,
        bbox=_bbox_from_geometry(geometry),
    )


def _bbox_from_geometry(geometry: object) -> list[float]:
    if not isinstance(geometry, dict):
        raise ValueError("AOI geometry must be an object")
    kind = geometry.get("type")
    if kind not in ("Polygon", "MultiPolygon"):
        raise ValueError("AOI geometry must be a Polygon or MultiPolygon")
    pairs = _coordinate_pairs(geometry.get("coordinates"))
    if len(pairs) < 3:
        raise ValueError("AOI geometry needs at least three coordinate pairs")
    xs = [pair[0] for pair in pairs]
    ys = [pair[1] for pair in pairs]
    if min(xs) == max(xs) or min(ys) == max(ys):
        raise ValueError("AOI geometry must have a positive area")
    return [min(xs), min(ys), max(xs), max(ys)]


def _coordinate_pairs(value: object) -> list[tuple[float, float]]:
    if isinstance(value, (list, tuple)):
        if len(value) >= 2 and all(
            isinstance(item, (int, float)) and not isinstance(item, bool) for item in value[:2]
        ):
            return [(float(value[0]), float(value[1]))]
        pairs: list[tuple[float, float]] = []
        for child in value:
            pairs.extend(_coordinate_pairs(child))
        return pairs
    return []


def _load_catalogue() -> DataCatalogue:
    if DEFAULT_CATALOGUE_PATH.is_file():
        return DataCatalogue.model_validate_json(DEFAULT_CATALOGUE_PATH.read_text(encoding="utf-8"))
    return DataCatalogue(created_utc=datetime.now(UTC))


app = create_app()


__all__ = [
    "ASSET_TYPES",
    "DEFAULT_AOI_ID",
    "DEFAULT_RUNTIME_ROOT",
    "DEFAULT_SOURCE_IDS",
    "HANDOFF_SCHEMA_VERSION",
    "MANAGEMENT_STANDARDS",
    "MODEL_BUILDER_SCHEMA_VERSION",
    "AoiOption",
    "ApprovalRequest",
    "BuildRequest",
    "BuildStage",
    "BuilderSession",
    "HandoffRecord",
    "ModelBuilderStore",
    "ReviewSummary",
    "SessionCreate",
    "SourceAvailability",
    "app",
    "create_app",
]

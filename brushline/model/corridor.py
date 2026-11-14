"""Corridor graph contract: corridors, segments, spans, treatment units, access, and structures.

The segment is the decision unit. A span is an ordered, contiguous run of segments between access
points. A treatment unit is a set of segments scheduled and contracted together. The graph validator
checks the stable ids, the references, the sequence order, the length conservation, the access
links, the structure links, and the service standards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CORRIDOR_SCHEMA_VERSION: Literal["brushline.corridor.v1"] = "brushline.corridor.v1"
ASSET_TYPES: tuple[str, ...] = ("transmission", "pipeline", "railway", "road", "other")
ACCESS_KINDS: tuple[str, ...] = ("road", "trail", "landing", "water", "other")

AssetType = Literal["transmission", "pipeline", "railway", "road", "other"]
AccessKind = Literal["road", "trail", "landing", "water", "other"]


@dataclass(frozen=True)
class CorridorValidation:
    """The outcome of validating a corridor graph.

    Parameters
    ----------
    errors : tuple of str
        Named errors. An empty tuple means the graph is valid.
    warnings : tuple of str
        Non-fatal findings.
    counts : dict of str to int or float
        Object counts and total segment length.
    """

    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    counts: dict[str, int | float]

    @property
    def is_valid(self) -> bool:
        """Return whether the graph passed every check.

        Returns
        -------
        bool
            ``True`` when there are no errors.
        """
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-ready report.

        Returns
        -------
        dict of str to object
            Validity, errors, warnings, and counts.
        """
        return {
            "is_valid": self.is_valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "counts": dict(sorted(self.counts.items())),
        }


class ServiceStandard(BaseModel):
    """A vegetation service standard for a segment.

    Parameters
    ----------
    service_standard_id : str
        Stable identifier.
    max_height_m : float
        Maximum allowed vegetation height in metres. Must be positive.
    min_clearance_m : float
        Minimum required clearance in metres. Must be non-negative.
    access_required : bool, optional
        Whether the segment must remain accessible. Defaults to ``True``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    service_standard_id: str = Field(min_length=1)
    max_height_m: float = Field(gt=0)
    min_clearance_m: float = Field(ge=0)
    access_required: bool = True


class Corridor(BaseModel):
    """A linear asset and the land managed along it.

    Parameters
    ----------
    corridor_id : str
        Stable identifier.
    name : str
        Human-readable name.
    asset_type : {"transmission", "pipeline", "railway", "road", "other"}
        Asset class.
    length_m : float
        Total corridor length in metres. Must be positive.
    crs : str
        Coordinate reference system.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    corridor_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    asset_type: AssetType
    length_m: float = Field(gt=0)
    crs: str = Field(min_length=1)


class Segment(BaseModel):
    """A length of corridor with stable site, access, and management attributes.

    Parameters
    ----------
    segment_id : str
        Stable identifier and decision key.
    corridor_id : str
        Owning corridor.
    span_id : str
        Owning span.
    treatment_unit_id : str
        Owning treatment unit.
    sequence : int
        Zero-based position within the span.
    length_m : float
        Segment length in metres. Must be positive.
    geometry_wkt : str
        ``LINESTRING`` or ``MULTILINESTRING`` geometry in the corridor CRS.
    service_standard_id : str
        Service standard that applies to the segment.
    access_point_id : str or None, optional
        Nearest access point, when one is known.
    structure_ids : list of str, optional
        Structures on or adjacent to the segment.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    corridor_id: str = Field(min_length=1)
    span_id: str = Field(min_length=1)
    treatment_unit_id: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    length_m: float = Field(gt=0)
    geometry_wkt: str = Field(min_length=1)
    service_standard_id: str = Field(min_length=1)
    access_point_id: str | None = None
    structure_ids: list[str] = Field(default_factory=list)

    @field_validator("geometry_wkt")
    @classmethod
    def _line_geometry(cls, value: str) -> str:
        upper = value.strip().upper()
        if not (upper.startswith("LINESTRING") or upper.startswith("MULTILINESTRING")):
            raise ValueError("segment geometry must be LINESTRING or MULTILINESTRING WKT")
        return value


class Span(BaseModel):
    """An ordered, contiguous run of segments between access points.

    Parameters
    ----------
    span_id : str
        Stable identifier.
    corridor_id : str
        Owning corridor.
    segment_ids : list of str
        Ordered segment identifiers. At least one is required.
    access_point_ids : list of str, optional
        Access points that serve the span.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    span_id: str = Field(min_length=1)
    corridor_id: str = Field(min_length=1)
    segment_ids: list[str] = Field(min_length=1)
    access_point_ids: list[str] = Field(default_factory=list)


class TreatmentUnit(BaseModel):
    """A set of segments scheduled and contracted together.

    Parameters
    ----------
    treatment_unit_id : str
        Stable identifier.
    corridor_id : str
        Owning corridor.
    segment_ids : list of str
        Segments in the unit. At least one is required.
    contract_start_year : int
        First year of the contract window.
    contract_end_year : int
        Last year of the contract window.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    treatment_unit_id: str = Field(min_length=1)
    corridor_id: str = Field(min_length=1)
    segment_ids: list[str] = Field(min_length=1)
    contract_start_year: int
    contract_end_year: int


class AccessPoint(BaseModel):
    """An access point that serves a span or a segment.

    Parameters
    ----------
    access_point_id : str
        Stable identifier.
    corridor_id : str
        Owning corridor.
    kind : {"road", "trail", "landing", "water", "other"}
        Access class.
    location_wkt : str
        ``POINT`` geometry in the corridor CRS.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    access_point_id: str = Field(min_length=1)
    corridor_id: str = Field(min_length=1)
    kind: AccessKind
    location_wkt: str = Field(min_length=1)

    @field_validator("location_wkt")
    @classmethod
    def _point_geometry(cls, value: str) -> str:
        if not value.strip().upper().startswith("POINT"):
            raise ValueError("access point geometry must be POINT WKT")
        return value


class Structure(BaseModel):
    """An asset structure on or adjacent to a segment.

    Parameters
    ----------
    structure_id : str
        Stable identifier.
    corridor_id : str
        Owning corridor.
    segment_id : str
        Segment that carries or abuts the structure.
    structure_type : str
        Structure class, such as tower, pole, valve, or crossing.
    clearance_m : float
        Required clearance in metres. Must be non-negative.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    structure_id: str = Field(min_length=1)
    corridor_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    structure_type: str = Field(min_length=1)
    clearance_m: float = Field(ge=0)


class CorridorNetwork(BaseModel):
    """The root corridor graph contract.

    Parameters
    ----------
    crs : str
        Coordinate reference system for every geometry.
    corridors : list of Corridor
        Corridors in the network.
    segments : list of Segment
        Decision segments.
    spans : list of Span
        Ordered spans.
    treatment_units : list of TreatmentUnit
        Contracted treatment units.
    access_points : list of AccessPoint
        Access points.
    structures : list of Structure
        Asset structures.
    service_standards : list of ServiceStandard
        Service standards.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.corridor.v1"] = CORRIDOR_SCHEMA_VERSION
    crs: str = Field(min_length=1)
    corridors: list[Corridor] = Field(min_length=1)
    segments: list[Segment] = Field(min_length=1)
    spans: list[Span] = Field(min_length=1)
    treatment_units: list[TreatmentUnit] = Field(min_length=1)
    access_points: list[AccessPoint] = Field(default_factory=list)
    structures: list[Structure] = Field(default_factory=list)
    service_standards: list[ServiceStandard] = Field(min_length=1)


def validate_corridor_network(
    network: CorridorNetwork,
    *,
    length_tolerance_m: float = 0.01,
) -> CorridorValidation:
    """Validate the corridor graph's ids, references, order, and length conservation.

    Parameters
    ----------
    network : CorridorNetwork
        The graph to validate.
    length_tolerance_m : float, optional
        Allowed absolute difference between a corridor length and the sum of its segments.
        Defaults to ``0.01`` metres.

    Returns
    -------
    CorridorValidation
        Errors, warnings, and object counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    corridors = {item.corridor_id: item for item in network.corridors}
    segments = {item.segment_id: item for item in network.segments}
    spans = {item.span_id: item for item in network.spans}
    treatment_units = {item.treatment_unit_id: item for item in network.treatment_units}
    access_points = {item.access_point_id: item for item in network.access_points}
    structures = {item.structure_id: item for item in network.structures}
    standards = {item.service_standard_id: item for item in network.service_standards}
    _check_duplicates("corridor", [item.corridor_id for item in network.corridors], errors)
    _check_duplicates("segment", [item.segment_id for item in network.segments], errors)
    _check_duplicates("span", [item.span_id for item in network.spans], errors)
    _check_duplicates(
        "treatment unit",
        [item.treatment_unit_id for item in network.treatment_units],
        errors,
    )
    _check_duplicates(
        "access point",
        [item.access_point_id for item in network.access_points],
        errors,
    )
    _check_duplicates("structure", [item.structure_id for item in network.structures], errors)
    _check_duplicates(
        "service standard",
        [item.service_standard_id for item in network.service_standards],
        errors,
    )

    for corridor in network.corridors:
        if corridor.crs != network.crs:
            errors.append(
                f"CORRIDOR-CRS: corridor {corridor.corridor_id} uses {corridor.crs}, "
                f"expected {network.crs}"
            )

    for segment in network.segments:
        if segment.corridor_id not in corridors:
            errors.append(
                f"CORRIDOR-REF: segment {segment.segment_id} references unknown corridor "
                f"{segment.corridor_id}"
            )
        if segment.span_id not in spans:
            errors.append(
                f"CORRIDOR-REF: segment {segment.segment_id} references unknown span "
                f"{segment.span_id}"
            )
        elif segment.segment_id not in spans[segment.span_id].segment_ids:
            errors.append(
                f"CORRIDOR-SPAN: segment {segment.segment_id} is not listed in span "
                f"{segment.span_id}"
            )
        if segment.treatment_unit_id not in treatment_units:
            errors.append(
                f"CORRIDOR-REF: segment {segment.segment_id} references unknown treatment unit "
                f"{segment.treatment_unit_id}"
            )
        if segment.service_standard_id not in standards:
            errors.append(
                f"CORRIDOR-REF: segment {segment.segment_id} references unknown service standard "
                f"{segment.service_standard_id}"
            )
        if segment.access_point_id is not None and segment.access_point_id not in access_points:
            errors.append(
                f"CORRIDOR-ACCESS: segment {segment.segment_id} references unknown access point "
                f"{segment.access_point_id}"
            )
        for structure_id in segment.structure_ids:
            if structure_id not in structures:
                errors.append(
                    f"CORRIDOR-STRUCTURE: segment {segment.segment_id} references unknown "
                    f"structure {structure_id}"
                )

    for span in network.spans:
        if span.corridor_id not in corridors:
            errors.append(
                f"CORRIDOR-REF: span {span.span_id} references unknown corridor {span.corridor_id}"
            )
        _check_duplicates(f"span {span.span_id} segment", span.segment_ids, errors)
        missing = [segment_id for segment_id in span.segment_ids if segment_id not in segments]
        for segment_id in missing:
            errors.append(
                f"CORRIDOR-REF: span {span.span_id} references unknown segment {segment_id}"
            )
        present = [segment_id for segment_id in span.segment_ids if segment_id in segments]
        for segment_id in present:
            if segments[segment_id].corridor_id != span.corridor_id:
                errors.append(
                    f"CORRIDOR-SPAN: segment {segment_id} corridor "
                    f"{segments[segment_id].corridor_id} does not match span {span.span_id}"
                )
        sequences = [segments[segment_id].sequence for segment_id in present]
        if sequences != list(range(len(present))):
            errors.append(
                f"CORRIDOR-SEQUENCE: span {span.span_id} sequences {sequences} are not the "
                f"contiguous order 0 to {len(present) - 1}"
            )
        for access_point_id in span.access_point_ids:
            if access_point_id not in access_points:
                errors.append(
                    f"CORRIDOR-ACCESS: span {span.span_id} references unknown access point "
                    f"{access_point_id}"
                )
            elif access_points[access_point_id].corridor_id != span.corridor_id:
                errors.append(
                    f"CORRIDOR-ACCESS: access point {access_point_id} corridor "
                    f"{access_points[access_point_id].corridor_id} does not match span "
                    f"{span.span_id}"
                )

    segment_units: dict[str, list[str]] = {}
    for unit in network.treatment_units:
        if unit.corridor_id not in corridors:
            errors.append(
                f"CORRIDOR-REF: treatment unit {unit.treatment_unit_id} references unknown "
                f"corridor {unit.corridor_id}"
            )
        if unit.contract_end_year < unit.contract_start_year:
            errors.append(
                f"CORRIDOR-TU: treatment unit {unit.treatment_unit_id} ends before it starts"
            )
        _check_duplicates(
            f"treatment unit {unit.treatment_unit_id} segment",
            unit.segment_ids,
            errors,
        )
        for segment_id in unit.segment_ids:
            if segment_id not in segments:
                errors.append(
                    f"CORRIDOR-REF: treatment unit {unit.treatment_unit_id} references unknown "
                    f"segment {segment_id}"
                )
                continue
            segment_units.setdefault(segment_id, []).append(unit.treatment_unit_id)
            if segments[segment_id].corridor_id != unit.corridor_id:
                errors.append(
                    f"CORRIDOR-TU: segment {segment_id} corridor "
                    f"{segments[segment_id].corridor_id} does not match treatment unit "
                    f"{unit.treatment_unit_id}"
                )
            if segments[segment_id].treatment_unit_id != unit.treatment_unit_id:
                errors.append(
                    f"CORRIDOR-TU: segment {segment_id} names treatment unit "
                    f"{segments[segment_id].treatment_unit_id} but is listed in "
                    f"{unit.treatment_unit_id}"
                )
    for segment_id, units in segment_units.items():
        if len(units) > 1:
            errors.append(
                f"CORRIDOR-TU: segment {segment_id} belongs to more than one treatment unit: "
                f"{', '.join(sorted(units))}"
            )
    for segment in network.segments:
        if segment.segment_id not in segment_units:
            errors.append(
                f"CORRIDOR-TU: segment {segment.segment_id} is not listed in its treatment unit "
                f"{segment.treatment_unit_id}"
            )

    for access in network.access_points:
        if access.corridor_id not in corridors:
            errors.append(
                f"CORRIDOR-REF: access point {access.access_point_id} references unknown corridor "
                f"{access.corridor_id}"
            )

    for structure in network.structures:
        if structure.corridor_id not in corridors:
            errors.append(
                f"CORRIDOR-REF: structure {structure.structure_id} references unknown corridor "
                f"{structure.corridor_id}"
            )
        if structure.segment_id not in segments:
            errors.append(
                f"CORRIDOR-STRUCTURE: structure {structure.structure_id} references unknown "
                f"segment {structure.segment_id}"
            )
        elif segments[structure.segment_id].corridor_id != structure.corridor_id:
            errors.append(
                f"CORRIDOR-STRUCTURE: structure {structure.structure_id} corridor "
                f"{structure.corridor_id} does not match its segment"
            )

    lengths: dict[str, float] = {}
    for segment in network.segments:
        lengths[segment.corridor_id] = lengths.get(segment.corridor_id, 0.0) + segment.length_m
    for corridor in network.corridors:
        measured = lengths.get(corridor.corridor_id, 0.0)
        if abs(measured - corridor.length_m) > length_tolerance_m:
            errors.append(
                f"CORRIDOR-LENGTH: corridor {corridor.corridor_id} length {corridor.length_m} "
                f"does not match segment sum {measured}"
            )

    for segment in network.segments:
        if segment.access_point_id is None:
            warnings.append(f"CORRIDOR-ACCESS: segment {segment.segment_id} has no access point")

    counts: dict[str, int | float] = {
        "corridors": len(network.corridors),
        "segments": len(network.segments),
        "spans": len(network.spans),
        "treatment_units": len(network.treatment_units),
        "access_points": len(network.access_points),
        "structures": len(network.structures),
        "service_standards": len(network.service_standards),
        "total_length_m": round(sum(item.length_m for item in network.segments), 6),
    }
    return CorridorValidation(tuple(errors), tuple(warnings), counts)


def _check_duplicates(label: str, values: list[str], errors: list[str]) -> None:
    """Append one error for each duplicated value.

    Parameters
    ----------
    label : str
        Human label for the collection.
    values : list of str
        Identifiers in the collection.
    errors : list of str
        Error accumulator.
    """
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    for value in sorted(duplicates):
        errors.append(f"CORRIDOR-ID: duplicate {label} id {value}")

"""Contract tests for the corridor graph: ids, references, order, access, and length."""

from __future__ import annotations

import pytest
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
from pydantic import ValidationError


def _network() -> CorridorNetwork:
    return CorridorNetwork(
        crs="EPSG:3005",
        corridors=[
            Corridor(
                corridor_id="c1",
                name="Test corridor",
                asset_type="transmission",
                length_m=30.0,
                crs="EPSG:3005",
            )
        ],
        segments=[
            Segment(
                segment_id="s1",
                corridor_id="c1",
                span_id="sp1",
                treatment_unit_id="tu1",
                sequence=0,
                length_m=10.0,
                geometry_wkt="LINESTRING (0 0, 10 0)",
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
                length_m=20.0,
                geometry_wkt="LINESTRING (10 0, 30 0)",
                service_standard_id="std1",
                access_point_id="ap1",
            ),
        ],
        spans=[
            Span(
                span_id="sp1",
                corridor_id="c1",
                segment_ids=["s1", "s2"],
                access_point_ids=["ap1"],
            )
        ],
        treatment_units=[
            TreatmentUnit(
                treatment_unit_id="tu1",
                corridor_id="c1",
                segment_ids=["s1", "s2"],
                contract_start_year=2027,
                contract_end_year=2031,
            )
        ],
        access_points=[
            AccessPoint(
                access_point_id="ap1",
                corridor_id="c1",
                kind="road",
                location_wkt="POINT (0 0)",
            )
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
            )
        ],
    )


def _with_segment(network: CorridorNetwork, index: int, **updates: object) -> CorridorNetwork:
    segments = list(network.segments)
    segments[index] = segments[index].model_copy(update=updates)
    return network.model_copy(update={"segments": segments})


def test_valid_network_passes() -> None:
    """A well-formed corridor graph passes and reports its counts."""
    report = validate_corridor_network(_network())
    assert report.is_valid
    assert report.errors == ()
    assert report.counts["corridors"] == 1
    assert report.counts["segments"] == 2
    assert report.counts["total_length_m"] == 30.0


def test_validation_report_is_json_ready() -> None:
    """The validation report serializes its validity, errors, warnings, and counts."""
    payload = validate_corridor_network(_network()).to_dict()
    assert payload["is_valid"] is True
    assert payload["errors"] == []
    assert payload["counts"] == {
        "access_points": 1,
        "corridors": 1,
        "segments": 2,
        "service_standards": 1,
        "spans": 1,
        "structures": 1,
        "total_length_m": 30.0,
        "treatment_units": 1,
    }


def test_duplicate_ids_are_named() -> None:
    """Duplicate ids in each collection fail with CORRIDOR-ID."""
    network = _network()
    variants = [
        network.model_copy(update={"corridors": [network.corridors[0], network.corridors[0]]}),
        network.model_copy(update={"segments": [network.segments[0], network.segments[0]]}),
        network.model_copy(update={"spans": [network.spans[0], network.spans[0]]}),
        network.model_copy(
            update={"treatment_units": [network.treatment_units[0], network.treatment_units[0]]}
        ),
        network.model_copy(
            update={"access_points": [network.access_points[0], network.access_points[0]]}
        ),
        network.model_copy(update={"structures": [network.structures[0], network.structures[0]]}),
        network.model_copy(
            update={
                "service_standards": [
                    network.service_standards[0],
                    network.service_standards[0],
                ]
            }
        ),
    ]
    for variant in variants:
        report = validate_corridor_network(variant)
        assert any(message.startswith("CORRIDOR-ID") for message in report.errors)


def test_corridor_crs_must_match_the_network() -> None:
    """A corridor with a different CRS fails."""
    corridor = _network().corridors[0].model_copy(update={"crs": "EPSG:4326"})
    network = _network().model_copy(update={"corridors": [corridor]})
    report = validate_corridor_network(network)
    assert any(message.startswith("CORRIDOR-CRS") for message in report.errors)


def test_unknown_segment_references_are_named() -> None:
    """Unknown corridor, span, treatment unit, standard, access, and structure references fail."""
    cases = [
        ("corridor_id", "c9"),
        ("span_id", "sp9"),
        ("treatment_unit_id", "tu9"),
        ("service_standard_id", "std9"),
        ("access_point_id", "ap9"),
        ("structure_ids", ["st9"]),
    ]
    for field, value in cases:
        report = validate_corridor_network(_with_segment(_network(), 0, **{field: value}))
        assert report.errors, field
        assert any(
            message.startswith(("CORRIDOR-REF", "CORRIDOR-STRUCTURE", "CORRIDOR-ACCESS"))
            for message in report.errors
        )


def test_segment_must_be_listed_in_its_span() -> None:
    """A segment whose span does not list it fails with CORRIDOR-SPAN."""
    span = _network().spans[0].model_copy(update={"segment_ids": ["s1"]})
    network = _network().model_copy(update={"spans": [span]})
    report = validate_corridor_network(network)
    assert any(message.startswith("CORRIDOR-SPAN") for message in report.errors)


def test_span_sequence_must_be_contiguous() -> None:
    """A gap in a span's sequence fails with CORRIDOR-SEQUENCE."""
    network = _with_segment(_network(), 1, sequence=2)
    report = validate_corridor_network(network)
    assert any(message.startswith("CORRIDOR-SEQUENCE") for message in report.errors)


def test_span_duplicate_and_unknown_segments_are_named() -> None:
    """A span with a duplicate or an unknown segment fails."""
    duplicate = _network().spans[0].model_copy(update={"segment_ids": ["s1", "s1"]})
    unknown = _network().spans[0].model_copy(update={"segment_ids": ["s1", "s9"]})
    for span in (duplicate, unknown):
        network = _network().model_copy(update={"spans": [span]})
        report = validate_corridor_network(network)
        assert report.errors


def test_span_access_points_are_checked() -> None:
    """A span with an unknown access point fails with CORRIDOR-ACCESS."""
    span = _network().spans[0].model_copy(update={"access_point_ids": ["ap9"]})
    network = _network().model_copy(update={"spans": [span]})
    report = validate_corridor_network(network)
    assert any(message.startswith("CORRIDOR-ACCESS") for message in report.errors)


def test_treatment_unit_contract_window_is_ordered() -> None:
    """A treatment unit that ends before it starts fails."""
    unit = (
        _network()
        .treatment_units[0]
        .model_copy(update={"contract_start_year": 2031, "contract_end_year": 2027})
    )
    network = _network().model_copy(update={"treatment_units": [unit]})
    report = validate_corridor_network(network)
    assert any(message.startswith("CORRIDOR-TU") for message in report.errors)


def test_treatment_unit_unknown_and_duplicate_segments_are_named() -> None:
    """A treatment unit with an unknown or duplicate segment fails."""
    duplicate = _network().treatment_units[0].model_copy(update={"segment_ids": ["s1", "s1"]})
    unknown = _network().treatment_units[0].model_copy(update={"segment_ids": ["s1", "s9"]})
    for unit in (duplicate, unknown):
        network = _network().model_copy(update={"treatment_units": [unit]})
        report = validate_corridor_network(network)
        assert any(message.startswith("CORRIDOR-") for message in report.errors)


def test_segment_in_more_than_one_treatment_unit_is_named() -> None:
    """A segment listed in two treatment units fails."""
    first = _network().treatment_units[0]
    second = TreatmentUnit(
        treatment_unit_id="tu2",
        corridor_id="c1",
        segment_ids=["s1"],
        contract_start_year=2027,
        contract_end_year=2031,
    )
    network = _network().model_copy(update={"treatment_units": [first, second]})
    report = validate_corridor_network(network)
    assert any("more than one treatment unit" in message for message in report.errors)


def test_segment_must_be_listed_in_its_treatment_unit() -> None:
    """A segment missing from its named treatment unit fails."""
    unit = _network().treatment_units[0].model_copy(update={"segment_ids": ["s1"]})
    network = _network().model_copy(update={"treatment_units": [unit]})
    report = validate_corridor_network(network)
    assert any("not listed" in message for message in report.errors)


def test_access_point_corridor_is_checked() -> None:
    """An access point with an unknown corridor fails."""
    access = _network().access_points[0].model_copy(update={"corridor_id": "c9"})
    network = _network().model_copy(update={"access_points": [access]})
    report = validate_corridor_network(network)
    assert any(message.startswith("CORRIDOR-REF") for message in report.errors)


def test_structure_links_are_checked() -> None:
    """An unknown structure corridor or segment fails."""
    bad_corridor = _network().structures[0].model_copy(update={"corridor_id": "c9"})
    bad_segment = _network().structures[0].model_copy(update={"segment_id": "s9"})
    for structure in (bad_corridor, bad_segment):
        network = _network().model_copy(update={"structures": [structure]})
        report = validate_corridor_network(network)
        assert report.errors


def test_length_conservation_is_checked() -> None:
    """A corridor length that differs from the segment sum fails."""
    corridor = _network().corridors[0].model_copy(update={"length_m": 99.0})
    network = _network().model_copy(update={"corridors": [corridor]})
    report = validate_corridor_network(network)
    assert any(message.startswith("CORRIDOR-LENGTH") for message in report.errors)


def test_missing_access_point_is_a_warning() -> None:
    """A segment without an access point is valid but warned."""
    network = _with_segment(_network(), 0, access_point_id=None)
    report = validate_corridor_network(network)
    assert report.is_valid
    assert any(message.startswith("CORRIDOR-ACCESS") for message in report.warnings)


def test_invalid_segment_geometry_is_rejected() -> None:
    """A segment geometry must be a line."""
    with pytest.raises(ValidationError):
        Segment(
            segment_id="s1",
            corridor_id="c1",
            span_id="sp1",
            treatment_unit_id="tu1",
            sequence=0,
            length_m=10.0,
            geometry_wkt="POINT (0 0)",
            service_standard_id="std1",
        )


def test_invalid_access_geometry_is_rejected() -> None:
    """An access point geometry must be a point."""
    with pytest.raises(ValidationError):
        AccessPoint(
            access_point_id="ap1",
            corridor_id="c1",
            kind="road",
            location_wkt="LINESTRING (0 0, 1 1)",
        )


def test_negative_clearance_is_rejected() -> None:
    """A structure clearance must be non-negative."""
    with pytest.raises(ValidationError):
        Structure(
            structure_id="st1",
            corridor_id="c1",
            segment_id="s1",
            structure_type="tower",
            clearance_m=-1.0,
        )


def test_negative_length_is_rejected() -> None:
    """A segment length must be positive."""
    with pytest.raises(ValidationError):
        Segment(
            segment_id="s1",
            corridor_id="c1",
            span_id="sp1",
            treatment_unit_id="tu1",
            sequence=0,
            length_m=0.0,
            geometry_wkt="LINESTRING (0 0, 1 0)",
            service_standard_id="std1",
        )


def test_empty_crs_is_rejected() -> None:
    """The root CRS must not be empty."""
    payload = _network().model_dump()
    payload["crs"] = ""
    with pytest.raises(ValidationError):
        CorridorNetwork.model_validate(payload)


def test_non_positive_service_standard_is_rejected() -> None:
    """A service standard must have a positive height limit."""
    with pytest.raises(ValidationError):
        ServiceStandard(
            service_standard_id="std1",
            max_height_m=0.0,
            min_clearance_m=6.0,
        )

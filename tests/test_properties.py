"""Property tests: invariants that must hold for every generated input.

Hypothesis generates valid roadmaps, control-character injections, and changelog date
sequences. The properties state what the validator must do for all of them, which the
hand-written examples in ``test_check_workflow.py`` cannot cover.
"""

from __future__ import annotations

import datetime as dt
from typing import Final

import pytest
from brushline.model.archive import (
    ArchiveMember,
    Objective,
    ParetoArchive,
    Scalarization,
    dominates,
    validate_pareto_archive,
)
from brushline.model.corridor import (
    AccessPoint,
    Corridor,
    CorridorNetwork,
    Segment,
    ServiceStandard,
    Span,
    TreatmentUnit,
    validate_corridor_network,
)
from brushline.model.state import VegetationState
from brushline.model.validation import check_duplicates
from brushline.sim.schedule import ScheduleRow
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

import check_workflow as cw

CONTROL_CHARACTERS: Final[tuple[str, ...]] = tuple(
    chr(code) for code in (*range(0, 9), 11, 12, *range(14, 32), 127)
)


@st.composite
def valid_roadmaps(draw: st.DrawFn) -> str:
    """Draw the text of a roadmap that satisfies every roadmap rule.

    Parameters
    ----------
    draw : st.DrawFn
        Hypothesis draw function.

    Returns
    -------
    str
        A roadmap with a consistent tracker map and phase sections.
    """
    phase_count = draw(st.integers(min_value=1, max_value=4))
    tracker = [
        "## Issue Tracker Map",
        "",
        "| Phase | Parent issue | Branch | Status |",
        "| --- | --- | --- | --- |",
    ]
    sections: list[str] = []
    for number in range(phase_count):
        status = draw(st.sampled_from(cw.PHASE_STATUSES))
        if status in cw.OPEN_STATUSES:
            parent = f"#{draw(st.integers(min_value=1, max_value=999))}"
        else:
            parent = draw(st.sampled_from(["TBD", "#42"]))
        branch = f"feature/p{number}-phase-{number}"
        tracker.append(f"| P{number} Phase {number} | {parent} | `{branch}` | {status} |")
        low = 1 if status == "complete" else 0
        task_count = draw(st.integers(min_value=low, max_value=3))
        lines = [
            f"## Phase {number}: Phase {number}",
            "",
            f"Parent issue: {parent}",
            f"Branch: `{branch}`",
            f"Status: {status}",
            "",
        ]
        for task_number in range(1, task_count + 1):
            checked = status == "complete" or draw(st.booleans())
            box = "x" if checked else " "
            lines.append(f"- [{box}] P{number}.{task_number} Task {task_number}")
            if draw(st.booleans()):
                sub_box = "x" if status == "complete" or draw(st.booleans()) else " "
                lines.append(f"  - [{sub_box}] A subtask of P{number}.{task_number}")
        lines.append("")
        sections.append("\n".join(lines))
    head = ["# Generated Roadmap", "", *tracker, ""]
    return "\n".join(head) + "\n" + "\n".join(sections)


@settings(max_examples=60, deadline=None)
@given(text=valid_roadmaps())
def test_generated_valid_roadmaps_have_no_findings(text: str) -> None:
    """Every roadmap that follows the grammar passes the roadmap checks with no findings."""
    assert cw.check_roadmap("ROADMAP.md", text) == []


@settings(max_examples=60, deadline=None)
@given(data=st.data())
def test_injected_control_characters_are_always_found(data: st.DataObject) -> None:
    """A control character anywhere in a valid roadmap produces a CONTROL-CHAR finding."""
    text = data.draw(valid_roadmaps())
    position = data.draw(st.integers(min_value=0, max_value=len(text)))
    character = data.draw(st.sampled_from(CONTROL_CHARACTERS))
    corrupted = text[:position] + character + text[position:]
    codes = {d.code for d in cw.scan_text("ROADMAP.md", corrupted.encode("utf-8"))}
    assert "CONTROL-CHAR" in codes


@settings(max_examples=60, deadline=None)
@given(
    dates=st.lists(
        st.dates(min_value=dt.date(2020, 1, 1), max_value=dt.date(2030, 12, 31)),
        min_size=1,
        max_size=6,
    )
)
def test_changelog_order_matches_the_dates(dates: list[dt.date]) -> None:
    """The changelog is flagged for ordering exactly when its dates are not sorted."""
    body = "".join(f"## {day.isoformat()}\n\n- Entry.\n\n" for day in dates)
    diags = cw.check_changelog("CHANGE_LOG.md", "# Change Log\n\n" + body)
    codes = {d.code for d in diags}
    assert ("CHANGELOG-ORDER" in codes) == (dates != sorted(dates))
    assert "CHANGELOG-DATE" not in codes
    assert "CHANGELOG-EMPTY" not in codes


FINITE_FLOATS: Final[st.SearchStrategy[float]] = st.floats(
    min_value=-100.0,
    max_value=100.0,
    allow_nan=False,
    allow_infinity=False,
)
NON_NEGATIVE_FLOATS: Final[st.SearchStrategy[float]] = st.floats(
    min_value=0.0,
    max_value=5.0,
    allow_nan=False,
    allow_infinity=False,
)


def _state(**updates: object) -> VegetationState:
    values: dict[str, object] = {
        "segment_id": "s1",
        "state_year": 2026,
        "functional_group": "shrub",
        "state_class": "shrub",
        "height_m": 2.0,
        "cover_pct": 50.0,
        "source": "synthetic",
        "source_version": "1.0",
    }
    values.update(updates)
    return VegetationState.model_validate(values)


def _member(plan_id: str, values: list[float]) -> ArchiveMember:
    return ArchiveMember(
        plan_id=plan_id,
        plan_path=f"plans/{plan_id}.json",
        objective={f"o{index}": value for index, value in enumerate(values)},
        feasible=True,
        seed=1,
        evidence_path=f"evidence/{plan_id}.json",
    )


def _corridor_network(lengths: list[float], declared_length: float) -> CorridorNetwork:
    segments = [
        Segment(
            segment_id=f"s{index}",
            corridor_id="c1",
            span_id="sp1",
            treatment_unit_id="tu1",
            sequence=index,
            length_m=length,
            geometry_wkt="LINESTRING (0 0, 1 0)",
            service_standard_id="std1",
            access_point_id="ap1",
        )
        for index, length in enumerate(lengths)
    ]
    return CorridorNetwork(
        crs="EPSG:3005",
        corridors=[
            Corridor(
                corridor_id="c1",
                name="Property corridor",
                asset_type="transmission",
                length_m=declared_length,
                crs="EPSG:3005",
            )
        ],
        segments=segments,
        spans=[
            Span(
                span_id="sp1",
                corridor_id="c1",
                segment_ids=[segment.segment_id for segment in segments],
                access_point_ids=["ap1"],
            )
        ],
        treatment_units=[
            TreatmentUnit(
                treatment_unit_id="tu1",
                corridor_id="c1",
                segment_ids=[segment.segment_id for segment in segments],
                contract_start_year=2026,
                contract_end_year=2030,
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
        service_standards=[
            ServiceStandard(
                service_standard_id="std1",
                max_height_m=3.0,
                min_clearance_m=6.0,
            )
        ],
    )


@settings(max_examples=50, deadline=None)
@given(values=st.lists(st.from_regex(r"[a-z]{1,5}", fullmatch=True), max_size=12))
def test_duplicate_checker_finds_exactly_the_duplicates(values: list[str]) -> None:
    """The duplicate checker reports one named error per duplicated value."""
    errors: list[str] = []
    check_duplicates("TEST", "item", values, errors)
    expected = sorted({value for value in values if values.count(value) > 1})
    assert len(errors) == len(expected)
    assert all(message.startswith("TEST-ID") for message in errors)


@settings(max_examples=40, deadline=None)
@given(
    left=st.lists(FINITE_FLOATS, min_size=1, max_size=4),
    right=st.lists(FINITE_FLOATS, min_size=1, max_size=4),
)
def test_dominance_is_irreflexive_and_asymmetric(
    left: list[float],
    right: list[float],
) -> None:
    """No member dominates itself, and two members cannot dominate each other."""
    size = min(len(left), len(right))
    left = left[:size]
    right = right[:size]
    objectives = [
        Objective(name=f"o{index}", direction="minimize", unit="u") for index in range(size)
    ]
    left_member = _member("left", left)
    right_member = _member("right", right)
    assert not dominates(left_member, left_member, objectives)
    if dominates(left_member, right_member, objectives):
        assert not dominates(right_member, left_member, objectives)


@settings(max_examples=30, deadline=None)
@given(
    base=st.lists(FINITE_FLOATS, min_size=1, max_size=4),
    deltas=st.lists(
        st.floats(
            min_value=0.01,
            max_value=5.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        min_size=1,
        max_size=4,
    ),
)
def test_archive_rejects_a_dominated_member(
    base: list[float],
    deltas: list[float],
) -> None:
    """A member that is worse on every objective and strict on one is rejected."""
    size = min(len(base), len(deltas))
    base = base[:size]
    deltas = deltas[:size]
    assume(any(delta > 0 for delta in deltas))
    objectives = [
        Objective(name=f"o{index}", direction="minimize", unit="u") for index in range(size)
    ]
    dominated_values = [base[index] + deltas[index] for index in range(size)]
    assume(any(dominated_values[index] > base[index] for index in range(size)))
    archive = ParetoArchive(
        instance_id="property",
        run_id="run",
        objectives=objectives,
        scalarizations=[
            Scalarization(
                scalarization_id="first",
                weights={f"o{index}": 1.0 if index == 0 else 0.0 for index in range(size)},
            )
        ],
        members=[_member("left", base), _member("right", dominated_values)],
        eviction="crowding-distance",
        created_utc=dt.datetime(2026, 11, 14, tzinfo=dt.UTC),
        created_by="tests",
    )
    report = validate_pareto_archive(archive)
    assert any(message.startswith("PARETO-DOMINANCE") for message in report.errors)


@settings(max_examples=30, deadline=None)
@given(
    lengths=st.lists(
        st.floats(min_value=1.0, max_value=50.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=4,
    ),
    extra=st.floats(min_value=-4.0, max_value=4.0, allow_nan=False, allow_infinity=False),
)
def test_corridor_length_conservation_is_exact(
    lengths: list[float],
    extra: float,
) -> None:
    """A declared corridor length is accepted only within the tolerance."""
    assume(abs(extra) < 0.005 or abs(extra) > 0.02)
    declared = sum(lengths) + extra
    assume(declared > 0.1)
    report = validate_corridor_network(_corridor_network(lengths, declared))
    has_error = any(message.startswith("CORRIDOR-LENGTH") for message in report.errors)
    assert has_error == (abs(extra) > 0.005)


@settings(max_examples=40, deadline=None)
@given(cover=st.floats(min_value=100.001, max_value=500.0, allow_nan=False, allow_infinity=False))
def test_state_cover_above_100_is_rejected(cover: float) -> None:
    """A cover above 100 percent is rejected for every generated value."""
    with pytest.raises(ValidationError):
        _state(cover_pct=cover)


@settings(max_examples=40, deadline=None)
@given(height=st.floats(min_value=-500.0, max_value=-0.001, allow_nan=False, allow_infinity=False))
def test_state_negative_height_is_rejected(height: float) -> None:
    """A negative height is rejected for every generated value."""
    with pytest.raises(ValidationError):
        _state(height_m=height)


@settings(max_examples=40, deadline=None)
@given(efficacy=st.floats(min_value=1.001, max_value=10.0, allow_nan=False, allow_infinity=False))
def test_schedule_efficacy_above_one_is_rejected(efficacy: float) -> None:
    """A schedule efficacy above 1 is rejected for every generated value."""
    with pytest.raises(ValidationError):
        ScheduleRow(
            segment_id="s1",
            year=2026,
            action_id="a1",
            method="mowing",
            intensity=0.5,
            efficacy=efficacy,
            cost=100.0,
        )

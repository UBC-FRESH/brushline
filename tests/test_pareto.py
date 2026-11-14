"""Tests for the P5.5 multi-objective archive and promotion."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from brushline.model.archive import Scalarization, validate_pareto_archive
from brushline.optimization.adapter import ADAPTER_NAME, SearchRun
from brushline.optimization.pareto import (
    ARCHIVE_OBJECTIVES,
    ArchiveConfig,
    ArchiveError,
    ArchiveResult,
    PromotionRecord,
    archive_scalarizations,
    build_archive,
    load_pareto_archive,
    load_promotion,
    promote_member,
    write_pareto_archive,
    write_promotion,
)
from pydantic import ValidationError

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _run(
    vector: tuple[float, float, float, float],
    *,
    seed: int = 1,
    scalarization: str = "balanced",
    feasible: bool = True,
    instance: str = "tiny",
) -> SearchRun:
    objective = {
        "present_cost": vector[0],
        "service_risk": vector[1],
        "service_attainment": vector[2],
        "uncertainty": vector[3],
    }
    return SearchRun(
        mode="local",
        instance_id=instance,
        adapter=ADAPTER_NAME,
        fresh_solutions_version="0.9.3",
        seed=seed,
        budget=10,
        assignment={0: 0},
        objective=1.0,
        objective_vector=objective,
        feasible=feasible,
        evaluations=1,
        history=[1.0],
        stop_reason="budget",
        evidence={
            "metadata": {"scalarization": scalarization},
            "objective": 1.0,
            "feasible": feasible,
        },
        replay_ok=True,
    )


def _archive(
    runs: list[SearchRun],
    config: ArchiveConfig | None = None,
    scalarizations: list[Scalarization] | None = None,
) -> ArchiveResult:
    return build_archive(
        runs,
        instance_id="tiny",
        run_id="run-1",
        config=config,
        scalarizations=scalarizations,
        created_utc=NOW,
    )


def test_archive_keeps_only_non_dominated_feasible_members() -> None:
    """Dominated, duplicate, and infeasible runs are excluded."""
    a = _run((100, 0.2, 0.8, 0.3), seed=1, scalarization="cost_first")
    b = _run((120, 0.1, 0.9, 0.2), seed=2, scalarization="risk_first")
    c = _run((90, 0.4, 0.9, 0.5), seed=3, scalarization="service_first")
    dominated = _run((110, 0.3, 0.7, 0.4), seed=4)
    duplicate = _run((100, 0.2, 0.8, 0.3), seed=5)
    infeasible = _run((1, 0.0, 1.0, 0.0), seed=6, feasible=False)
    result = _archive([a, b, c, dominated, duplicate, infeasible])
    assert {member.plan_id for member in result.archive.members} == {
        "local-cost_first-1-000",
        "local-risk_first-2-001",
        "local-service_first-3-002",
    }
    assert result.duplicates
    assert result.rejected_infeasible
    assert validate_pareto_archive(result.archive).is_valid
    assert len(result.archive.scalarizations) == 5
    assert result.archive.run_id == "run-1"
    assert result.archive.objectives == list(ARCHIVE_OBJECTIVES)
    assert all("crowding_distance" in member.metadata for member in result.archive.members)


def test_diversity_cap_is_deterministic() -> None:
    """The size cap keeps the least crowded members deterministically."""
    runs = [
        _run((100, 0.5, 0.5, 0.5), seed=1),
        _run((110, 0.4, 0.6, 0.4), seed=2),
        _run((120, 0.3, 0.7, 0.3), seed=3),
        _run((130, 0.2, 0.8, 0.2), seed=4),
    ]
    config = ArchiveConfig(max_size=2)
    first = _archive(runs, config=config)
    second = _archive(runs, config=config)
    assert len(first.archive.members) == 2
    assert [member.plan_id for member in first.archive.members] == [
        member.plan_id for member in second.archive.members
    ]
    assert len(first.evicted) == 2
    assert first.crowding == second.crowding
    assert first.archive.eviction == "crowding-distance-v1"


def test_empty_archive_and_mixed_instances() -> None:
    """An all-infeasible input is a valid empty archive; mixed instances fail."""
    empty = _archive([_run((1, 0, 1, 0), feasible=False)])
    assert empty.archive.members == []
    assert validate_pareto_archive(empty.archive).warnings != ()
    with pytest.raises(ArchiveError, match="one instance"):
        build_archive([_run((1, 0, 1, 0)), _run((2, 0, 1, 0), instance="other")])
    with pytest.raises(ArchiveError, match="at least one"):
        build_archive([])
    with pytest.raises(ValidationError):
        ArchiveConfig(max_size=0)


def test_write_load_and_promotion(tmp_path: Path) -> None:
    """The archive and promotion records round-trip and validate."""
    result = _archive([_run((100, 0.2, 0.8, 0.3))])
    path = tmp_path / "pareto.json"
    assert write_pareto_archive(result.archive, path) == path
    loaded = load_pareto_archive(path)
    assert loaded == result.archive
    member = result.archive.members[0]
    promotion = promote_member(
        loaded,
        member.plan_id,
        "best balanced trade-off",
        parent_plan_id="plan-prev",
        created_utc=NOW,
    )
    assert promotion.plan_id == member.plan_id
    assert promotion.parent_plan_id == "plan-prev"
    promotion_path = tmp_path / "promotion.json"
    assert write_promotion(promotion, promotion_path) == promotion_path
    assert load_promotion(promotion_path) == promotion
    with pytest.raises(ArchiveError, match="not in the archive"):
        promote_member(loaded, "missing", "no", created_utc=NOW)
    with pytest.raises(ValidationError):
        PromotionRecord(
            promotion_id="p",
            plan_id="same",
            parent_plan_id="same",
            reason="bad",
            objective=member.objective,
            created_utc=NOW,
            created_by="test",
        )
    with pytest.raises(ValidationError):
        PromotionRecord(
            promotion_id="p",
            plan_id="x",
            reason="bad",
            objective=member.objective,
            created_utc=datetime(2026, 11, 14),
            created_by="test",
        )


def test_invalid_archive_cannot_be_written(tmp_path: Path) -> None:
    """A dominated archive is rejected by the writer."""
    result = _archive(
        [
            _run((100, 0.2, 0.8, 0.3), seed=1),
            _run((110, 0.3, 0.7, 0.4), seed=2),
        ]
    )
    assert len(result.archive.members) == 1
    valid = result.archive
    dominated = valid.members[0].model_copy(update={"plan_id": "dominated"})
    # A duplicate objective is not dominated, but a missing objective is invalid.
    missing = dominated.model_copy(update={"objective": {"present_cost": 1.0}})
    bad = valid.model_copy(update={"members": [valid.members[0], missing]})
    with pytest.raises(ArchiveError):
        write_pareto_archive(bad, tmp_path / "bad.json")


def test_archive_scalarizations_sum_to_one() -> None:
    """The archive portfolio carries the adapter weights."""
    scalarizations = archive_scalarizations()
    assert {item.scalarization_id for item in scalarizations} == {
        "cost_first",
        "risk_first",
        "service_first",
        "uncertainty_first",
        "balanced",
    }
    assert all(abs(sum(item.weights.values()) - 1.0) < 1e-9 for item in scalarizations)


def test_archive_scalarization_and_crowding_edges() -> None:
    """Invalid scalarizations and constant objective spans are handled."""
    bad = Scalarization(scalarization_id="bad", weights={"nope": 1.0})
    with pytest.raises(ArchiveError, match="PARETO-SCALARIZATION"):
        _archive([_run((100, 0.2, 0.8, 0.3))], scalarizations=[bad])
    run = _run((100, 0.2, 0.8, 0.3))
    run = run.model_copy(update={"evidence": {"metadata": []}})
    result = _archive([run])
    assert result.archive.members[0].plan_id.startswith("local-unknown-1-")
    same_cost = _archive(
        [
            _run((100, 0.2, 0.8, 0.3), seed=1),
            _run((100, 0.1, 0.7, 0.2), seed=2),
        ]
    )
    assert len(same_cost.archive.members) == 2


def test_promotion_validation_and_invalid_load(tmp_path: Path) -> None:
    """Promotion objectives and loaded archives are validated."""
    from brushline.optimization.pareto import _validate_promotion

    record = PromotionRecord(
        promotion_id="p",
        plan_id="plan",
        reason="test",
        objective={"present_cost": 1.0},
        created_utc=NOW,
        created_by="test",
    )
    assert not _validate_promotion(record).is_valid
    result = _archive([_run((100, 0.2, 0.8, 0.3))])
    path = tmp_path / "pareto.json"
    write_pareto_archive(result.archive, path)
    payload = path.read_text()
    payload = payload.replace('"service_risk": 0.2,', "")
    path.write_text(payload)
    with pytest.raises(ArchiveError, match="PARETO-OBJECTIVE"):
        load_pareto_archive(path)

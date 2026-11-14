from __future__ import annotations

from pathlib import Path

from brushline.operations.governance import (
    audit_dependencies,
    default_governance,
    default_pilot_evidence,
    validate_governance,
    write_operations_json,
)


def test_governance_and_dependency_audit(tmp_path: Path) -> None:
    records = default_governance()
    assert len(records) >= 3
    assert validate_governance(records) == []
    deps = audit_dependencies()
    assert any(row.package == "fresh-solutions" for row in deps)
    assert all(
        row.status in {"current", "missing-optional", "drift", "not-installed"} for row in deps
    )
    pilot = default_pilot_evidence()
    assert pilot.status == "synthetic"
    assert pilot.metrics["optimized_service"] > pilot.metrics["bau_service"]
    path = write_operations_json(tmp_path / "operations.json")
    assert "schema_version" in path.read_text()

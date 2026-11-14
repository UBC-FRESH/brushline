from __future__ import annotations

from pathlib import Path

from brushline.verification.acceptance import (
    build_verification,
    write_report_markdown,
    write_verification,
)


def test_verification_evidence_and_reports(tmp_path: Path) -> None:
    report = build_verification()
    assert len(report.criteria) == 16
    assert {c.status for c in report.criteria} >= {"met", "partial", "not_met"}
    assert report.bau["optimized_service"] >= 0.7
    assert report.monitoring["beats_calendar"]
    assert report.exchange["same_artifact"]
    assert report.reproducible
    assert not report.performance["target_met"]
    assert "not a production" in report.recommendation
    json_path = tmp_path / "verification.json"
    md_path = tmp_path / "verification.md"
    write_verification(report, json_path)
    write_report_markdown(report, md_path)
    assert "P12 verification" in md_path.read_text()
    assert json_path.exists()

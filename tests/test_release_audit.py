"""Tests for the release-boundary audit."""

from __future__ import annotations

from tools.audit_release import audit_release


def test_release_boundary_passes() -> None:
    result = audit_release()
    assert result["schema_version"] == "brushline.release-audit.v1"
    assert result["status"] == "pass"
    assert result["tracked_files"] > 0
    assert {check["name"] for check in result["checks"]} == {
        "private-paths-untracked",
        "gitignore-boundary",
        "no-local-absolute-paths",
        "public-demo-synthetic",
    }
    assert all(check["ok"] for check in result["checks"])

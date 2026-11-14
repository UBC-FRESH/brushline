from __future__ import annotations

from pathlib import Path

from brushline.demo.builder import build_demo_site
from brushline.demo.pilot import default_pilot
from brushline.demo.portfolio import build_portfolio
from brushline.demo.validation import validate_site


def test_portfolio_and_static_site(tmp_path: Path) -> None:
    manifests = build_portfolio()
    assert len(manifests) >= 5
    root = build_demo_site(tmp_path / "site", portfolio=manifests)
    assert (root / "index.html").exists()
    assert (root / "health.json").read_text().find("read_only") >= 0
    assert all((root / "instance" / f"{m.id}.html").exists() for m in manifests)
    assert (root / "pilot.html").exists()
    assert validate_site(root).passed
    assert default_pilot().data_request

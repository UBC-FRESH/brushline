# ruff: noqa: E501
"""Static public demo portal builder."""

from __future__ import annotations

import html
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from brushline.demo.pilot import default_pilot, write_pilot
from brushline.demo.portfolio import build_portfolio
from brushline.model.demo import DemoManifest, validate_demo_manifest

STYLE = """body{font-family:system-ui,sans-serif;max-width:1100px;margin:auto;padding:2rem;color:#183024;background:#f4f7f1}h1{font-size:2rem}a{color:#1c6b45}.card{border:1px solid #ccd9ca;border-radius:10px;padding:1rem;margin:1rem 0;background:#fff}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #e1e9df;padding:.3rem;text-align:left}.caveat{color:#6b4d18;background:#fff7df;padding:.6rem;border-radius:6px}canvas{background:#dfe9df;border-radius:8px;width:100%;max-width:900px}"""


def _artifact(root: Path, name: str) -> dict[str, Any] | None:
    path = root / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _page(manifest: DemoManifest, root: Path) -> str:
    plan = _artifact(root, manifest.artifacts.plan) or {}
    pareto = _artifact(root, manifest.artifacts.pareto or "") or {}
    metrics = "".join(
        f"<li><strong>{html.escape(m.name)}</strong>: {m.value} {html.escape(m.unit)}</li>"
        for m in manifest.headline_metrics
    )
    sources = "".join(
        f"<li>{html.escape(s.name)} — {html.escape(s.licence)} — {html.escape(s.version)}</li>"
        for s in manifest.data_sources
    )
    caveats = "".join(f"<li>{html.escape(c)}</li>" for c in manifest.caveats)
    actions = "".join(
        f"<tr><td>{html.escape(a['segment_id'])}</td><td>{html.escape(a['method'])}</td><td>{a['year']}</td><td>{sum(x['amount'] for x in a['cost_lines'])}</td></tr>"
        for a in plan.get("actions", [])
    )
    members = "".join(
        f"<tr><td>{html.escape(m['plan_id'])}</td><td>{m['objective'].get('present_cost')}</td><td>{m['objective'].get('service_risk')}</td></tr>"
        for m in pareto.get("members", [])
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(manifest.title)}</title><link rel="stylesheet" href="../style.css"></head><body>
<p><a href="../index.html">Brushline demo portfolio</a></p><h1>{html.escape(manifest.title)}</h1><p>{html.escape(manifest.question)}</p>
<div class="card"><h2>What this shows</h2><ul>{metrics}</ul><p><strong>Region:</strong> {html.escape(manifest.region)} · <strong>Sector:</strong> {html.escape(manifest.sector)}</p></div>
<div class="card"><h2>2D corridor</h2><svg width="800" height="140" viewBox="0 0 800 140"><line x1="20" y1="70" x2="780" y2="70" stroke="#48735a" stroke-width="8"/>{"".join(f'<circle cx="{60 + i * 130}" cy="70" r="18" fill="#7ca786"><title>{html.escape(a["segment_id"])}</title></circle>' for i, a in enumerate(plan.get("actions", [])))}</svg></div>
<div class="card"><h2>3D context</h2><canvas id="demo-scene" width="800" height="220"></canvas><p class="caveat">Context view only. This public demo uses synthetic geometry and does not imply survey precision.</p><button id="variant">Pre / Post</button></div>
<div class="card"><h2>Plan actions</h2><table><tr><th>Segment</th><th>Method</th><th>Year</th><th>Cost</th></tr>{actions}</table></div>
<div class="card"><h2>Pareto explorer</h2><table><tr><th>Plan</th><th>Cost</th><th>Risk</th></tr>{members}</table></div>
<div class="card"><h2>What this does not show</h2><ul>{caveats}</ul><h2>Sources and licences</h2><ul>{sources}</ul><p><a href="../pilot.html">Request a pilot</a></p></div>
<script src="../demo.js"></script></body></html>"""


DEMO_JS = """const canvas=document.getElementById('demo-scene');if(canvas){const c=canvas.getContext('2d');let post=false;function draw(){c.fillStyle='#dfe9df';c.fillRect(0,0,800,220);for(let i=0;i<5;i++){let h=post?35+i*8:70+i*14;c.fillStyle=post?'#b67b4a':'#3d7a4f';c.fillRect(80+i*140,190-h,60,h)}}document.getElementById('variant').onclick=()=>{post=!post;draw()};draw()}"""


def build_demo_site(
    out_dir: str | Path,
    *,
    artifact_root: str | Path | None = None,
    portfolio: list[DemoManifest] | None = None,
    created_utc: datetime | None = None,
) -> Path:
    """Build the static public portal and return its root."""
    root = Path(
        artifact_root or Path(__file__).resolve().parents[2] / "examples" / "synthetic-corridor"
    )
    destination = Path(out_dir)
    if destination.exists():
        shutil.rmtree(destination)
    (destination / "instance").mkdir(parents=True)
    manifests = portfolio or build_portfolio(created_utc)
    for manifest in manifests:
        validation = validate_demo_manifest(manifest)
        if not validation.is_valid:
            raise ValueError("; ".join(validation.errors))
        (destination / "instance" / f"{manifest.id}.html").write_text(
            _page(manifest, root), encoding="utf-8"
        )
    cards = "".join(
        f'<div class="card"><h2><a href="instance/{m.id}.html">{html.escape(m.title)}</a></h2>'
        f"<p>{html.escape(m.question)}</p><p>{m.headline_metrics[0].name}: {m.headline_metrics[0].value} "
        f"{html.escape(m.headline_metrics[0].unit)}</p></div>"
        for m in manifests
    )
    (destination / "index.html").write_text(
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Brushline demos</title><link rel="stylesheet" href="style.css"></head><body><h1>Brushline public demos</h1><p>Read-only public-data examples. Synthetic evidence is labelled.</p>{cards}<p><a href="pilot.html">Request a pilot</a></p></body></html>',
        encoding="utf-8",
    )
    (destination / "style.css").write_text(STYLE, encoding="utf-8")
    (destination / "demo.js").write_text(DEMO_JS, encoding="utf-8")
    write_pilot(default_pilot(), destination / "pilot.html")
    (destination / "portfolio.json").write_text(
        json.dumps([m.model_dump(mode="json") for m in manifests], indent=2) + "\n",
        encoding="utf-8",
    )
    (destination / "health.json").write_text(
        json.dumps({"status": "ok", "read_only": True, "demos": len(manifests)}) + "\n",
        encoding="utf-8",
    )
    return destination

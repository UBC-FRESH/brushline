"""Generate a self-contained planning brief from network model artifacts.

The brief is a decision record, not a replacement for the underlying plans. It packages the
selected frontier point, tactical schedule, workforce scenarios, commercial check, uncertainty
bands, scenario comparison, provenance, and caveats into one offline-readable document.
"""

from __future__ import annotations

import html as html_module
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PLANNING_BRIEF_SCHEMA_VERSION: Literal["brushline.planning-brief.v1"] = (
    "brushline.planning-brief.v1"
)


class PlanningBriefError(ValueError):
    """Raised when planning-brief inputs are missing or inconsistent."""


class BriefTable(BaseModel):
    """A rendered table in a planning brief."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    columns: list[str]
    rows: list[list[str]]
    note: str | None = None


class BriefSection(BaseModel):
    """One section of a planning brief."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    heading: str
    paragraphs: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    table: BriefTable | None = None


class PlanningBrief(BaseModel):
    """Self-contained Markdown and HTML planning brief."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.planning-brief.v1"] = PLANNING_BRIEF_SCHEMA_VERSION
    instance_id: str
    title: str
    generated_utc: datetime
    command: str
    commit: str
    markdown: str
    html: str
    filename_markdown: str
    filename_html: str

    @model_validator(mode="after")
    def _time(self) -> PlanningBrief:
        if self.generated_utc.tzinfo is None:
            raise ValueError("generated_utc must be timezone-aware")
        return self


def _text(value: Any, default: str = "n/a") -> str:  # noqa: ANN401
    if value is None or value == "":
        return default
    return str(value)


def _number(value: Any, digits: int = 0) -> str:  # noqa: ANN401
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{number:,.{digits}f}"


def _percent(value: Any, digits: int = 1) -> str:  # noqa: ANN401
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{number * 100:.{digits}f}%"


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "planning-brief"


def _table(
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
    *,
    note: str | None = None,
) -> BriefTable:
    return BriefTable(
        columns=[str(column) for column in columns],
        rows=[[_text(cell) for cell in row] for row in rows],
        note=note,
    )


def _markdown_section(section: BriefSection) -> list[str]:
    lines = [f"## {section.heading}", ""]
    lines.extend(f"{paragraph}\n" for paragraph in section.paragraphs)
    for bullet in section.bullets:
        lines.append(f"- {bullet}")
    if section.bullets:
        lines.append("")
    table = section.table
    if table is not None:
        header = "| " + " | ".join(_md_cell(column) for column in table.columns) + " |"
        divider = "|" + "|".join("---" for _ in table.columns) + "|"
        lines.extend([header, divider])
        for row in table.rows:
            lines.append("| " + " | ".join(_md_cell(cell) for cell in row) + " |")
        if table.note:
            lines.extend(["", table.note])
        lines.append("")
    return lines


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_markdown(
    *,
    title: str,
    instance_id: str,
    generated_utc: datetime,
    command: str,
    commit: str,
    sections: Sequence[BriefSection],
) -> str:
    """Render a planning brief as GitHub-flavoured Markdown."""
    lines = [
        f"# {title}",
        "",
        f"Instance: `{instance_id}`",
        f"Generated: {generated_utc.isoformat()}",
        f"Command: `{command}`",
        f"Commit: `{commit}`",
        "",
        "> Prototype planning record. Not an asset-owner plan, a safety certification, or a",
        "> field-calibrated forecast.",
        "",
    ]
    for section in sections:
        lines.extend(_markdown_section(section))
    return "\n".join(lines).rstrip() + "\n"


def render_html(
    *,
    title: str,
    instance_id: str,
    generated_utc: datetime,
    command: str,
    commit: str,
    sections: Sequence[BriefSection],
) -> str:
    """Render a self-contained, print-friendly HTML planning brief."""
    body: list[str] = []
    for section in sections:
        body.append(f"<section><h2>{_e(section.heading)}</h2>")
        body.extend(f"<p>{_e(paragraph)}</p>" for paragraph in section.paragraphs)
        if section.bullets:
            body.append("<ul>")
            body.extend(f"<li>{_e(bullet)}</li>" for bullet in section.bullets)
            body.append("</ul>")
        table = section.table
        if table is not None:
            body.append("<table><thead><tr>")
            body.extend(f"<th>{_e(column)}</th>" for column in table.columns)
            body.append("</tr></thead><tbody>")
            for row in table.rows:
                body.append("<tr>")
                body.extend(f"<td>{_e(cell)}</td>" for cell in row)
                body.append("</tr>")
            body.append("</tbody></table>")
            if table.note:
                body.append(f'<p class="note">{_e(table.note)}</p>')
        body.append("</section>")
    meta = f"Generated {generated_utc.isoformat()} · Instance {instance_id} · Commit {commit}"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)}</title>
<style>
:root {{ color-scheme: light; --ink: #1f2b27; --muted: #5e6f68; --line: #d7dfda;
  --paper: #fbfcfb; --accent: #315c49; --warm: #f4eee2; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--paper); color: var(--ink);
  font: 16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }}
header {{ background: var(--warm); border-bottom: 1px solid var(--line);
  padding: 2.4rem 1.4rem 1.8rem; }}
main {{ max-width: 1120px; margin: 0 auto; padding: 1.4rem; }}
.eyebrow {{ margin: 0 0 .4rem; color: var(--accent); font-size: .78rem;
  font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }}
h1 {{ margin: 0; max-width: 900px; font-size: clamp(1.9rem, 4vw, 3rem);
  line-height: 1.08; }}
.lede {{ max-width: 860px; margin: .9rem 0 0; color: var(--muted); font-size: 1.05rem; }}
.meta {{ max-width: 1000px; margin: 1rem 0 0; color: var(--muted); font-size: .82rem;
  overflow-wrap: anywhere; }}
h2 {{ margin: 2rem 0 .6rem; padding-bottom: .3rem; border-bottom: 1px solid var(--line);
  color: var(--accent); font-size: 1.3rem; }}
p {{ max-width: 950px; }}
ul {{ max-width: 950px; padding-left: 1.25rem; }}
li {{ margin: .28rem 0; }}
table {{ width: 100%; margin: .8rem 0 .5rem; border-collapse: collapse;
  font-size: .9rem; }}
th, td {{ padding: .5rem .55rem; border-bottom: 1px solid var(--line);
  text-align: left; vertical-align: top; }}
th {{ background: #edf3ef; color: var(--accent); font-size: .78rem;
  letter-spacing: .02em; }}
.note {{ color: var(--muted); font-size: .82rem; }}
footer {{ max-width: 1120px; margin: 0 auto; padding: 1.4rem; color: var(--muted);
  font-size: .82rem; }}
code {{ padding: .1rem .3rem; border-radius: 4px; background: #edf3ef; }}
@media print {{
  body {{ background: white; font-size: 11pt; }}
  header, main, footer {{ max-width: none; padding: .6in; }}
  h2 {{ break-after: avoid; }}
  table {{ break-inside: avoid; }}
}}
</style>
</head>
<body>
<header>
<p class="eyebrow">Brushline planning brief</p>
<h1>{_e(title)}</h1>
<p class="lede">A prototype decision record for a public-data network planning demonstration.
It is a lab review artifact, not an asset-owner plan or safety certification.</p>
<p class="meta">{_e(meta)}</p>
</header>
<main>
{"".join(body)}
</main>
<footer>
<p>Reproduction: <code>{_e(command)}</code> · commit <code>{_e(commit)}</code>.</p>
<p>Network-derived artifacts remain private until data-sharing and release approval.</p>
</footer>
</body>
</html>
"""


def _e(value: str) -> str:
    return html_module.escape(value, quote=True)


def _frontier(
    strategic: Mapping[str, Any],
) -> tuple[list[Mapping[str, Any]], Mapping[str, Any], BriefTable]:
    scenarios = list(strategic.get("milp_scenarios") or [])
    if not scenarios:
        raise PlanningBriefError("strategic artifact has no MILP scenarios")
    selected = next(
        (
            item
            for item in scenarios
            if "60000" in str(item.get("name", ""))
            or _number(item.get("annual_budget")) == "60,000"
        ),
        None,
    )
    if selected is None:
        selected = max(scenarios, key=lambda item: float(item.get("annual_budget", 0)))
    rows: list[list[Any]] = [
        [
            item.get("name"),
            _number(item.get("annual_budget")),
            _number(item.get("five_year_cost")),
            _number(item.get("mean_service"), 3),
            _number(item.get("mean_risk"), 3),
            _number(item.get("mean_annual_hours")),
        ]
        for item in scenarios
    ]
    bau = strategic.get("stateful_bau") or {}
    if bau:
        rows.append(
            [
                "BAU five-year mowing",
                "0",
                _number(bau.get("five_year_cost")),
                _number(bau.get("mean_service"), 3),
                _number(bau.get("mean_risk"), 3),
                _number(bau.get("mean_annual_hours")),
            ]
        )
    table = _table(
        ["Scenario", "Budget/yr", "5-year cost", "Mean service", "Mean risk", "Hours/yr"],
        rows,
    )
    return [dict(item) for item in scenarios], dict(selected), table


def _method_table(network: Mapping[str, Any]) -> BriefTable:
    assumptions = network.get("assumptions") or {}
    methods = assumptions.get("method_costs") or {}
    rows = []
    for method, params in methods.items():
        rows.append(
            [
                method,
                _number(params.get("cost_ha")),
                _number(params.get("hours_ha")),
                _number(params.get("service_gain"), 2),
                _number(params.get("risk_reduction"), 2),
            ]
        )
    return _table(
        ["Method", "Cost/ha (CAD)", "Hours/ha", "Service gain", "Risk reduction"],
        rows,
    )


def _annual_tactical_table(
    tactical: Mapping[str, Any],
    resources: Mapping[str, Any],
    operations: Mapping[str, Any],
) -> BriefTable:
    actions_by_year: dict[int, int] = {}
    hours_by_year: dict[int, float] = {}
    work_orders_by_year: dict[int, int] = {}
    for action in tactical.get("actions") or []:
        year = int(action.get("year", 0))
        actions_by_year[year] = actions_by_year.get(year, 0) + 1
    for request in resources.get("requests") or []:
        year = int(request.get("year", 0))
        hours_by_year[year] = hours_by_year.get(year, 0.0) + float(
            request.get("capacity_units", 0.0)
        )
    for order in operations.get("work_orders") or []:
        year = int(order.get("year", 0))
        work_orders_by_year[year] = work_orders_by_year.get(year, 0) + 1
    cost_by_year = tactical.get("cost_by_year") or {}
    rows = []
    years = set(actions_by_year) | set(hours_by_year)
    years |= {int(year) for year in cost_by_year}
    for year in sorted(years):
        rows.append(
            [
                year,
                actions_by_year.get(year, 0),
                _number(cost_by_year.get(str(year), cost_by_year.get(year))),
                _number(hours_by_year.get(year)),
                work_orders_by_year.get(year, 0),
            ]
        )
    return _table(
        ["Year", "Actions", "Tactical cost", "Crew-hours requested", "Work orders"],
        rows,
    )


def build_planning_brief(
    *,
    network: Mapping[str, Any],
    strategic: Mapping[str, Any],
    tactical: Mapping[str, Any],
    resources: Mapping[str, Any],
    operations: Mapping[str, Any],
    shifts: Mapping[str, Any],
    workforce: Sequence[Mapping[str, Any]],
    bid: Mapping[str, Any],
    uncertainty: Mapping[str, Any],
    scenario_optimization: Mapping[str, Any],
    access: Mapping[str, Any],
    generated_utc: datetime | None = None,
    command: str = "python tools/build_bc_network_demo.py",
    commit: str = "unknown",
) -> PlanningBrief:
    """Build the planning brief from the network artifact set.

    Parameters
    ----------
    network, strategic, tactical, resources, operations, shifts, bid, uncertainty : mapping
        Loaded model artifacts. ``scenario_optimization`` and ``access`` are also required.
    workforce : sequence of mapping
        Workforce scenario results.
    generated_utc : datetime, optional
        Generation time; defaults to the current UTC time.
    command : str, optional
        Reproduction command.
    commit : str, optional
        Repository commit identifier.

    Returns
    -------
    PlanningBrief
        Markdown and HTML renderings with filenames.

    Raises
    ------
    PlanningBriefError
        If required artifacts or the selected frontier point are missing.
    """
    if not network:
        raise PlanningBriefError("network artifact is empty")
    if not strategic:
        raise PlanningBriefError("strategic artifact is empty")
    if not tactical:
        raise PlanningBriefError("tactical artifact is empty")
    if not bid:
        raise PlanningBriefError("bid artifact is empty")
    if not uncertainty:
        raise PlanningBriefError("uncertainty artifact is empty")
    if not scenario_optimization:
        raise PlanningBriefError("scenario-optimization artifact is empty")
    scenarios, selected, frontier_table = _frontier(strategic)
    instance_id = _text(network.get("instance_id"), "unknown")
    selected_rows = list(selected.get("rows") or [])
    selected_plan = selected.get("plan") or {}
    uncertainty_cost = uncertainty.get("cost_band") or {}
    uncertainty_hours = uncertainty.get("hours_band") or {}
    scenario_fixed = scenario_optimization.get("fixed_cost_band") or {}
    scenario_adaptive = scenario_optimization.get("adaptive_cost_band") or {}
    scenario_fixed_risk = scenario_optimization.get("fixed_risk_band") or {}
    scenario_adaptive_risk = scenario_optimization.get("adaptive_risk_band") or {}
    sources = list(network.get("sources") or [])
    source_rows = [[source.get("name"), source.get("licence")] for source in sources]
    caveats = [
        "Public-data prototype; values are modelled, not surveyed.",
        "Costs, hours, productivity, access, and capacity are explicit demo assumptions.",
        "The MILP is exact for the declared linear risk state, not a full nonlinear "
        "vegetation model.",
        "Scenario-optimized planning is a hindsight upper bound, not an executable "
        "forecast-update policy.",
        "No asset-owner clearance standard, outage constraint, safety certification, or "
        "field calibration is claimed.",
    ]
    for caveat in strategic.get("caveats") or []:
        if caveat not in caveats:
            caveats.append(str(caveat))
    if network.get("assumptions", {}).get("caveat"):
        caveats.insert(0, str(network["assumptions"]["caveat"]))
    title = (
        "BC Hydro public-data network planning brief"
        if instance_id.startswith("bc-hydro-network")
        else f"{instance_id} planning brief"
    )
    selected_name = _text(selected.get("name"), "selected frontier point")
    solver = _text(selected_plan.get("solver"), "MILP")
    status = _text(selected_plan.get("status"), "unknown")
    replay = _text(selected_plan.get("replay_ok"), "unknown")
    scenario_count = len(scenarios)
    annual_table = _annual_tactical_table(tactical, resources, operations)
    workforce_rows = [
        [
            item.get("name"),
            _number(item.get("reassigned_hours")),
            _number(item.get("resource_cost")),
            _text(item.get("resource_feasible")),
            _text(item.get("shift_feasible")),
            item.get("shift_assignments", "n/a"),
        ]
        for item in workforce
    ]
    bid_comparison = bid.get("comparison") or {}
    bid_details = bid.get("bid") or {}
    access_results = list(access.get("results") or [])
    access_allowed = sum(bool(item.get("allowed")) for item in access_results)
    crew_utilization = shifts.get("crew_utilization") or {}
    shift_note = (
        f"{len(shifts.get('assignments') or [])} assignments; "
        f"{_number(shifts.get('total_productive_hours'))} productive hours; "
        f"{_number(shifts.get('total_travel_hours'))} travel hours; feasible: "
        f"{_text(shifts.get('feasible'))}."
    )
    crew_note = ", ".join(f"{name}: {_number(hours)} h" for name, hours in crew_utilization.items())
    sections = [
        BriefSection(
            heading="Decision summary",
            paragraphs=[
                "This brief records the current public-data network prototype and the selected "
                "balanced five-year plan. It is intended for lab review of the planning workflow, "
                "not for field deployment or asset-owner approval.",
            ],
            bullets=[
                f"Area of interest: {_number(network.get('aoi_ha'))} ha; "
                f"{_number(network.get('line_km'), 1)} km of mapped power-line features; "
                f"{len(network.get('lines') or [])} features, "
                f"{len(network.get('units') or [])} management units, "
                f"{len(network.get('segments') or [])} segments.",
                f"Selected frontier point: {selected_name}; five-year cost "
                f"{_number(selected.get('five_year_cost'))} CAD; mean risk "
                f"{_number(selected.get('mean_risk'), 3)}; mean service "
                f"{_number(selected.get('mean_service'), 3)}; "
                f"{_number(selected.get('mean_annual_hours'))} crew-hours/year.",
                f"Execution uncertainty: five-year cost P10-P90 "
                f"{_number(uncertainty_cost.get('p10'))}-"
                f"{_number(uncertainty_cost.get('p90'))} CAD; crew-hours P10-P90 "
                f"{_number(uncertainty_hours.get('p10'))}-"
                f"{_number(uncertainty_hours.get('p90'))}.",
                f"Hindsight adaptive planning improved the normalized objective in "
                f"{_percent(scenario_optimization.get('probability_adaptation_improves'))} of "
                f"{scenario_optimization.get('scenarios')} scenarios; see the caveat below.",
            ],
        ),
        BriefSection(
            heading="Data provenance and scope",
            paragraphs=[
                "The network uses public vector line and tower geometry, public stand inventory "
                "context, and public terrain. Stand condition, treatment response, costs, hours, "
                "and capacity are prototype assumptions layered on those inputs.",
            ],
            bullets=[
                f"Scenario set: {scenario_count} MILP budget points, 2027-2031.",
                f"Access checks: {access_allowed}/{len(access_results)} open; "
                f"{_number(access.get('total_route_m'))} m of modelled route; "
                f"feasible: {_text(access.get('feasible'))}.",
                "Network-derived artifacts remain private until data-sharing and release approval.",
            ],
            table=_table(["Source", "Licence"], source_rows),
        ),
        BriefSection(
            heading="Cost, hours, and risk assumptions",
            paragraphs=[
                "The selected plan is a linear stateful MILP over segment-period-method choices. "
                "The model minimizes residual risk subject to annual budget and crew-hour "
                "capacity; the declared risk state is linear.",
            ],
            bullets=[
                f"Contractor capacity assumptions: "
                f"{network.get('assumptions', {}).get('contractor_capacity')} hours/year.",
                f"Segment length: "
                f"{_number(network.get('assumptions', {}).get('segment_m'), 1)} m; "
                f"horizon: {network.get('assumptions', {}).get('horizon')} years from "
                f"{network.get('assumptions', {}).get('start_year')}.",
            ],
            table=_method_table(network),
        ),
        BriefSection(
            heading="Budget and risk frontier",
            paragraphs=[
                "The frontier places annual budget against modelled five-year cost, service, and "
                "residual risk. The balanced row is selected for the tactical and operational "
                "examples; it is not an asset-owner preferred budget.",
            ],
            table=frontier_table,
        ),
        BriefSection(
            heading="Selected five-year schedule",
            paragraphs=[
                f"The selected plan is {selected_name}, solved by {solver} with status {status} "
                f"and replay {replay}. Annual rows below are the MILP plan's replayed projections."
            ],
            table=_table(
                ["Year", "Cost", "Crew-hours", "Risk", "Service", "Actions"],
                [
                    [
                        row.get("year"),
                        _number(row.get("cost")),
                        _number(row.get("hours")),
                        _number(row.get("risk"), 3),
                        _number(row.get("service"), 3),
                        row.get("actions"),
                    ]
                    for row in selected_rows
                ],
            ),
        ),
        BriefSection(
            heading="Tactical and operational plan",
            paragraphs=[
                f"The tactical program contains {len(tactical.get('actions') or [])} actions and "
                f"{_number(tactical.get('total_cost'))} CAD of treatment cost. The resource plan "
                f"contains {_number(resources.get('total_cost'))} CAD of modelled resource cost "
                f"and is feasible: {_text(resources.get('feasible'))}. The operations plan "
                f"contains {len(operations.get('work_orders') or [])} work orders and is feasible: "
                f"{_text(operations.get('feasible'))}.",
                f"Shift scheduling produced {shift_note} Crew utilization: {crew_note or 'n/a'}.",
            ],
            table=annual_table,
        ),
        BriefSection(
            heading="Workforce scenarios",
            paragraphs=[
                "Workforce scenarios reallocate the same tactical work under current, expanded, "
                "and community-enterprise capacity assumptions. Feasibility is modelled, not a "
                "contractual commitment."
            ],
            table=_table(
                [
                    "Scenario",
                    "Reassigned h",
                    "Resource cost",
                    "Resource feasible",
                    "Shift feasible",
                    "Assignments",
                ],
                workforce_rows,
            ),
        ),
        BriefSection(
            heading="Commercial check",
            paragraphs=[
                "The commercial check compares an owner cost estimate with a mock contractor bid "
                "using explicit labour, equipment, travel, access, and productivity assumptions. "
                "It is a range test, not a procurement recommendation."
            ],
            table=_table(
                ["Item", "Value"],
                [
                    ["Owner plan", f"{_number(bid.get('owner_total'))} CAD"],
                    ["Mock contractor bid", f"{_number(bid_details.get('total_cost'))} CAD"],
                    ["Delta", f"{_number(bid_comparison.get('delta'))} CAD"],
                    [
                        "Fair range",
                        f"{_number(bid_comparison.get('fair_low'))}-"
                        f"{_number(bid_comparison.get('fair_high'))} CAD",
                    ],
                    ["Within fair range", _text(bid_comparison.get("within_fair_range"))],
                ],
                note=" ".join(str(item) for item in bid_details.get("assumptions") or []),
            ),
        ),
        BriefSection(
            heading="Execution uncertainty",
            paragraphs=[
                f"Seeded execution sampling around the selected plan: {uncertainty.get('samples')} "
                "samples. The plan is held fixed; costs, productive hours, and contractor capacity "
                "are varied. This is not an adaptive stochastic program."
            ],
            table=_table(
                ["Metric", "P10", "P50", "P90", "Shortfall probability"],
                [
                    [
                        "5-year total cost",
                        _number(uncertainty_cost.get("p10")),
                        _number(uncertainty_cost.get("p50")),
                        _number(uncertainty_cost.get("p90")),
                        f"{_percent(uncertainty.get('probability_budget_exceeded'))} budget",
                    ],
                    [
                        "5-year crew-hours",
                        _number(uncertainty_hours.get("p10")),
                        _number(uncertainty_hours.get("p50")),
                        _number(uncertainty_hours.get("p90")),
                        f"{_percent(uncertainty.get('probability_capacity_shortfall'))} capacity",
                    ],
                ],
            ),
        ),
        BriefSection(
            heading="Hindsight adaptive planning",
            paragraphs=[
                f"{scenario_optimization.get('scenarios')} exact scenario re-solves. The fixed "
                "plan is the balanced nominal plan; the adaptive policy re-solves with each "
                "scenario's "
                "costs, hours, and capacity. This is a hindsight upper bound, not a deployable "
                "forecast-update policy.",
                f"Risk-equivalent objective: fixed "
                f"{_number(scenario_optimization.get('mean_fixed_objective'), 4)}; adaptive "
                f"{_number(scenario_optimization.get('mean_adaptive_objective'), 4)}; mean regret "
                f"{_number(scenario_optimization.get('mean_regret'), 4)}. The score includes a "
                "normalized budget/capacity penalty for the fixed plan.",
            ],
            table=_table(
                ["Policy", "5-year cost P10-P90", "Mean risk", "Budget violation"],
                [
                    [
                        "Fixed balanced plan",
                        f"{_number(scenario_fixed.get('p10'))}-{_number(scenario_fixed.get('p90'))}",
                        _number(scenario_fixed_risk.get("mean"), 4),
                        _percent(scenario_optimization.get("fixed_budget_violation_probability")),
                    ],
                    [
                        "Scenario-optimized",
                        f"{_number(scenario_adaptive.get('p10'))}-"
                        f"{_number(scenario_adaptive.get('p90'))}",
                        _number(scenario_adaptive_risk.get("mean"), 4),
                        "0.0%",
                    ],
                ],
            ),
        ),
        BriefSection(
            heading="Scaling evidence",
            paragraphs=[
                "The heuristic scaling table records the Fresh Solutions path used beyond the "
                "exact MILP range. Statuses are feasible search states; they are not global "
                "optimality claims."
            ],
            table=_table(
                ["Segments", "Variables", "Seconds", "Mean risk", "Status", "Evaluations"],
                [
                    [
                        item.get("segments"),
                        item.get("variables"),
                        _number(item.get("seconds"), 2),
                        _number(item.get("mean_risk"), 3),
                        item.get("status"),
                        item.get("evaluations"),
                    ]
                    for item in strategic.get("scalability") or []
                ],
            ),
        ),
        BriefSection(
            heading="Caveats",
            bullets=caveats,
        ),
        BriefSection(
            heading="Reproduction",
            paragraphs=[
                f"Run `{command}` from the repository root. The brief was generated from the model "
                f"artifact set at {generated_utc or datetime.now(UTC)}.",
                "Source artifacts: network, strategic, tactical, resources, operations, shifts, "
                "workforce, bid, uncertainty, scenario-optimization, and access JSON files.",
            ],
            bullets=[
                f"Repository commit: `{commit}`.",
                "The exact small-instance MILP and heuristic large-instance paths are separate; "
                "do not infer global optimality at 10,000 segments.",
            ],
        ),
    ]
    created = generated_utc or datetime.now(UTC)
    if created.tzinfo is None:
        raise PlanningBriefError("generated_utc must be timezone-aware")
    markdown = render_markdown(
        title=title,
        instance_id=instance_id,
        generated_utc=created,
        command=command,
        commit=commit,
        sections=sections,
    )
    html = render_html(
        title=title,
        instance_id=instance_id,
        generated_utc=created,
        command=command,
        commit=commit,
        sections=sections,
    )
    slug = _slug(instance_id)
    return PlanningBrief(
        instance_id=instance_id,
        title=title,
        generated_utc=created,
        command=command,
        commit=commit,
        markdown=markdown,
        html=html,
        filename_markdown=f"{slug}-planning-brief.md",
        filename_html=f"{slug}-planning-brief.html",
    )


__all__ = [
    "PLANNING_BRIEF_SCHEMA_VERSION",
    "BriefSection",
    "BriefTable",
    "PlanningBrief",
    "PlanningBriefError",
    "build_planning_brief",
    "render_html",
    "render_markdown",
]

"""Tests for the self-contained planning brief."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from brushline.strategic.planning_brief import (
    BriefSection,
    BriefTable,
    PlanningBriefError,
    build_planning_brief,
    render_html,
    render_markdown,
)

CREATED = datetime(2026, 11, 15, 23, 0, tzinfo=UTC)


def _artifacts() -> dict[str, Any]:
    network = {
        "instance_id": "bc-hydro-network-2026",
        "aoi_ha": 8737,
        "line_km": 29.2,
        "lines": [{"line_id": "L01"}],
        "units": [{"unit_id": "U001"}],
        "segments": [{"segment_id": "L01-S001"}],
        "sources": [{"name": "OSM <test>", "licence": "ODbL"}],
        "assumptions": {
            "method_costs": {
                "mowing": {
                    "cost_ha": 420,
                    "hours_ha": 7,
                    "service_gain": 0.35,
                    "risk_reduction": 0.3,
                }
            },
            "contractor_capacity": [2600, 4200, 2400],
            "segment_m": 500,
            "horizon": 5,
            "start_year": 2027,
            "caveat": "Prototype assumptions only.",
        },
    }
    strategic = {
        "milp_scenarios": [
            {
                "name": "milp-budget-60000",
                "annual_budget": 60000,
                "five_year_cost": 299859,
                "mean_service": 0.971,
                "mean_risk": 0.0294,
                "mean_annual_hours": 1000,
                "rows": [
                    {
                        "year": 2027,
                        "cost": 59972,
                        "hours": 1000,
                        "risk": 0.115,
                        "service": 0.885,
                        "actions": 46,
                    }
                ],
                "plan": {
                    "solver": "scipy-highs",
                    "status": "optimal",
                    "replay_ok": True,
                },
            }
        ],
        "stateful_bau": {
            "five_year_cost": 79082,
            "mean_service": 0.747,
            "mean_risk": 0.257,
            "mean_annual_hours": 264,
        },
        "caveats": ["A strategic caveat."],
        "scalability": [
            {
                "segments": 59,
                "variables": 295,
                "seconds": 0.05,
                "mean_risk": 0.029,
                "status": "feasible",
                "evaluations": 21,
            }
        ],
    }
    tactical = {
        "actions": [{"year": 2027, "cost": 59972}],
        "total_cost": 299859,
        "cost_by_year": {"2027": 59972},
    }
    resources = {
        "requests": [{"year": 2027, "capacity_units": 1000}],
        "total_cost": 258638,
        "feasible": True,
    }
    operations = {"work_orders": [{"year": 2027}], "feasible": True}
    shifts = {
        "assignments": [{"work_order_id": "wo-1"}],
        "total_productive_hours": 4998,
        "total_travel_hours": 42,
        "crew_utilization": {"crew-a": 4998},
        "feasible": True,
    }
    workforce = [
        {
            "name": "current-mix",
            "reassigned_hours": 0,
            "resource_cost": 258638,
            "resource_feasible": True,
            "shift_feasible": True,
            "shift_assignments": 698,
        }
    ]
    bid = {
        "owner_total": 299859,
        "bid": {
            "total_cost": 321651,
            "assumptions": ["Mock contractor rate adjustment."],
        },
        "comparison": {
            "delta": 21792,
            "fair_low": 284866,
            "fair_high": 344838,
            "within_fair_range": True,
        },
    }
    uncertainty = {
        "samples": 500,
        "cost_band": {"p10": 231034, "p50": 296536, "p90": 373432},
        "hours_band": {"p10": 4090, "p50": 5014, "p90": 5956},
        "probability_budget_exceeded": 0.484,
        "probability_capacity_shortfall": 0.0,
    }
    scenario_optimization = {
        "scenarios": 30,
        "fixed_cost_band": {"p10": 249742, "p90": 371650},
        "adaptive_cost_band": {"p10": 298055, "p90": 299452},
        "fixed_risk_band": {"mean": 0.0294},
        "adaptive_risk_band": {"mean": 0.0317},
        "probability_adaptation_improves": 1.0,
        "mean_fixed_objective": 0.1068,
        "mean_adaptive_objective": 0.0317,
        "mean_regret": 0.0752,
        "fixed_budget_violation_probability": 0.5667,
    }
    rolling_policy = {
        "episodes": 20,
        "lookahead_years": 2,
        "fixed_cost_band": {"p10": 265469, "p90": 333437},
        "rolling_cost_band": {"p10": 298123, "p90": 299398},
        "fixed_risk_band": {"mean": 0.0294},
        "rolling_risk_band": {"mean": 0.0296},
        "fixed_budget_violation_probability": 0.95,
        "rolling_budget_violation_probability": 0.0,
        "fixed_capacity_violation_probability": 0.0,
        "rolling_capacity_violation_probability": 0.0,
        "mean_fixed_objective": 0.1031,
        "mean_rolling_objective": 0.0296,
        "mean_regret": 0.0735,
        "probability_rolling_improves": 1.0,
    }
    policy_execution = {
        "selection": {"episode_index": 18, "year": 2027},
        "policy": {
            "actions": 45,
            "cost": 59794,
            "hours": 814,
            "tactical_actions": 17,
            "work_orders": 17,
            "shift_assignments": 116,
            "resource_feasible": True,
            "shift_feasible": True,
        },
        "fixed": {"actions": 46, "cost": 59972, "hours": 1000},
    }
    policy_execution_scan = {
        "episodes": 20,
        "execution_feasibility_rate": 1.0,
        "tactical_feasibility_rate": 1.0,
        "access_open_rate": 1.0,
        "resource_feasibility_rate": 1.0,
        "operation_feasibility_rate": 1.0,
        "shift_feasibility_rate": 1.0,
        "cost_band": {"p10": 59775, "p90": 59986},
        "hours_band": {"p10": 699, "p90": 1295},
    }
    static_plan = {
        "episodes": 20,
        "budget_risk_limit": 0.05,
        "recommended": "milp-budget-30000",
        "plans": [
            {
                "name": "milp-budget-30000",
                "nominal_budget": 30000,
                "cost_band": {"p10": 132246, "p90": 166121},
                "risk": 0.1009,
                "budget_violation_probability": 0.0,
            },
            {
                "name": "milp-budget-60000",
                "nominal_budget": 60000,
                "cost_band": {"p10": 265469, "p90": 333438},
                "risk": 0.0294,
                "budget_violation_probability": 0.95,
            },
        ],
    }
    operational_stress = {
        "scenarios": 50,
        "window_days": 75,
        "outage_days": [11, 12, 13, 14, 15],
        "weather_probability": 0.2,
        "completion_probability": 0.0,
        "mean_completion_rate": 0.9341,
        "baseline": {
            "feasible": True,
            "assignments": 116,
            "unscheduled_hours": 0.0,
        },
        "unscheduled_hours_band": {"p50": 50.2, "p90": 97.7},
        "shift_assignments_band": {"p50": 107.0},
    }
    operational_stress_scan = {
        "episodes": 20,
        "scenarios_per_episode": 50,
        "window_days": 75,
        "baseline_feasibility_rate": 0.5,
        "scenario_completion_rate": 0.132,
        "mean_completion_rate": 0.8563,
        "unscheduled_hours_band": {"p50": 127.5, "p90": 372.31},
        "failure_sources": {
            "fall_window": 10,
            "weather_outage_calendar": 8,
            "crew_capacity": 0,
            "none": 2,
        },
        "window_sensitivity": [
            {
                "window_days": 75,
                "scenario_completion_rate": 0.1375,
                "mean_unscheduled_hours": 165.77,
            },
            {
                "window_days": 90,
                "scenario_completion_rate": 0.4025,
                "mean_unscheduled_hours": 83.69,
            },
            {
                "window_days": 105,
                "scenario_completion_rate": 0.6275,
                "mean_unscheduled_hours": 38.27,
            },
        ],
    }
    operational_remedies = {
        "episodes": 20,
        "scenarios_per_episode": 50,
        "crew_day_cost": 1200.0,
        "machine_day_cost": 900.0,
        "annual_budget": 60000.0,
        "cases": [
            {
                "name": "baseline",
                "scenario_completion_rate": 0.132,
                "mean_completion_rate": 0.8563,
                "unscheduled_hours_band": {"p50": 127.5},
                "added_cost_band": {"p50": 0.0},
                "total_cost_band": {"p50": 59875.0},
                "budget_feasibility_rate": 1.0,
            },
            {
                "name": "+1 shared crew + machine",
                "scenario_completion_rate": 0.929,
                "mean_completion_rate": 0.9982,
                "unscheduled_hours_band": {"p50": 0.0},
                "added_cost_band": {"p50": 80850.0},
                "total_cost_band": {"p50": 140800.0},
                "budget_feasibility_rate": 0.0,
            },
        ],
    }
    risk_ranked_scope = {
        "target_fraction": 0.2,
        "cases": [
            {
                "name": "risk-ranked 20% scope + 105-day",
                "window_days": 105,
                "scenario_completion_rate": 0.874,
                "mean_risk_loss": 0.04127,
                "mean_residual_risk": 0.154581,
                "mean_deferred_fraction": 0.2131,
                "total_cost_band": {"p50": 47226.19},
                "budget_feasibility_rate": 1.0,
            },
            {
                "name": "risk-ranked 20% scope + 75-day",
                "window_days": 75,
                "scenario_completion_rate": 0.471,
                "mean_risk_loss": 0.04127,
                "mean_residual_risk": 0.154581,
                "mean_deferred_fraction": 0.2131,
                "total_cost_band": {"p50": 47226.19},
                "budget_feasibility_rate": 1.0,
            },
        ],
    }
    risk_trajectory = {
        "years": [2027, 2028, 2029, 2030, 2031],
        "mean_deferred_fraction": 0.2131,
        "cases": [
            {
                "name": "full policy",
                "annual_risk": [0.1133, 0.0147, 0.0060, 0.0067, 0.0073],
                "mean_risk_loss": 0.0,
                "final_risk_loss": 0.0,
            },
            {
                "name": "risk-ranked first-year 20%",
                "annual_risk": [0.1546, 0.0560, 0.0473, 0.0480, 0.0486],
                "mean_risk_loss": 0.0413,
                "final_risk_loss": 0.0413,
            },
        ],
    }
    rolling_recovery = {
        "years": [2027, 2028, 2029, 2030, 2031],
        "lookahead_years": 2,
        "mean_recovery": 0.029531,
        "final_recovery": 0.041266,
        "cases": [
            {
                "name": "full policy",
                "annual_risk": [0.1133, 0.0147, 0.0060, 0.0067, 0.0073],
                "mean_risk_loss": 0.0,
                "final_risk_loss": 0.0,
            },
            {
                "name": "deferred, no reoptimization",
                "annual_risk": [0.1546, 0.0560, 0.0473, 0.0480, 0.0486],
                "mean_risk_loss": 0.04127,
                "final_risk_loss": 0.04127,
            },
            {
                "name": "deferred, rolling reoptimization",
                "annual_risk": [0.1546, 0.0318, 0.0063, 0.0067, 0.0073],
                "mean_risk_loss": 0.011739,
                "final_risk_loss": 0.000003,
            },
        ],
    }
    out_of_sample_recovery = {
        "episodes": 20,
        "paths_total": 100,
        "final_loss_band": {"p10": -0.007771, "p50": -0.001029, "p90": 0.007205, "mean": -0.000793},
        "recovery_band": {"p10": 0.033975, "p50": 0.042105, "p90": 0.04905, "mean": 0.042063},
        "probability_final_gap_at_most_0_005": 0.87,
        "reopt_cost_band": {"p10": 284835, "p50": 285927, "p90": 286788, "mean": 285868},
        "no_reopt_cost_band": {"p10": 227290, "p50": 249930, "p90": 272072, "mean": 251312},
        "full_cost_band": {"p10": 273213, "p50": 295899, "p90": 326472, "mean": 299052},
    }
    access = {
        "results": [{"allowed": True}, {"allowed": True}],
        "total_route_m": 86235,
        "feasible": True,
    }
    return {
        "network": network,
        "strategic": strategic,
        "tactical": tactical,
        "resources": resources,
        "operations": operations,
        "shifts": shifts,
        "workforce": workforce,
        "bid": bid,
        "uncertainty": uncertainty,
        "scenario_optimization": scenario_optimization,
        "access": access,
        "rolling_policy": rolling_policy,
        "policy_execution": policy_execution,
        "policy_execution_scan": policy_execution_scan,
        "static_plan": static_plan,
        "operational_stress": operational_stress,
        "operational_stress_scan": operational_stress_scan,
        "operational_remedies": operational_remedies,
        "risk_ranked_scope": risk_ranked_scope,
        "risk_trajectory": risk_trajectory,
        "rolling_recovery": rolling_recovery,
        "out_of_sample_recovery": out_of_sample_recovery,
    }


def test_planning_brief_markdown_and_html() -> None:
    artifacts = _artifacts()
    brief = build_planning_brief(
        **artifacts,
        generated_utc=CREATED,
        command="python tools/build_bc_network_demo.py",
        commit="abc1234",
    )
    assert brief.filename_markdown == "bc-hydro-network-2026-planning-brief.md"
    assert brief.filename_html == "bc-hydro-network-2026-planning-brief.html"
    assert "BC Hydro public-data network planning brief" in brief.markdown
    assert "## Decision summary" in brief.markdown
    assert "## Workforce scenarios" in brief.markdown
    assert "## Commercial check" in brief.markdown
    assert "## Execution uncertainty" in brief.markdown
    assert "## Hindsight adaptive planning" in brief.markdown
    assert "## Rolling-horizon policy" in brief.markdown
    assert "20 annual-factor episodes; 2-year lookahead" in brief.markdown
    assert "## Rolling year-one execution" in brief.markdown
    assert "Selected episode 18" in brief.markdown
    assert "## Policy execution scan" in brief.markdown
    assert "Fully feasible: 100.0%" in brief.markdown
    assert "## Static budget-headroom plans" in brief.markdown
    assert "## Weather and outage stress" in brief.markdown
    assert "stress fully feasible: 0.0%" in brief.markdown
    assert "## All-episode weather and outage scan" in brief.markdown
    assert "Failure sources: fall window 10" in brief.markdown
    assert "## Weather/outage remedies" in brief.markdown
    assert "+1 shared crew + machine" in brief.markdown
    assert "## Risk-ranked scope deferral" in brief.markdown
    assert "risk-ranked 20% scope + 105-day" in brief.markdown
    assert "## Multi-year risk trajectory" in brief.markdown
    assert "risk-ranked first-year 20%" in brief.markdown
    assert "## Rolling recovery after deferral" in brief.markdown
    assert "deferred, rolling reoptimization" in brief.markdown
    assert "## Out-of-sample recovery" in brief.markdown
    assert "100 paths" in brief.markdown
    assert "milp-budget-30000" in brief.markdown
    assert "299,859" in brief.markdown
    assert "249,742-371,650" in brief.markdown
    assert "current-mix" in brief.markdown
    assert "Mock contractor rate adjustment." in brief.markdown
    assert "&lt;test&gt;" in brief.html
    assert "<table>" in brief.html
    assert "<script" not in brief.html
    assert "abc1234" in brief.html
    assert "Prototype assumptions only." in brief.html


def test_planning_brief_validation_and_renderers() -> None:
    artifacts = _artifacts()
    with pytest.raises(PlanningBriefError, match="network artifact"):
        build_planning_brief(**{**artifacts, "network": {}}, generated_utc=CREATED)
    with pytest.raises(PlanningBriefError, match="strategic artifact"):
        build_planning_brief(**{**artifacts, "strategic": {}}, generated_utc=CREATED)
    empty_strategic = {**artifacts["strategic"], "milp_scenarios": []}
    with pytest.raises(PlanningBriefError, match="no MILP scenarios"):
        build_planning_brief(**{**artifacts, "strategic": empty_strategic}, generated_utc=CREATED)
    with pytest.raises(PlanningBriefError, match="timezone-aware"):
        build_planning_brief(
            **artifacts,
            generated_utc=datetime(2026, 11, 15, 23, 0),
        )
    section = BriefSection(
        heading="Example",
        paragraphs=["A paragraph"],
        bullets=["A bullet"],
        table=BriefTable(columns=["A", "B"], rows=[["1", "2"]], note="A note"),
    )
    assert "A note" in render_markdown(
        title="T",
        instance_id="i",
        generated_utc=CREATED,
        command="cmd",
        commit="c",
        sections=[section],
    )
    assert "A note" in render_html(
        title="T",
        instance_id="i",
        generated_utc=CREATED,
        command="cmd",
        commit="c",
        sections=[section],
    )

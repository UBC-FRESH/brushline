# Brushline Interactive Planning Studio

Status: draft for Phase 0 review
Phase: P0
Date: 2026-11-14
Task: P0.7
Related: ADR 0007, `notes/design/brushline-architecture.md`

## 1. Purpose

The studio is the browser surface for Brushline. It is not a reporting afterthought and it is not a
second model runtime. It is one optional FastAPI service and one static browser shell over the artifacts
the command line writes.

It serves three kinds of work:

- **Build:** point at an AOI, inspect data availability, approve sources, watch an instance build, and
  review the result.
- **Plan:** read a strategic, tactical, or operational plan on a 2D corridor map and a 3D operations
  scene, edit targets, start or stop a search, and explore the Pareto archive.
- **Explain:** show the owner, the contractor, the reviewer, and a prospective partner why the plan looks
  the way it does, with provenance, caveats, and a clear separation between what the model shows and what
  it does not.

The studio follows the patterns already proven in WS4, FHOPS, Fresh Fire Studio, the FRESH urban-forest
lab, and Fresh Woodlots.

## 2. Design principles

1. **Artifacts are the contract.** The service reads `run.json`, the plan, `schedule.csv`,
   `account_values.csv`, `pareto.json`, `operations_timeline.jsonl`, `telemetry.jsonl`, and `reports/`.
   It does not own model state and does not compute a value the CLI cannot reproduce.
2. **One application, several skins.** A skin is a checked manifest of panels, layers, actions, and a
   read-only flag. A new role is a new manifest, not a new application.
3. **2D and 3D share one state.** The selected segment, span, period, year, plan, and run are shared
   between the map and the scene.
4. **The map is the corridor.** The map shows segments, spans, structures, access, treatments, monitoring
   coverage, and risk. It is not a generic basemap with a line drawn on it.
5. **The 3D scene is a context view.** It shows terrain, corridor, vegetation, structures, machines, and
   crews. It is not survey-grade geometry and does not claim field accuracy.
6. **Live search is observable.** Server-sent events stream progress, the incumbent, target values, and
   schedule changes. Pause and stop write a control file; the search writes the usual artifacts.
7. **The archive is inspectable.** The Pareto explorer shows the objective vectors, dominance,
   trade-offs, and the evidence behind each archive member.
8. **Offline-capable and proxy-safe.** MapLibre and Three.js are vendored. URLs are relative so the app
   works at `/` and behind a path prefix.
9. **Small and auditable.** Loopback bind by default, explicit remote opt-in, allowlisted actions, no
   authentication in the first release, and a read-only skin that cannot mutate.

## 3. Workspaces

The shell has five workspaces. A skin decides which are visible.

| Workspace | Purpose |
| --- | --- |
| **Build** | AOI selection, data availability, fetch plan, approvals, build progress, gap report, instance handoff |
| **Map** | 2D corridor map, layers, period strip, segment detail, monitoring coverage |
| **Plan** | Targets, charts, plan table, cost build-up, search controls, archive |
| **Results** | Reports, comparisons, Pareto explorer, operations animation, exports |
| **Data** | Dataset summary, LiDAR bundle and model cards, provenance, coverage, caveats |

The **Build** workspace is only in the `model-builder` skin. The public demo portal uses a read-only
subset of Map, Plan, and Results; it is a separate surface, not a skin of an operational deployment.

## 4. Skins

### 4.1 Skin manifest

```json
{
  "id": "tactical-planner",
  "title": "Tactical planner",
  "description": "Multi-year treatment units, contractors, access, and monitoring missions.",
  "workspaces": ["map", "plan", "results", "data"],
  "panels": ["legend", "dataset", "targets", "plan_table", "cost_buildup", "reports", "archive"],
  "layers": ["corridor", "segments", "treatments", "monitoring", "access", "risk", "structures"],
  "actions": ["edit_targets", "save_targets", "start_search", "pause_search", "stop_search", "export"],
  "read_only": false
}
```

The loader validates:

- the id is unique and lowercase;
- every workspace, panel, layer, and action is in the registry;
- a read-only skin has no mutating action;
- the skin does not name an artifact the run type cannot produce;
- the required provenance and caveat panels are present.

### 4.2 The seven skins

| Skin | Primary user | Workspaces | Key actions | Read-only |
| --- | --- | --- | --- | --- |
| `model-builder` | Analyst or agent building an instance | Build, Data | Select AOI, approve sources, build, review, export | no |
| `owner-strategic` | Asset owner executive and program manager | Map, Plan, Results, Data | Edit targets, start search, compare, export | no |
| `tactical-planner` | Tactical planner | Map, Plan, Results, Data | Edit targets, start search, compare, export | no |
| `operations-planner` | Field operations supervisor | Map, Plan, Results | Edit work plan, animate, export | no |
| `contractor-bid` | Contractor estimator | Map, Plan, Results, Data | Edit bid annotations, compare, export | no |
| `monitoring` | Monitoring specialist | Map, Plan, Results, Data | Edit monitoring plan, start mission search, export | no |
| `reviewer` | Reviewer, auditor, community liaison | Map, Plan, Results, Data | None | yes |

The model-builder skin is the map-to-instance surface. The reviewer skin is the audit surface. The
contractor-bid skin is the shared-plan surface, not a separate product.

## 5. 2D map

### 5.1 Layers

- **Corridor:** the corridor centerline and the management standard.
- **Segments:** the decision units, coloured by the selected attribute.
- **Vegetation height / cover / uncertainty:** a class or continuous ramp with a legend.
- **Treatment need / risk:** the risk-weighted score, with the components in the detail panel.
- **Planned treatments:** the current period, with the method and the treatment unit.
- **Cumulative treatments:** the current period and earlier, distinguished from the current period.
- **Monitoring coverage:** observed, stale, missing, and out of domain.
- **Access:** the road network, status, and the route to the segment.
- **Structures:** towers, poles, crossings, valves, and other assets.
- **Bid delta:** the difference between two bids or two plans, with a named assumption.
- **Comparison:** A-only, B-only, both, neither.

### 5.2 Interactions

- Click a segment to open the detail panel: state, uncertainty, history, planned action, cost, risk,
  observations, and provenance.
- Hover to preview the period value and the target status.
- The period strip folds years into the plan's periods and shows both the period and the year range.
- The layer tree groups layers and names the reason a layer is unavailable.
- The map fits to the corridor, not to a generic basemap extent.
- The URL carries `run`, `view`, `period`, `segment`, and `plan` so refresh and back/forward restore the
  view.
- The map supports 1024×768 landscape and larger, including iPad landscape. Phone layout is not a
  supported target.

### 5.3 Level of detail

- At overview zoom, draw segment centroids or simplified lines with counts.
- At detail zoom, draw the segment geometry and the selected attributes.
- Use vector tiles or PMTiles where the segment count makes GeoJSON impractical.
- Keep the full-run counts while drawing the viewport.

## 6. 3D scene

### 6.1 Content

- terrain from the DEM, with hillshade and slope;
- corridor centerline and segment footprints;
- vegetation height and cover as instanced or impostor geometry;
- mature-tree crowns where a tree product exists;
- structures and crossings;
- machines and crews from the operations timeline;
- treatment units and current actions;
- a ground plane and a scale reference.

### 6.2 Interaction

- Orbit, pan, and zoom.
- Click a segment or a machine to select it; the selection is shared with the 2D map.
- Play, pause, speed, and scrub the operations timeline.
- Toggle vegetation, structures, machines, and treatment layers.
- A camera target can be pinned to a segment or a treatment unit.

### 6.3 Fidelity and caveats

- Vegetation is a procedural or instanced representation of the state; it is not a measured stem map.
- Crown shapes are approximations unless a tree product supplies them.
- The scene is a context view, not an engineering model.
- The UI displays a persistent "context view" note and a link to the methods page.
- The scene does not imply that a machine position is a real GPS track.

### 6.4 Level of detail

- A near-field stand with individual trunks and crowns around the camera target.
- A mid-field ring of tree or shrub silhouettes.
- A far-field canopy or cover texture over the observed extent.
- Fixed world-space detail tiles cached across navigation.
- A frame budget and a fallback when the device cannot render the scene.

## 7. Shared state and URL

The shared state is:

```text
instance -> run -> plan -> period -> year -> segment/span -> layer -> selection
```

- The URL is the source of truth for refresh and back/forward.
- A run selector lists the runs in the instance.
- A plan selector lists the plan versions.
- A period selector folds the years by the plan's period width.
- A segment selector is shared by the map, the 3D scene, the detail panel, and the charts.
- A skin cannot hide the provenance or the caveats.

## 8. Live search

### 8.1 Stream

- `GET /api/runs/{run}/events` returns server-sent events.
- Events: `progress`, `targets`, `schedule`, `done`, `error`.
- `progress` carries the objective, the best iteration, the accepted moves, and the elapsed time.
- `targets` carries the current target values and the status.
- `schedule` carries the changed segments, not the whole schedule, unless the incumbent resets.
- A finished run returns `204 No Content` to stop EventSource reconnecting.
- A live stream closes after a bounded time and reconnects, so a lost browser cannot hold a thread.

### 8.2 Control

- `POST /api/runs/{run}/control` with `{"action": "pause" | "run" | "stop"}`.
- The search polls a control file at a bounded cadence.
- Pause holds the current incumbent.
- Stop writes the best schedule and the summary.
- The service refuses a control action it did not start or a run that is not live.

### 8.3 Start

- `POST /api/runs` starts a search only when the service was started with `--allow-runs`.
- The request can choose the iterations, seed, years, islands, and time limit within bounds.
- The service composes the command from its configured dataset, targets, scenario, and topology.
- The request body cannot choose an arbitrary command, path, or dataset.
- The new run appears in the run selector when its summary lands.

## 9. Pareto explorer

### 9.1 Views

- **Pareto front:** the non-dominated archive members in two or three objective dimensions.
- **Parallel coordinates:** every objective, with brushing and filtering.
- **Scatter matrix:** pairwise trade-offs.
- **Table:** objective values, plan id, seed, budget, feasibility, and evidence.
- **Comparison:** the selected archive member against the baseline or another plan.

### 9.2 Actions

- Filter by objective range, feasibility, budget, or plan.
- Select an archive member and inspect its plan on the map.
- Compare two archive members.
- **Promote to plan:** write the selected archive member as a new plan version, without rerunning the
  search.
- Export the archive table and the selected plan.

### 9.3 Rules

- The objective names, directions, and units come from the archive manifest.
- A member without an evidence record is displayed as incomplete, not as a result.
- The promotion action records the archive member, the evidence record, and the promotion reason.
- The explorer does not invent a weight or a preference. The weights and the scalarization portfolio are
  visible in the archive manifest.

## 10. Operations animation

- The animation reads `operations_timeline.jsonl`.
- Each event carries a timestamp, a crew or machine id, a segment or span, an action, a start, an end, a
  state, and a cost.
- The 2D map highlights the active segment and the route.
- The 3D scene moves the machine or crew marker along the route and shows the treatment.
- Play, pause, speed, and scrub are shared with the period selector.
- If the timeline is missing, the panel says so and does not synthesize positions.

## 11. Artifact endpoints

| Endpoint | Returns |
| --- | --- |
| `GET /api/summary` | Instance summary and run list |
| `GET /api/runs/{run}/summary` | `run.json` |
| `GET /api/runs/{run}/plan` | The plan header and tables |
| `GET /api/runs/{run}/accounts` | Account values, filtered by period and account |
| `GET /api/runs/{run}/targets` | Target values and status |
| `GET /api/runs/{run}/layers` | Available layers and named reasons for unavailable layers |
| `GET /api/runs/{run}/periods` | Period range and labels |
| `GET /api/runs/{run}/map` | GeoJSON for the selected layer and period |
| `GET /api/runs/{run}/tiles/{z}/{x}/{y}.mvt` | Vector tile for the selected layer |
| `GET /api/runs/{run}/pareto` | The Pareto archive |
| `GET /api/runs/{run}/timeline` | The operations timeline |
| `GET /api/runs/{run}/reports` | Report files |
| `GET /api/runs/{run}/events` | SSE stream |
| `POST /api/runs` | Start a search (allowlisted) |
| `POST /api/runs/{run}/control` | Pause, run, or stop (allowlisted) |
| `GET /api/skins` | The checked skin manifests |

The service refuses a path that escapes the instance root and a run that does not exist.

## 12. Deployment and security

- Loopback bind by default: `127.0.0.1`.
- A non-loopback bind is refused unless `--allow-remote` is passed.
- The first release has no authentication. A hosted deployment must sit behind the lab's access gate.
- The service reads artifacts and a small configuration; it does not execute arbitrary commands.
- A search start is refused unless `--allow-runs` is passed.
- A read-only skin cannot carry a mutating action.
- Relative URLs work at `/` and behind a proxy prefix.
- A health endpoint reports the service, the instance, and the artifact roots.
- The public demo portal is a separate static surface; it is not the studio with a public bind.

## 13. Performance and accessibility

- The first paint shows the shell and the run summary before the map is ready.
- The map and the 3D scene load progressively.
- Large layers use vector tiles or simplified geometry; the viewport keeps the full-run counts.
- The 3D scene has a frame budget and a fallback to the 2D map.
- Keyboard navigation covers the workspace tabs, the period strip, the layer tree, and the segment list.
- Colour is not the only channel: status also uses text and shape.
- The layout supports 1024×768 landscape and larger.
- The UI states the data vintage, the model card, and the caveat next to the result.

## 14. Reuse from the sibling projects

- **WS4:** the FastAPI plus static shell, the artifact-reader boundary, the layer tree, the period strip,
  the target charts, the comparison map, the skins, and the SSE/control pattern.
- **FHOPS:** the run discovery, the 3D operations scene, the machine and crew timeline, and the
  scenario-based service.
- **Fresh Fire Studio:** the static export, the 3D level-of-detail, the methods page, and the public
  framing.
- **Fresh Woodlots:** the catalogue, the featured-pilot framing, the pilot brief, the demo script, and
  the read-only deployment.
- **Urban-forest lab:** the shared selection between the 2D map and the 3D scene, the vendored Three.js,
  and the scenario time controls.

## 15. Acceptance criteria

- The studio reads only artifacts; the service holds no model state.
- The seven skins load and a read-only skin refuses a mutating action.
- The 2D and 3D views share the selected run, plan, period, and segment.
- The map shows corridor, segment, treatment, monitoring, access, risk, and structure layers, and names
  an unavailable layer.
- The 3D scene shows terrain, corridor, vegetation, structures, and operations, with a context-view
  caveat.
- Live search streams progress and schedule changes; pause and stop produce the usual artifacts.
- The Pareto explorer reads the archive and promotes a member without rerunning the search.
- The operations animation reads the timeline and invents no position.
- The service binds to loopback by default and refuses an unsafe remote bind.
- The dashboard is green and the UI contract tests pass.

## 16. Open questions

| Question | Resolve in |
| --- | --- |
| Which map format carries the first 10,000-segment case: GeoJSON, MVT, or PMTiles? | P10 |
| How much 3D vegetation is useful before it implies survey precision? | P4 and P10 |
| Which skin actions need a confirmation step? | P10 |
| How are target edits versioned against a plan? | P9 and P10 |
| How should the studio show an out-of-domain segment? | P3 and P10 |
| Which browser and device matrix is supported? | P10 |

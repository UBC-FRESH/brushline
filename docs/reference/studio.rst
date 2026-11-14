Planning studio
===============

P10 adds an artifact-only FastAPI service and static shell over the synthetic run. It exposes summary,
plan, Pareto, timeline, block, scene, skins, and SSE progress endpoints. The 2D map is an SVG corridor
view; the 3D context uses a deterministic canvas scene with a forester walkthrough, HUD, known/unknown
positions, and a Pre/Post treatment toggle. Seven skins are listed; the reviewer skin is read-only.

The service does not own model state and does not invent positions. The forester walkthrough plan is
`notes/design/brushline-forester-walkthrough.md`.

The studio also includes an observed public-data UBC block: 538 tree records plus a 2 m DEM/CHM grid, with PDDL-1.0/Abacus attribution. It is shown as `ubc-real`; pre/post is disabled because it is observed state, not a modelled treatment scenario.

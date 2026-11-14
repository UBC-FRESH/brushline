# Forester POV walkthrough with pre/post-treatment views

Status: proposed for P10
Phase: P10 Interactive planning studio
Related: `brushline-ui.md`, `brushline-architecture.md`, ADR 0007
Date: 2026-11-14
Task: P10.3 (3D scene), P10.7 (operations animation)

## 1. Purpose

Give a forester a first-person, eye-height inspection of any selected **block** in a model instance,
and let them toggle the scene between the **pre-treatment** and **post-treatment** state without losing
their camera position or context.

This is an inspection and communication view. It is not a survey, a stem map, a safety certification, or
a claim that the rendered vegetation is field-accurate.

## 2. Block semantics

Brushline uses **segment** and **treatment unit** as its vocabulary. The UI will call the selected
inspection area a **block** only as a user-facing label.

- The canonical block is a **treatment unit**.
- Selecting a single segment resolves to its treatment unit and highlights the contributing segments.
- If the model instance has no treatment-unit join, the block is the selected segment group and the UI
  says so.
- A block with no selected treatment still opens in the current state; the pre/post toggle is disabled
  with an explicit reason.

## 3. User flow

1. Select a block on the 2D map, plan table, or 3D scene.
2. Choose **Walk this block**.
3. The walkthrough camera spawns at the block's first landing, else the nearest access point, else the
   first boundary vertex, facing the area-weighted block centroid. This is the FHOPS spawn rule.
4. The HUD shows block id, terrain coordinates, compass heading, ground elevation, current plan year,
   treatment action, and the state variant.
5. The walker moves with WASD or arrow keys, runs with Shift, looks with pointer lock or drag fallback,
   and exits with Esc.
6. **V** or the **Pre / Post** toggle switches the vegetation/state variant. The camera, yaw, pitch,
   selection, and time remain fixed. The toggle is a layer/state swap, not a scene reload.
7. Exiting restores the prior orbit camera, field of view, target, and editing tool.

The first release supports two variants:

- `pre`: the state immediately before the selected treatment action.
- `post`: the immediate post-treatment state returned by the P4 treatment transition.

A later `post_1y`/`post_recovered` variant can use the P4 post-delay trajectory, but it must be a named
variant and must not be confused with the immediate result.

## 4. Existing implementations to reuse

### FHOPS forester walkthrough

`fhops-ground-support/sandbox/studio/static/studio_3d.js` already has:

- `enterWalkthrough()` and `exitWalkthrough()` with orbit-camera snapshot/restore;
- `updateWalkthrough(dt)` with terrain-following movement, eye height, smoothing, walking bob, and
  block-bound clamping;
- `walkSpawn()`, `blockCentroid()`, `getBounds()`, and `terrainHeight()`;
- HUD updates and pointer-lock/drag look.

Constants worth preserving: eye height `1.7 m`, walk FOV `68°`, radius `2 m`. The movement does not
collide with individual trees or model slope speed.

### FHOPS shared POV camera

`fhops-ground-support/sandbox/tree_lab/static/viewer.js` provides the reusable camera pattern:

- `setPov(id)` / `exitPov()` / `cyclePov(direction)`;
- orbit snapshot restore;
- terrain-relative eye height;
- heading smoothing from route geometry and look targets;
- pointer-lock and drag fallback;
- `onPov` callback for HUD synchronization.

For Brushline, the POV subject is a **forester walker**, not a machine, so route-following is replaced
by free walking inside the block.

### Fresh urban forest lab

`fresh-urban-forest-lab/src/fresh_urban_forest/web/static/app.js` supplies:

- the Three.js scene setup (`ensureThree`, terrain mesh, instanced trees, roads, buildings);
- scenario/year state (`previewYear`) and `loadSceneAtYear(year)`;
- the explicit baseline/scenario verdict and caveats;
- the pattern of rebuilding scene layers while keeping the page state.

Brushline should reuse the state-switch pattern but not reload the whole scene for pre/post. The two
variants should be prebuilt or lazily loaded in parallel, then swapped in place.

### WS4 scene

`ws4-gpu/ws4/scene/viewer.html` provides instanced trunk/crown geometry, terrain, camera setup, and
time-state updates. It is the preferred reference for draw-call-efficient block vegetation and a
time-swept state layer.

### Reuse rule

Extract or reimplement the small camera/HUD behaviour in a Brushline-owned module with attribution and a
licence check. Do not copy a sibling application wholesale, and do not fork FHOPS or the urban-forest
lab.

## 5. Scene contract

Add a versioned `brushline.scene.v1` artifact for a model instance and block. It is written by the CLI or
scene exporter and read by the studio. The browser does not compute the vegetation state.

```json
{
  "schema_version": "brushline.scene.v1",
  "instance_id": "corridor-a",
  "block": {
    "block_id": "tu-042",
    "block_kind": "treatment_unit",
    "segment_ids": ["seg-101", "seg-102"],
    "bounds_m": [0, 0, 240, 180],
    "centroid_m": [120, 90],
    "access_point_m": [0, 90]
  },
  "terrain": {
    "dem_path": "layers/dem.tif",
    "crs": "EPSG:3005",
    "resolution_m": 1.0,
    "vertical_datum": "CGVD2013",
    "source": "femic.lidar.bundle.v1"
  },
  "plan": {
    "plan_id": "plan-007",
    "run_id": "run-012",
    "year": 2028,
    "action_id": "act-221",
    "method": "mowing",
    "season": "spring"
  },
  "state": {
    "pre": {
      "variant_id": "pre",
      "state_version": "brushline.state.v1",
      "vegetation_path": "blocks/tu-042/pre.json",
      "observed_or_model": "model",
      "caveat": "Model state, not a measured stem map."
    },
    "post": {
      "variant_id": "post",
      "state_version": "brushline.state.v1",
      "vegetation_path": "blocks/tu-042/post.json",
      "observed_or_model": "model",
      "treatment_result": "brushline.treatment.v1",
      "caveat": "Immediate modelled post-treatment state."
    }
  },
  "geometry": {
    "vegetation_kind": "instanced_shrub_tree",
    "tree_product": "layers/trees.parquet",
    "position_source": "canopy_or_tree_product",
    "geometry_seed": 17,
    "lod": ["near", "mid", "far"]
  },
  "caveats": [
    "Context view only; not survey-grade geometry.",
    "No invented positions: absence of a tree product is labelled."
  ]
}
```

Rules:

- Pre and post use the same block bounds, terrain, geometry seed, and stable instance ids.
- Only state attributes (height, cover, density, class, crown scale) change between variants.
- Every vegetation feature names whether its position is observed, derived from a tree product, or
  approximate from a raster. Missing positions are omitted, not synthesised.
- If the selected action has no post state, `post` is `null` with an error reason.
- The scene artifact references layers; it does not duplicate raw point clouds.

## 6. API surface

The P10 service reads artifacts only. Proposed endpoints:

- `GET /api/instances/{instance_id}/blocks` — blocks with bounds, segment ids, plan action, variant
  availability.
- `GET /api/instances/{instance_id}/scene/{block_id}` — `brushline.scene.v1` manifest.
- `GET /api/instances/{instance_id}/scene/{block_id}/{variant}` — block terrain and vegetation payload,
  where `variant` is `pre` or `post`.
- `GET /api/instances/{instance_id}/scene/{block_id}/diff` — bounded vegetation changes for a later
  split/compare mode.

All responses are cacheable and read-only. The service rejects unknown block ids, missing variant
artifacts, and paths outside the artifact root. It does not compute treatment transitions on request.

## 7. Browser modules

Keep the camera and variant logic separate from the planning shell:

- `brushline/web/static/studio_pov.js`
  - `createPovController({camera, controls, terrain, bounds, onHud})`
  - `enter({spawn, heading})`, `exit()`, `update(dt)`, `handleLook(dx, dy)`
  - orbit snapshot/restore, pointer lock/drag, terrain follow, HUD callbacks.
- `brushline/web/static/scene_variants.js`
  - `loadVariant(manifest, 'pre'|'post')`
  - `prefetchVariants()`, `activateVariant(id)`, `getActiveVariant()`
  - validates stable feature ids and swaps only state-driven attributes.
- `brushline/web/static/studio_3d.js`
  - block selection, walk button, Pre/Post toggle, URL state, and shared 2D selection.

The camera controller is generic; the variant module never mutates the camera.

## 8. Visual and interaction details

- HUD: block id, PRE/POST badge, plan year, action id/method/season, coordinates, elevation, heading,
  position confidence, and "context view" note.
- Toggle: keyboard `V`, HUD button, and a hold-to-compare affordance. A 150–250 ms crossfade is optional;
  the camera must not move.
- The post view shows the action and immediate state. If the model returns `out_of_domain`, `unknown`, or
  a blocked trajectory, the HUD shows the reason and does not fabricate a greener/cleaner scene.
- Layer toggles remain available (terrain, vegetation, structures, access, treatment unit boundary).
- Reduced-motion preference disables bob and crossfade.
- If pointer lock is unavailable, drag-look is the fallback; keyboard-only look is not required for the
  first release but focus and Esc must work.
- A read-only skin can enter walkthrough and toggle states; it cannot edit the plan.

## 9. Testing

- Contract tests:
  - `brushline.scene.v1` validation, stable ids, bounds, variant references, missing post state;
  - block resolution from segment to treatment unit;
  - path containment and no raw point-cloud duplication.
- Browser tests:
  - enter/exit restores orbit camera exactly;
  - WASD changes position and HUD coordinates;
  - pointer lock and drag fallback;
  - `V` swaps pre/post while position/yaw/pitch are unchanged;
  - missing variant disables the toggle with a reason;
  - 2D map and 3D walkthrough share block and variant selection;
  - URL refresh restores block, variant, and walk mode.
- Visual smoke:
  - before/after screenshot of the same block and camera pose;
  - post state visibly reflects the treatment result;
  - context-view and model-state labels are present.
- Performance:
  - 60 fps target on the supported desktop/iPad landscape hardware;
  - instanced near/mid/far LOD;
  - fallback to 2D map when WebGL or the frame budget fails.

## 10. Work breakdown

1. P10.3a — define `brushline.scene.v1` and block resolution; add fixture export.
2. P10.3b — port the FHOPS walkthrough camera/HUD into a Brushline-owned generic POV controller.
3. P10.3c — build pre/post variant payloads from the selected P4 treatment transition; load both in
   parallel; swap state attributes in place.
4. P10.3d — add the Walk this block control, Pre/Post toggle, URL state, and shared 2D/3D selection.
5. P10.7a — connect the walkthrough to the plan year/operations timeline without implying a real GPS
   position.
6. P10.8 — contract/browser/accessibility/performance tests and deployment checks.

## 11. Acceptance criteria

- Any selected treatment unit in a model instance with a scene artifact can enter a first-person
  walkthrough.
- Entering and exiting restores the prior orbit camera exactly.
- The walkthrough follows terrain at eye height and stays within the block bounds.
- Pre and post variants use the same camera, block geometry, and feature ids.
- The toggle is available only when both variants exist, and missing/blocked states are explicit.
- The HUD names the variant, action, year, position confidence, and context-view caveat.
- No position or vegetation state is invented when the artifact is absent.
- The 2D map and 3D view share block, variant, and year state.
- The dashboard and P10 browser tests are green.

## 12. Non-goals and risks

- No tree-trunk collision, slope travel cost, stream wading, or survey-grade traversal.
- No live UAV/GPS feed, machine cab POV, boom/head motion, or operator training.
- No implication that pre/post geometry is measured; it is a model comparison.
- No full point-cloud rendering; use LOD, instancing, and raster/tree-product representations.
- The main risk is visual overclaiming. Mitigate with persistent labels, provenance in the HUD, and a
  clear unavailable state.

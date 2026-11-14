# Brushline Demo Portal and Pilot Onboarding

Status: draft for Phase 0 review
Phase: P0
Date: 2026-11-14
Task: P0.11
Related: ADR 0010, `notes/design/brushline-ui.md`

## 1. Purpose

The demo portal is the partner-facing surface. It shows what Brushline can do for a utility, pipeline
operator, railway, road agency, or other corridor owner, and it turns a demonstration into a scoped pilot
conversation.

It is not an operational deployment. It is public-data-only, read-only, and explicit about its limits. It
reuses the patterns that already work in the lab:

- the WS4 public demo shell and skins;
- the FHOPS operations scene;
- Fresh Fire Studio's static export and 3D level-of-detail;
- Fresh Woodlots' catalogue, featured-pilot framing, pilot brief, and demo script;
- the urban-forest lab's 2D/3D shell.

## 2. Principles

1. **Show a decision, not a screenshot.** Every demo answers a partner question: what to treat, when,
   where to monitor, what it costs, and what changes.
2. **Public data only.** Synthetic or openly licensed data. No real partner, asset, contractor, or
   personal data.
3. **Read-only.** No uploads, no arbitrary searches, no arbitrary runs.
4. **Static-first.** A GitHub-Pages-compatible export from precomputed runs is the permanent portal. A
   lab preview may add a read-only service.
5. **Honest caveats.** Every page separates "what this shows" from "what this does not show".
6. **One manifest per demo.** The catalogue is versioned and validated.
7. **A clear pilot path.** A partner can see what data is needed, how it is protected, and what a pilot
   delivers.
8. **No marketing that outruns the evidence.** A demo metric is a result of a stated scenario, not a
   promise.

## 3. Demo portfolio

The first portfolio has six instances. Each is a real run directory plus a narrative.

| Demo | Partner question | Data | What it shows |
| --- | --- | --- | --- |
| **Utility corridor, LiDAR-rich** | What does a risk-ranked treatment program look like when the corridor has good LiDAR? | Public LidarBC, VRI, DRA, synthetic asset | State from LiDAR, treatment plan, clearance risk, cost, monitoring |
| **Remote pipeline, coverage gap** | What do we do where the open LiDAR does not reach? | Public VRI/DRA, synthetic asset, missing LiDAR | Coverage as a knowledge state, monitoring decision, uncertainty |
| **Fire-risk road or rail corridor** | Where does fuel connectivity change the treatment priority? | Public terrain, VRI, NTEMS, synthetic fuel | Fuel connectivity, risk, treatment trade-off, Pareto archive |
| **Contractor bid comparison** | Why do two bids for the same corridor differ? | Synthetic plan, two cost structures | One plan artifact, two views, attributable differences |
| **Monitoring policy** | Is a fixed inspection calendar cheaper than a targeted one? | Synthetic observation model | Fixed vs value-of-information monitoring, regret per dollar |
| **Multi-objective trade-off** | What does a lower budget cost in risk and service? | Synthetic corridor | Pareto front, parallel coordinates, promoted plan |

Each demo has:

- a one-sentence question;
- a map and a 3D scene;
- a plan timeline;
- target and account charts;
- a Pareto explorer where the run has an archive;
- a methods and provenance panel;
- a "what this shows" and "what this does not show" panel;
- a "what a pilot would need" panel;
- a contact and pilot-request link.

## 4. Demo manifest

Every demo has a `brushline.demo.v1` manifest:

```json
{
  "schema_version": "brushline.demo.v1",
  "id": "utility-lidar-rich",
  "title": "Utility corridor with open LiDAR",
  "sector": "utility",
  "region": "British Columbia",
  "aoi": "demo/utility-lidar-rich/aoi.geojson",
  "question": "What does a risk-ranked treatment program look like when the corridor has good LiDAR?",
  "data_sources": [
    {"name": "LidarBC", "licence": "OGL-BC", "version": "2024", "url": "https://lidar.gov.bc.ca/"},
    {"name": "VRI", "licence": "OGL-BC", "version": "2025"},
    {"name": "Synthetic asset", "licence": "CC0-1.0", "version": "1.0"}
  ],
  "scenarios": ["baseline", "risk-first", "budget-constrained"],
  "artifacts": {
    "run": "runs/risk-first/",
    "plan": "runs/risk-first/plan.json",
    "pareto": "runs/risk-first/pareto.json",
    "timeline": "runs/risk-first/operations_timeline.jsonl",
    "reports": "runs/risk-first/reports/"
  },
  "headline_metrics": [
    {"name": "present_cost", "value": 1200000, "unit": "CAD"},
    {"name": "service_attainment", "value": 0.96, "unit": "fraction"}
  ],
  "caveats": [
    "Synthetic asset geometry; public vegetation data.",
    "The plan is a demonstration, not an operational recommendation."
  ],
  "pilot": "pilot/utility-lidar-rich.md",
  "status": "published",
  "created_utc": "2026-11-14T00:00:00Z"
}
```

The builder validates:

- every source has a licence and a version;
- every artifact exists and is readable;
- the headline metrics are present in the run's accounts;
- the caveats are present;
- the pilot brief exists;
- no private-data marker or personal path is present.

## 5. Static-first build

```bash
brushline demo build --manifest demo/utility-lidar-rich/demo.json --out site/
```

The build:

- copies the small artifacts and the screenshots;
- generates the HTML pages from the manifest and the run artifacts;
- writes the map and 3D assets;
- validates every link, licence, caveat, and metric;
- writes a `manifest.sha256`;
- refuses a missing or private artifact.

The permanent portal is a GitHub Pages site. It needs no server. A large artifact stays in a public data
store with a stable URL; the site carries the pointer and the licence.

## 6. Optional interactive service

A lab preview may run a read-only FastAPI service:

- the same demo catalogue;
- the same artifact endpoints as the studio, but only for the published demo runs;
- no search start, no upload, no arbitrary path;
- a health endpoint;
- the lab's access gate in front;
- a read-only skin (`demo-visitor`) with no mutating action.

The service is not the studio with a public bind. It is a separate configuration and a separate action
allowlist.

## 7. Instance page

The page is a narrative, not a dashboard dump:

1. **Question.** The partner question and the decision.
2. **Context.** The corridor, the region, the data, and the caveats.
3. **Map.** The 2D corridor, the state, the plan, and the monitoring coverage.
4. **3D.** The terrain, vegetation, structures, and operations.
5. **Plan.** The timeline, the treatment units, and the cost build-up.
6. **Results.** The target charts, the Pareto front, and the comparison.
7. **What this shows.** Three to five bullets.
8. **What this does not show.** The data limits, the model limits, and the synthetic elements.
9. **What a pilot would need.** Data, access, time, and the deliverables.
10. **Pilot request.** The contact and the data-sharing path.

## 8. Pilot funnel

### 8.1 Pilot brief

A two-page brief:

- the partner's problem and the corridor;
- the decision to improve;
- the data the partner has and the data Brushline can supply;
- the pilot scope, duration, and deliverables;
- the success metrics;
- the security and data-sharing arrangement;
- the cost and the responsibilities.

### 8.2 Data-request checklist

- corridor geometry and asset class;
- management standard and clearance requirements;
- treatment history and methods;
- cost rates and contractor structure;
- access constraints and road status;
- inspection, LiDAR, or imagery;
- service, outage, or risk history;
- the decision owner and the reviewer.

### 8.3 Pilot scope

A first pilot is 6 to 8 weeks and covers one corridor or one region:

- build the instance;
- initialize the state;
- calibrate or validate the low-vegetation model on the partner's data where available;
- produce a strategic and a tactical plan;
- compare with the partner's current cycle;
- deliver the plan, the cost build-up, the evidence, and a review session.

### 8.4 Data-sharing boundary

- A public demo uses public or synthetic data only.
- A partner pilot uses a separate private deployment.
- The partner approves each connector and each derived output.
- Credentials stay in the partner's or the lab's secret store.
- No partner data enters the public portal, a prompt, or a tracked file.
- The pilot agreement names the data classification, retention, and publication rules.

## 9. Analytics and privacy

- Anonymous counts: page views, demo selections, and pilot-request clicks.
- No cookies or personal tracking without consent.
- No personal data in the repository.
- The pilot-request form collects only what is needed to reply.
- A privacy page states what is collected and why.
- The analytics are aggregate; they do not identify a visitor.

## 10. Deployment

### 10.1 Permanent portal

- Static export to `gh-pages` or GitHub Pages.
- A custom domain is optional.
- HTTPS.
- A `methods` page and a `privacy` page.
- A `health` check is not applicable to a static site; the build validation is the gate.

### 10.2 Lab preview

- A read-only FastAPI service in a container or systemd unit.
- Loopback bind inside the host; the lab access gate in front.
- A path-prefixed reverse proxy.
- A read-only mount of the demo artifacts.
- A health endpoint.
- No search start and no upload.

### 10.3 Port convention

The sibling portals use distinct local ports. Brushline should reserve one and record it in the README and
the deployment unit. The exact port is a Phase 11 decision.

## 11. Reuse

| Source | What Brushline reuses |
| --- | --- |
| WS4 public demo | The shell, the map, the period strip, the target charts, the comparison, the skins |
| FHOPS web | The run discovery, the 3D operations scene, the machine and crew timeline |
| Fresh Fire Studio | The static export, the 3D level-of-detail, the methods page, the public framing |
| Fresh Woodlots | The catalogue, the featured-pilot framing, the pilot brief, the demo script, the read-only deployment |
| Urban-forest lab | The shared 2D/3D selection, the vendored Three.js, the scenario time controls |

## 12. Acceptance criteria

- The public portal contains only public or synthetic data.
- Every demo has a valid `brushline.demo.v1` manifest.
- The static export works without a server.
- The optional service is read-only and allowlisted.
- Every demo page separates "what this shows" from "what this does not show".
- Every source has a licence and a version.
- The pilot-request path states what data is needed and how it is protected.
- The build fails on a broken link, a missing licence, a missing caveat, or a private-data marker.
- The dashboard is green.

## 13. Open questions

| Question | Resolve in |
| --- | --- |
| Which six demos make the strongest partner case? | P11 |
| Which demo is the first to build? | P11 |
| What is the permanent domain and hosting? | P11 |
| Which analytics are useful without tracking? | P11 |
| What is the pilot price and duration? | P11 and the maintainer |
| Which partner sectors are the first targets? | P11 |
| How is a demo retired when its data or model changes? | P11 and P14 |

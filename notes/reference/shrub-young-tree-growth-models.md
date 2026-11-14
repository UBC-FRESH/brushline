# Open Shrub and Young-Tree Growth Models: A Reuse Review

Status: draft for Phase 0 review
Date: 2026-11-14
Task: P0.12
Related: `notes/design/brushline-scope.md`, `notes/design/brushline-architecture.md`, ADR 0009

## 1. The decision this review informs

Brushline needs a model that predicts the height, cover, density, and resprouting of shrubs and young
trees along a corridor, and that changes those attributes when a treatment is applied. The obvious
question from a reviewer is: **why not reuse an existing open model?**

This review answers that question. It identifies the candidate models a reviewer would expect us to
consider, records their code and licence status, tests their fit against the Brushline decision problem,
and states what Brushline will reuse, what it will build, and what would change that decision.

The review is deliberately about the **low-vegetation state and its transitions**, not about whether a
general forest growth model is useful for the mature-tree component. Mature trees at the corridor edge
are a fall-in hazard and a seed source; they are not the primary managed state.

## 2. Method and limits

### 2.1 What was searched

- Web searches for shrub growth models, young-tree growth models, right-of-way vegetation models,
  powerline corridor vegetation models, shrub biomass accumulation, resprouting, fuel accumulation, and
  state-and-transition models.
- GitHub repository searches for shrub growth, vegetation dynamics, right-of-way vegetation, powerline
  vegetation, and shrub biomass.
- Publisher pages, open-access full text, code repositories, licence files, and model documentation.
- The IRSS x Silva21 expansion notes in this environment for the LiDAR, EFI, and forest-model context.

### 2.2 What was read

- Full text or abstract for the key papers.
- Source code and licence files where the repository was public.
- Model documentation for FVS/FFE, LANDIS-II, ST-Sim, VDDT, MEDFATE, FireBGCv2, PHYGROW, and the
  BC Hydro Integrated Vegetation Management Plan.
- The FVS Fire and Fuels Extension guide, including its statement that live herb and shrub fuels are not
  dynamically simulated.

### 2.3 What was not done

- This is not a systematic review or a meta-analysis.
- No model was run or benchmarked on Brushline data.
- Some papers are behind a paywall. They are marked **abstract only** or **pending library package**.
  The companion prompt `notes/reference/codex-library-search-prompt.md` asks the maintainer's Codex
  desktop agent to retrieve them through the university library.
- No third-party code, paper text, or documentation is copied into this repository.

### 2.4 Search date

The search was run on 2026-11-14. A later search may find a new open model. The decision is dated and
revisitable.

## 3. Bottom line

**No open, validated, segment-level shrub and young-tree growth model was found that also represents
right-of-way treatment transitions, infrastructure clearance and access, uncertainty, and the
observation-update loop.** The candidates fall into four groups:

1. **Tree-centric forest models** (FVS/FFE, TASS, VDYP/TIPSY, SORTIE-ND). They model trees well and
   shrubs poorly or not at all. FVS/FFE is public domain, but its guide states that live herb and shrub
   fuels are not dynamically simulated.
2. **Landscape succession models** (LANDIS-II, FireBGCv2). They are spatially explicit and can represent
   shrub or herb layers, but they operate at landscape scales and coarse time steps, are complex to
   parameterize, and are not built for a segment-level treatment and monitoring decision.
3. **State-and-transition frameworks** (ST-Sim, VDDT/Path). They provide the right conceptual shape but
   not a shrub growth model; ST-Sim is CC BY-ND 4.0, which blocks derivative reuse, and VDDT/Path are
   freeware without a reusable library.
4. **Component models** (MEDFATE shrub cohorts, Botequim shrub biomass accumulation, PHYGROW,
   empirical allometry and fuel curves, dynamic global vegetation models). They contain useful pieces,
   but none is a corridor management model.

**Decision:** build a lightweight, open, modular **low-vegetation state-transition model** as the
Brushline core, and reuse components where they are validated and licence-compatible:

- published allometric and biomass equations for functional groups;
- published growth, recovery, and fuel-accumulation relationships as priors;
- the cohort and state-transition concepts from MEDFATE, LANDIS-II, and the state-and-transition
  frameworks;
- the FVS/FFE shrub and fuel relationships as a comparison and prior, not as the runtime engine;
- LiDAR, field plots, and treatment history for calibration;
- Nemora for distribution fitting and uncertainty;
- `fresh-solutions` for schedule search.

The model will be benchmarked against the closest candidates (MEDFATE, FVS/FFE, and Botequim-type
biomass curves) on the same segments where the data allow. If a candidate outperforms the lightweight
model on the Brushline validation case, the decision changes.

## 4. Why the standard models miss the problem

The standard forest growth models are not defective. They are built for a different decision.

| Standard assumption | Brushline requirement | Consequence |
| --- | --- | --- |
| The tree is the managed object | The shrub and young-tree community is the managed object | Shrubs are a fuel pool, a competition term, or absent |
| Merchantable volume is the output | Height, cover, density, resprouting, and clearance are the outputs | A volume model cannot answer when the corridor closes |
| Stand or landscape scale | Segment scale along a corridor graph | Aggregation hides the treatment unit and the access constraint |
| Annual or decadal time step | 1 to 5 year treatment intervals, seasonal operations | A 10-year step cannot represent a 3-year cycle |
| Treatments are thinning or harvest | Mowing, brushing, herbicide, grazing, and selective removal | Method-specific efficacy and resprouting are missing |
| Natural succession is the driver | Management is the driver | The model does not represent the action being optimized |
| Calibration is mature-forest inventory | Calibration is low vegetation on rights-of-way | The model is outside its applicability domain |
| Uncertainty is a sensitivity table | Uncertainty is part of the state and the decision | The plan implies false precision |
| The model is the product | The plan, the bid, and the evidence are the product | A black-box growth model does not make the plan inspectable |

The most important defect is the **treatment transition**. A rights-of-way model must represent what
happens after cutting, mowing, or herbicide: top-kill, resprouting, regrowth delay, selectivity, and
the cost of the method. A forest growth model can simulate a thinning; it does not simulate the
repeated low-intensity treatment cycle that defines corridor management. The BC Hydro plan is explicit
that brushing alone can increase regrowth density and that the method and follow-up determine the next
cycle; that is a transition problem, not a yield-curve problem.

## 5. Candidate table

| Candidate | What it is | Code and licence | Shrub and young-tree handling | Treatment handling | Fit for Brushline |
| --- | --- | --- | --- | --- | --- |
| **MEDFATE** | Cohort-based Mediterranean forest function and dynamics, R/C++, annual steps with daily water/carbon | GPL (>= 2) or LGPL (>= 3), public GitHub and CRAN | Explicit shrub cohorts: species, density, cover, height; growth, mortality, recruitment | A user management function can cut shrub cover and plant cohorts; no method-specific efficacy or cost | **Closest open model.** Reuse concepts and benchmark; not the core because of R runtime, Mediterranean calibration, stand scale, and missing corridor/treatment-cost layer |
| **FVS + FFE** | Individual-tree, distance-independent forest growth; Fire and Fuels Extension | Public domain, Fortran, public GitHub | FFE carries herb and shrub fuel pools, but does not dynamically simulate live herb/shrub amounts; they change only with cover type/cover | Thinning, harvest, fuel treatments; no mowing/brushing/herbicide transition | Reuse fuel/shrub relationships as priors and benchmark; not the core |
| **LANDIS-II + Biomass Succession** | Landscape forest succession with cohort species and disturbances | Biomass Succession extension Apache-2.0, .NET, public GitHub | Shrub species can be represented as cohorts; not a management-scale shrub growth model | Disturbances and harvest; not ROW treatment methods | Reuse cohort concepts and parameters; not the core |
| **ST-Sim** | Spatially explicit state-and-transition simulation framework | CC BY-ND 4.0, public GitHub | User-defined states and transitions; no built-in shrub growth | User-defined transitions | Concept only; the ND licence blocks derivative reuse |
| **VDDT / Path** | State-and-transition landscape models, LANDFIRE reference models | Freeware, Windows, no reusable library | User-defined states and transitions | User-defined transitions | Concept and state-class design; not code |
| **FireBGCv2** | Mechanistic landscape fire, vegetation, climate, and fuel model, C++ | USDA FS research platform; source access is not a reusable library | Includes shrub and herb dynamics in a research model | Fire and management scenarios; not ROW treatment | Research reference; not the core |
| **TASS + Harper 2008** | BC Tree and Stand Simulator; used to model brushing/herbicide effects on crop trees | BC government model, not open source | Tree-centric; competing vegetation is a treatment effect on crop trees | Brushing, herbicide, manual, sheep, mulch in the Harper study | Treatment-response evidence and tree component; not shrub community |
| **VDYP / TIPSY** | BC natural and managed stand yield models | BC government tools, not open source | Tree yield only | Silvicultural treatments at stand level | Young conifer growth component only |
| **SORTIE-ND** | Spatially explicit individual-tree stand model | Source available on GitHub; licence not verified in this review | Tree-centric; understory light, not shrub community | Thinning and harvest | Competition/light concepts; not the core |
| **FORECAST** | Stand ecosystem model with light, nutrients, and competing vegetation | Code availability not verified | May represent competing vegetation; not a shrub management model | Silvicultural treatments | Nutrient/light competition concepts; not the core |
| **PHYGROW** | Daily hydrologically driven herb and shrub growth, rangeland/grazing | Windows model, not a reusable open library | Herb and shrub biomass | Grazing and forage management; not ROW | Daily growth concepts and priors; not the core |
| **Botequim et al. 2015** | Shrub biomass accumulation model for Portuguese understory | Paper CC BY-NC 4.0; equations, no reusable code found | Biomass as a function of stand basal area, resprouting share, temperature | Understory fuel treatment scheduling context; no method transition | Model form and prior; not directly transferable |
| **ORCHIDEE, LPJ-GUESS, ED2** | Dynamic global vegetation models with shrub PFTs | Open source (CeCILL, MPL-2.0, CC BY 4.0 respectively) | Shrub PFTs and cohorts | Land use and disturbance, not ROW treatment | PFT concepts, climate response, allometry; not the core |
| **ArcVeg** | Nutrient-based Arctic plant community model with shrub PFTs | Research model; code availability not established | Shrub PFTs | Climate and nutrient scenarios | Functional-group concepts; not the core |
| **Powerline tree growth + LiDAR** | Tree height growth (Richards) with UAV LiDAR for encroachment | Paper-specific; code availability not established | Tree height only | Clearance prediction, not treatment transition | Tree encroachment component and observation operator |
| **PLS-CADD grow-in** | Proprietary transmission-line engineering software with grow-in and falling-tree checks | Proprietary | Individual trees and clearance | Engineering checks, not vegetation community management | Industry benchmark; not reusable |
| **BC Hydro IVMP** | Public operator plan for integrated vegetation management | Public document, not a model | Describes target and compatible vegetation, growth rates, cycles | Describes brushing, mowing, herbicide, cycles, and regrowth | Domain evidence and validation targets |
| **Empirical allometry and fuel curves** | Biomass, fuel load, and fuel accumulation equations | Public equations; licence varies by source | Biomass/fuel, not height/cover dynamics | None | Reusable components and priors |

## 6. Detailed assessments

### 6.1 MEDFATE: the closest open model

MEDFATE is a cohort-based model of Mediterranean forest function and dynamics. It simulates daily water
and carbon balance, annual growth, mortality, recruitment, and optional management. Its `fordyn` output
includes a `ShrubTable` with shrub species, density, cover, and height, and a `CutShrubTable` when shrubs
are cut. That is much closer to the Brushline state than any tree yield model.

Why it is not the Brushline core:

- **Runtime and language.** It is an R/C++ package with a daily water/carbon balance. A metaheuristic
  search evaluates thousands of schedules; calling an R process per segment per year is not practical.
  A precomputed curve table would remove much of the dynamic behaviour that makes MEDFATE valuable.
- **Calibration domain.** Its parameters are for Mediterranean species, particularly Spain. Brushline's
  first cases are BC/PNW corridors. Recalibrating MEDFATE for BC shrubs and young trees is a research
  project, not an integration.
- **Scale and decision.** It is a stand model. It has no corridor graph, no segment-level access, no
  infrastructure clearance standard, no contractor cost, and no monitoring decision.
- **Treatment model.** Management is a user function that cuts shrub cover. It does not carry method-specific
  efficacy, selectivity, seasonality, resprouting, or cost.
- **Licence.** The package is dual-licensed GPL (>= 2) or LGPL (>= 3). The LGPL path may permit a
  process-level or dynamic-link adapter, but a Python core that embeds R would still carry a heavy
  runtime and licensing boundary.

What Brushline will reuse from MEDFATE:

- the cohort representation of shrub and tree layers;
- the separation of growth, mortality, recruitment, and management;
- the idea of an explicit cut table and a dead-shrub table;
- the benchmark: on a segment with comparable data, does the Brushline state-transition model reproduce
  MEDFATE's shrub cover and height trajectory within a stated tolerance?
- an optional high-fidelity adapter for a single stand, if a partner needs it and accepts the R runtime.

This is the candidate that most needs a direct answer in the report. The answer is: **we evaluated it,
it is the closest open model, and we will benchmark against it; we are not embedding it because the
runtime, calibration domain, and decision scale do not fit the search loop.**

### 6.2 FVS and the Fire and Fuels Extension

FVS is a family of individual-tree, distance-independent forest growth models. It is public domain,
which makes it the most reusable of the standard models. The Fire and Fuels Extension adds fuel
dynamics and fire behaviour.

The FFE guide states that FFE does not dynamically simulate amounts of live fuel such as herbs and
shrubs; the values are derived from cover type and only change when the cover or type changes. It also
describes live herb and shrub fuels as poorly represented. This is the central defect for Brushline: the
managed state is exactly the live low vegetation that FFE does not grow.

FVS also operates on tree lists and stand-level silvicultural treatments. It has no mowing, brushing, or
herbicide transition with resprouting, and no corridor clearance or access objective.

What Brushline will reuse:

- FFE's fuel-loading and shrub-cover relationships as a prior or comparison where the cover type maps;
- the individual-tree allometry and crown relationships for the mature-tree edge;
- FVS as a benchmark for the tree component, not for the shrub state.

### 6.3 LANDIS-II

LANDIS-II is a spatially explicit landscape succession model. The Biomass Succession extension is
Apache-2.0 and uses species-age cohorts; shrubs can be represented as species or cohorts. The model is
built for landscape-scale, long-horizon succession and disturbance, not for a segment-level treatment
cycle.

The cohort concept is useful. The model is not: it is a .NET landscape engine with 10-year time steps,
large parameter sets, and a disturbance/ succession focus. Making it answer "should we mow this 400 m
segment in year 3 or 5, and what does it cost" would require a new decision layer and a new calibration.

What Brushline will reuse:

- the cohort and species-parameter concepts;
- the disturbance and succession framing for the hazard layer;
- published species parameters as candidate priors, subject to BC applicability.

### 6.4 ST-Sim, VDDT, and Path

ST-Sim is an open-source SyncroSim package for state-and-transition simulation. Its framework is a good
conceptual match: states, transitions, probabilities, spatial units, and management actions. But it is
a framework, not a shrub growth model; the transitions and states are user-defined.

Its licence is CC BY-ND 4.0. That licence permits sharing of the unmodified material but not derivative
works. Brushline cannot embed or modify ST-Sim code without a separate permission. That is a decisive
constraint for a software dependency.

VDDT and Path are freeware Windows tools with no reusable library. They are useful as design references
for state classes and transition diagrams, not as runtime components.

What Brushline will reuse:

- the state-and-transition vocabulary;
- the state-class and transition-diagram design method;
- the LANDFIRE/ecological-site reference models as a source of state hypotheses, not as BC parameters.

### 6.5 TASS, VDYP/TIPSY, and the BC treatment literature

TASS is BC's Tree and Stand Simulator. Harper (2008) used TASS to model vegetation-management treatments
and their effect on crop trees. That is valuable evidence for treatment response, but it is tree-centric:
the question is how brushing affects the planted crop, not how the shrub community grows and resprouts.

VDYP and TIPSY are BC yield models for natural and managed stands. They are the right tools for the
mature-tree and young-conifer component, and FEMIC already uses them. They do not model shrubs.

What Brushline will reuse:

- the BC treatment-response evidence from Harper and the BC brushing literature;
- the young-conifer growth component through the FEMIC/VDYP/TIPSY lane;
- the treatment method categories and cycle lengths from the BC Hydro plan as domain evidence.

### 6.6 FireBGCv2

FireBGCv2 is a C++ research platform that mechanistically simulates fire, vegetation, climate, and fuel
dynamics across landscapes. It includes shrub and herb dynamics and is a serious research tool. It is not
a reusable library for a segment-level decision support system, and its parameterization burden is high.
It is a reference for process representation, not a runtime dependency.

### 6.7 PHYGROW

PHYGROW is a daily, hydrologically driven herb and shrub growth model used in grazing and rangeland
assessment. It models above-ground herb and shrub growth, forage consumption, and hydrology. It is a
Windows model, not a reusable open library, and its calibration is for rangeland forage, not corridor
vegetation. The daily growth and water-balance concepts are useful; the model is not a fit.

### 6.8 Botequim et al. (2015): shrub biomass accumulation

Botequim et al. modelled shrub biomass accumulation in Portuguese understory as a function of stand basal
area, the percentage of resprouting species, and mean annual temperature. The paper is open access under
CC BY-NC 4.0. It is one of the few published shrub growth models, and it directly supports the idea that
resprouting strategy and climate drive accumulation.

It is not a Brushline model:

- it predicts biomass, not height, cover, density, or clearance;
- it is calibrated to Portuguese Mediterranean forests, not BC/PNW;
- it has no treatment transition, cost, access, or monitoring;
- the CC BY-NC licence is not a permissive software licence.

What Brushline will reuse:

- the model form: a saturating accumulation curve with a resprouting share and a climate modifier;
- the resprouting dichotomy as a functional-group parameter;
- the paper as a prior and a benchmark for the biomass trajectory.

### 6.9 Dynamic global vegetation models

ORCHIDEE, LPJ-GUESS, and ED2 are open, process-based models with shrub plant functional types. They are
built for regional to global vegetation and climate questions. They are valuable for trait and climate
response concepts, but they are not management models: they do not represent a 400 m corridor segment, a
mowing treatment, a contractor cost, or a clearance standard. Their calibration and computational cost
are far beyond a segment-level search loop.

What Brushline will reuse:

- functional-group traits and climate-response shapes as candidate priors;
- allometric relationships where they are species- and region-appropriate;
- a benchmark for the direction of climate sensitivity, not for the absolute trajectory.

### 6.10 Utility and powerline tools

The powerline literature is mostly about **tree encroachment**, not shrub community dynamics. Chen et al.
(2022) combine a Richards tree-height growth model with UAV LiDAR to detect encroachment. PLS-CADD has
grow-in and falling-tree checks. Utility analytics vendors sell machine-learning growth predictions.
These are useful for the mature-tree edge and for the observation operator, but they do not model the
shrub and young-tree state or the treatment transition.

The BC Hydro Integrated Vegetation Management Plan is a public operator document, not a model. It is
valuable because it states the real decision context: transmission cycles of roughly 4 to 12 years,
distribution cycles of roughly 3 to 7 years, growth rates and clearance determining the cycle, and
brushing alone sometimes increasing regrowth density. Those are validation targets and transition
hypotheses for Brushline.

### 6.11 Empirical allometry and fuel curves

There is a large literature on shrub biomass equations, fuel load, and fuel accumulation. These are
components, not dynamic management models. They are useful for converting a state to biomass or fuel,
and for comparing predicted fuel loads with FFE or other fuel models. They do not predict height, cover,
or resprouting through time, and they do not respond to treatment.

## 7. What Brushline will reuse

| Component | Source examples | How Brushline uses it |
| --- | --- | --- |
| Cohort representation | MEDFATE, LANDIS-II | Shrub and tree cohorts with species/functional group, density, cover, height |
| State-and-transition design | ST-Sim, VDDT, LANDFIRE | State classes, transition diagrams, management actions |
| Shrub biomass accumulation form | Botequim et al. 2015 | Saturating curve with resprouting share and climate modifier, refit for BC |
| Fuel and shrub cover relationships | FVS/FFE | Prior and benchmark for fuel load and cover |
| Tree allometry and crown relationships | FVS, TASS, VDYP/TIPSY | Mature-tree edge and fall-in hazard |
| Treatment response evidence | Harper 2008, BC Hydro IVMP, BC brushing literature | Method categories, efficacy priors, cycle lengths |
| Functional-group traits | ORCHIDEE, LPJ-GUESS, ED2 | Climate response and allometric priors |
| Observation operator | LiDAR/EFI work, Chen et al. 2022 | Height/cover observation error and detection |
| Distribution fitting | Nemora | Parameter and residual distributions |
| Schedule search | Fresh Solutions | Treatment and monitoring optimization |
| Validation data | Field plots, LiDAR, treatment history | Calibration, holdout, and benchmark |

## 8. The Brushline low-vegetation model

### 8.1 Model form

A modular state-transition model with:

- functional groups: shrub, deciduous sprout, conifer, grass/herb, and site-specific additions;
- state variables: height, cover, density or biomass, age since disturbance, treatment history;
- growth: a saturating height/cover curve with site and climate modifiers, competition, and
  functional-group-specific parameters;
- treatment: a transition that reduces height/cover and sets a regrowth delay or resprouting multiplier,
  with method-specific efficacy and cost;
- hazard: clearance, fall-in, fuel connectivity, access;
- uncertainty: parameter and residual distributions, updated by observations;
- domain: species, region, age, height, and data vintage, recorded in a model card.

### 8.2 Why this is not "from scratch" in the wasteful sense

The core state machine is new because no candidate provides it. The components are reused:

- the curve forms and priors come from published shrub growth and biomass work;
- the fuel and cover relationships come from FVS/FFE and the fuel literature;
- the cohort and transition concepts come from MEDFATE, LANDIS-II, and the state-and-transition
  frameworks;
- the calibration data comes from field plots, LiDAR, and treatment history;
- the fitting uses Nemora, and the search uses Fresh Solutions.

The novelty is the **integration**: a segment-level low-vegetation state with method-specific treatment
transitions, infrastructure service levels, uncertainty, and observation updates, inside a corridor
optimizer. That integration is the product, and no candidate provides it.

### 8.3 Validation plan

- Hold out field plots by site and by year.
- Compare predicted height and cover by functional group against observed plots.
- Compare the biomass trajectory against Botequim-type curves and FVS/FFE fuel loads where the data
  allow.
- Benchmark the shrub trajectory against MEDFATE on a stand with compatible parameters, with the
  transfer limits stated.
- Test the treatment transition against recorded brushing, mowing, and herbicide outcomes.
- Report error by functional group, height class, and time since treatment.
- Publish a model card with the applicability domain.

### 8.4 What would change the decision

- An open, validated, BC/PNW shrub and young-tree model with segment-level state, treatment
  transitions, and a permissive licence appears.
- A candidate can be parameterized for BC species with existing data and passes the Brushline validation
  case.
- A partner provides a calibrated model and a code licence that permits embedding.
- The lightweight model fails the validation case and a candidate passes it at an acceptable runtime.

If one of these happens, Brushline should adopt or wrap the candidate and retire the duplicate core.

## 9. The elevator answer

> We did not ignore the existing models. FVS/FFE is public domain, but its own guide says it does not
> dynamically simulate live herb and shrub fuels; they are derived from cover type. LANDIS-II is a
> landscape succession model, ST-Sim is a state-and-transition framework under a no-derivatives licence,
> TASS and VDYP/TIPSY are tree yield models, and MEDFATE is the closest open shrub-cohort model but it is
> an R/MEDFATE Mediterranean stand model with no corridor, treatment-cost, or clearance layer. We reuse
> their equations, priors, and concepts, and we benchmark against MEDFATE and FVS/FFE. We are building
> the segment-level state-transition and treatment layer that none of them provides, because that layer
> is the decision we are trying to support.

## 10. Evidence gaps and the library-search prompt

The following are the highest-value items to retrieve through the university library:

1. The FORCHANGE technical report on the shrub growth model in understory conditions (Botequim et al.
   2009), which underlies the 2015 biomass paper.
2. The full text of the FVS/FFE shrub and fuel sections, if the public guide is incomplete.
3. The MEDFATE model description paper (GMD 2023) and the shrub parameter sources for Mediterranean
   species.
4. The BC Hydro IVMP appendices and any BC Hydro vegetation growth-rate reports.
5. The BC brushing and vegetation-management literature, including Harper (2008) and the BC Ministry of
   Forests guidance.
6. Powerline vegetation growth and LiDAR papers, including Chen et al. (2022) and the 2025 review.
7. Any open-source shrub cohort model not found in the web and GitHub searches.

The prompt in `notes/reference/codex-library-search-prompt.md` asks the maintainer's Codex desktop agent
to search the library, download the papers into a package with a metadata manifest, and return summaries
without copying copyrighted text into the repository.

## 11. References

### Models and code

- USDA Forest Service. *Forest Vegetation Simulator*. GitHub.
  <https://github.com/USDAForestService/ForestVegetationSimulator>
- USDA Forest Service. *The Fire and Fuels Extension to the Forest Vegetation Simulator*.
  <https://www.fs.usda.gov/sites/default/files/forest-management/fvs-ffe-guide.pdf>
- LANDIS-II Foundation. *LANDIS-II forest landscape model*. <https://www.landis-ii.org/>
- LANDIS-II Foundation. *Biomass Succession Extension*.
  <https://landis-ii-foundation.github.io/Extension-Biomass-Succession/>
- ApexRMS. *ST-Sim*. GitHub. <https://github.com/ApexRMS/stsim>; documentation
  <https://docs.stsim.net/>
- ESSA Technologies. *Vegetation Dynamics Development Tool (VDDT)*.
  <https://www.essa.com/explore-essa/tools/vddt/>
- USDA Forest Service. *FireBGCv2 landscape fire model*.
  <https://research.fs.usda.gov/firelab/products/dataandtools/firebgcv2-landscape-fire-model>
- BC Ministry of Forests. *Tree and Stand Simulator (TASS)*.
  <https://www2.gov.bc.ca/gov/content/industry/forestry/managing-our-forest-resources/forest-inventory/growth-and-yield-modelling/tree-and-stand-simulator-tass>
- CREAF. *MEDFATE: Mediterranean forest simulation*. GitHub.
  <https://github.com/emf-creaf/medfate>; documentation
  <https://emf-creaf.github.io/medfate/>
- Texas A&M AgriLife. *PHYGROW*. <https://blackland.tamu.edu/models/phygrow/>
- ED2. *Ecosystem Demography model*. GitHub. <https://github.com/EDmodel/ED2>
- ORCHIDEE. *Land surface model*. <https://orchidee.ipsl.fr/>
- LPJ-GUESS. *Lund-Potsdam-Jena General Ecosystem Simulator*.
  <https://gmd.copernicus.org/articles/15/6709/2022/>

### Literature

- Botequim, B., Zubizarreta-Gerendiain, A., Garcia-Gonzalo, J., Silva, A., Marques, S., Fernandes, P.
  M., Pereira, J. M. C., and Tomé, M. (2015). A model of shrub biomass accumulation as a tool to support
  management of Portuguese forests. *iForest* 8: 114-125.
  <https://doi.org/10.3832/ifor0931-008>
- Botequim, B., Borges, P., Carreiras, J., Oliveira, M. M., and Borges, J. (2009). Development of a shrub
  growth model in understory conditions (preliminary model). Technical Report 7, FORCHANGE, Instituto
  Superior de Agronomia, Lisboa. (Cited in Botequim et al. 2015; pending library package.)
- De Cáceres, M., Molowny-Horas, R., Cabon, A., Martínez-Vilalta, J., Mencuccini, M., García-Valdés, R.,
  Nadal-Sala, D., Sabaté, S., Martin-StPaul, N., Morin, X., D'Adamo, F., Batllori, E., and Améztegui, A.
  (2023). MEDFATE 2.9.3: a trait-enabled model to simulate Mediterranean forest function and dynamics at
  regional scales. *Geoscientific Model Development* 16: 3165-3201.
  <https://doi.org/10.5194/gmd-16-3165-2023>
- Harper, G. J. (2008). Modelling vegetation management treatments with the Tree and Stand Simulator.
  *The Forestry Chronicle* 84(5): 749-757. <https://doi.org/10.5558/tfc84053-1>
- BC Hydro. *Integrated Vegetation Management Plan, 2022-2027*.
  <https://www.bchydro.com/content/dam/BCHydro/customer-portal/documents/corporate/safety/powerline-ivmp-2022-2027-confirmed-nov.2-2022.pdf>
- Chen, Y., et al. (2022). Early detection of tree encroachment in high voltage powerline corridor using
  growth model and UAV-borne LiDAR. *International Journal of Applied Earth Observation and
  Geoinformation*. <https://www.sciencedirect.com/science/article/pii/S0303243422000666>
- Bahreini, F., et al. (2025). Detection of vegetation proximity to power lines: critical review.
  *Forests* 16(11): 1658. <https://www.mdpi.com/1999-4907/16/11/1658>
- Garfinkel, M., et al. (2023). Balancing the management of powerline right-of-way vegetation.
  *Journal of Environmental Management*. <https://pubmed.ncbi.nlm.nih.gov/36610195/>
- NERC. *FAC-003-5 Transmission Vegetation Management*.
  <https://www.nerc.com/globalassets/standards/reliability-standards/fac/fac-003-5.pdf>
- Power Line Systems. *Transmission and Distribution Line Vegetation Management in PLS-CADD*.
  <https://www.powline.com/technotes/Transmission_&_Distribution_Line_Vegetation_Management_in_PLS-CADD.pdf>
- Right-of-Way Stewardship Council. *Integrated Vegetation Management*.
  <https://rowstewardship.org/ivm.php>

### Search note

- The web and GitHub searches were run on 2026-11-14. The search was not exhaustive; the library prompt
  is the next step for the paywalled and grey literature.

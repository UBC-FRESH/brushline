# Codex Library Search Prompt: Shrub and Young-Tree Growth Models

Copy the block below into the Codex desktop agent that has university library access. It asks for a
download package and a summary manifest. Do not paste library credentials or personal paths into this
repository.

---

## Prompt

You are a research librarian assistant working for the UBC FRESH Lab on a software project called
Brushline. Brushline is a decision support system for vegetation management along linear infrastructure
corridors. We need a defensible literature package on **shrub and young-tree growth models**, including
the models that a reviewer would expect us to reuse.

Your job is to search the university library and the public web, retrieve the highest-value papers, and
return a self-contained package with PDFs and structured summaries. Do not modify the Brushline
repository. Do not paste copyrighted text into any tracked file. Do not use Sci-Hub or any unlicensed
source.

### Access rules

- Use the university library's licensed subscriptions, the library proxy, and interlibrary loan only
  where the licence permits it.
- Prefer the publisher's version of record. If only an accepted manuscript is available, label it.
- Record whether each item is open access, library-licensed, or unavailable.
- Ask me before purchasing an article, requesting an interlibrary loan, or downloading more than 500 MB.
- Do not include my name, institution credentials, library barcode, or personal file paths in the
  package metadata.
- Keep the PDFs outside the Brushline repository. The package is for my local review.

### Search questions

For each paper or model, answer:

1. What is the model or model family, and what does it predict?
2. What are the state variables (height, cover, density, biomass, age, functional group, species)?
3. What are the spatial scale and time step?
4. How does it represent shrubs and young trees, as opposed to mature trees?
5. How does it represent treatment: cutting, mowing, brushing, herbicide, grazing, fire, or none?
6. Does it represent resprouting, regrowth delay, selectivity, or treatment efficacy?
7. What calibration and validation data were used, and what is the reported error?
8. Is the code available? Under what licence? Is it a library, a CLI, or a research script?
9. Is it applicable to British Columbia, the Pacific Northwest, or boreal/temperate corridors?
10. What would prevent us from reusing it in a Python decision support system?

### Priority searches

Run these queries in the library discovery layer and in Google Scholar, Web of Science, Scopus, and
CAB Direct where available. Add synonyms and truncation.

**Shrub growth and dynamics**
- shrub growth model
- shrub biomass accumulation model
- shrub cohort model
- shrub resprouting model
- shrub growth and mortality model
- understory shrub dynamics model
- early successional shrub model
- shrub encroachment model
- shrub fuel accumulation model
- shrub allometry growth model

**Young trees and regeneration**
- young tree growth model
- regeneration and early stand dynamics model
- sapling growth competition model
- free-growing stand model
- brushing and crop tree response model
- vegetation management treatment response model

**Rights-of-way and infrastructure**
- right-of-way vegetation management model
- powerline corridor vegetation growth model
- transmission corridor vegetation simulation
- pipeline right-of-way vegetation model
- utility vegetation management decision support
- integrated vegetation management model
- clearance prediction vegetation power line
- LiDAR vegetation encroachment power line
- vegetation growth model railway corridor
- roadside vegetation growth model

**Model families to check**
- Forest Vegetation Simulator (FVS) and the Fire and Fuels Extension (FFE), especially shrub and herb
  fuel dynamics
- LANDIS-II and its succession extensions, especially shrub representation
- ST-Sim and SyncroSim state-and-transition models
- VDDT and Path landscape models
- MEDFATE and medfateland
- FireBGCv2
- PHYGROW
- FORECAST
- TASS and the BC vegetation-management treatment literature
- VDYP and TIPSY
- SORTIE-ND
- ORCHIDEE, LPJ-GUESS, ED2, and other DGVMs with shrub PFTs
- ArcVeg and Arctic shrub models
- Botequim et al. shrub biomass accumulation and the FORCHANGE technical report
- fuel accumulation and shrub allometry literature
- powerline tree-height growth + LiDAR encroachment papers
- PLS-CADD vegetation checks and industry practice
- BC Hydro Integrated Vegetation Management Plan and BC brushing guidance

### Target items to retrieve first

Retrieve these if they are available. If a DOI or exact title differs, find the closest match and say so.

1. Botequim, B., Borges, P., Carreiras, J., Oliveira, M. M., and Borges, J. (2009). *Development of a
   shrub growth model in understory conditions (preliminary model).* Technical Report 7, FORCHANGE,
   Instituto Superior de Agronomia, Lisboa.
2. Botequim, B., et al. (2015). A model of shrub biomass accumulation as a tool to support management of
   Portuguese forests. *iForest* 8: 114-125. DOI 10.3832/ifor0931-008.
3. De Cáceres, M., et al. (2023). MEDFATE 2.9.3: a trait-enabled model to simulate Mediterranean forest
   function and dynamics at regional scales. *Geoscientific Model Development* 16: 3165-3201.
   DOI 10.5194/gmd-16-3165-2023.
4. Harper, G. J. (2008). Modelling vegetation management treatments with the Tree and Stand Simulator.
   *The Forestry Chronicle* 84(5): 749-757. DOI 10.5558/tfc84053-1.
5. The FVS Fire and Fuels Extension guide, especially the sections on live herb and shrub fuels.
6. The LANDIS-II Biomass Succession and PnET-Succession user guides, especially shrub parameters.
7. The ST-Sim and VDDT documentation on state-and-transition model design.
8. The BC Hydro Integrated Vegetation Management Plan, 2022-2027, and any appendices on growth rates,
   cycles, and treatment methods.
9. Chen, Y., et al. (2022). Early detection of tree encroachment in high voltage powerline corridor using
   growth model and UAV-borne LiDAR. *International Journal of Applied Earth Observation and
   Geoinformation*.
10. Bahreini, F., et al. (2025). Detection of vegetation proximity to power lines: critical review.
    *Forests* 16(11): 1658.
11. Any paper that reports a shrub growth model for BC, the Pacific Northwest, or boreal rights-of-way.
12. Any open-source shrub cohort or shrub growth model not listed above.

### Output package

Create a directory named `brushline-shrub-lit-package/` under `<DOWNLOAD_DIR>` with this structure:

```text
brushline-shrub-lit-package/
  README.md
  metadata.csv
  summaries.md
  gaps.md
  manifest.sha256
  pdf/
    <first-author><year>_<short-title>.pdf
```

#### `metadata.csv`

One row per item, with these columns:

```text
id,title,authors,year,journal,doi,url,access_status,licence,item_type,model_name,code_available,code_licence,state_variables,spatial_scale,time_step,treatment_representation,calibration_data,validation_metric,bc_pnw_applicability,relevance,notes
```

Use `unknown` or `not_reported` rather than guessing. `access_status` is one of `open`, `library`,
`abstract_only`, or `unavailable`. `item_type` is one of `paper`, `report`, `model_docs`, `code`, or
`standard`.

#### `summaries.md`

For each item, a 150-250 word summary in your own words with these headings:

```markdown
## <id>: <short title>

- Citation:
- What it models:
- State variables:
- Scale and time step:
- Shrub and young-tree handling:
- Treatment representation:
- Calibration and validation:
- Code and licence:
- BC/PNW applicability:
- Reuse assessment:
- What would change the assessment:
```

Do not copy the abstract. Paraphrase. If you only had the abstract, say so.

#### `gaps.md`

List the questions the package could not answer, the papers that were unavailable, and the searches
that returned nothing useful. Name the next search or the interlibrary loan request.

#### `manifest.sha256`

SHA-256 for every PDF and for `metadata.csv`, `summaries.md`, and `gaps.md`.

#### `README.md`

State the search date, the databases used, the number of items, the access breakdown, and the package
contents. Do not include personal or institutional credentials.

### Quality rules

- Every claim in `summaries.md` must be traceable to the paper or the code documentation.
- Do not invent a model, a coefficient, a licence, or a validation result.
- If a paper is paywalled and the library cannot supply it, mark it `unavailable` and explain.
- If a code repository has no licence file, say `no licence file found`, not `open source`.
- If a model is a framework rather than a growth model, say so.
- If a model is calibrated outside BC/PNW, say so and name the calibration region.
- Prefer the version of record; label preprints and accepted manuscripts.
- Do not include copyrighted figures or long quotations in the package.

### Return

When the package is complete, return:

1. The absolute path to the package directory.
2. The number of items by access status.
3. The five most important findings for Brushline.
4. The three biggest evidence gaps.
5. A list of items that need my approval (purchase, interlibrary loan, or a large download).

Do not modify the Brushline repository. I will upload the package to the project environment for the
next review step.

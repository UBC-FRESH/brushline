# MKRF field validation kit

## Purpose

The kit converts the MKRF corridor demo into a field-verifiable campaign. It carries planned plot
locations, the 2016 LiDAR targets those plots are meant to test, printable cards, an offline map, and
an import validator. It does not establish a treatment prescription or an approved work plan.

## Scope

- Two treatment units remain inside the modelled terrain block: SW-01 (2027) and SW-02 (2028).
- Twelve plots are planned, six per unit, alternating corridor centre and edge.
- SW-03 was removed from the field design and from the current schedule because its clipped fragment
  lies outside the modelled terrain block and cannot support plots or terrain sampling.
- Plot targets are 2016 LiDAR-derived shrub patch count, mean cover, maximum shrub height, tree-clump
  count, and canopy height. They are baselines, not ground truth.

## Outputs

The generated kit is private and lives under ignored runtime storage:

`runtime/private/mkrf-powerline/field-kit/`

It contains:

- `map.png` and `map.pdf`
- `plots.csv`
- `corridor-plots.geojson`
- `plot-cards.html` and `plot-cards.pdf`
- `field-observations-template.csv`
- `photo-log.csv`
- `README.md` and `validate.md`
- `field-kit.zip`

No MKRF coordinates, plot targets, or field kit payload are tracked in the repository.

## Import and comparison gates

The committed `brushline field validate` command checks required columns, known plot IDs, planned
unit and position, duplicate observations, GPS distance to the planned plot, numeric/date ranges, and
photo IDs. It writes normalized JSON for later calibration. See
`docs/reference/field-validation.rst` and `docs/api/field.rst`.

The committed `brushline field compare` command compares that normalized JSON with the planned plot
targets. It reports cover and height residuals, unit bias/MAE/RMSE, sample-size gates, review
multipliers, and an explicit `not_tested` treatment-response status. It does not apply corrections
automatically. See `docs/reference/field-comparison.rst` and `docs/api/field-comparison.rst`.

## Evidence

- `python scripts/dashboard.py`: `OVERALL: GREEN`.
- `pytest`: 790 passed, 96.84 percent coverage after the comparison addition.
- End-to-end smoke test: a filled template row validated against the generated GeoJSON and wrote
  normalized JSON successfully.
- The private kit was generated with 12 plots, two scheduled units, and a 2.8 MB archive.

## Limits

- No field data has been collected yet.
- The tests validate schema and planned-reference consistency, not measurement accuracy.
- The schedule remains modelled; plot results have not been calibrated into treatment efficacy.
- Field work must follow MKRF access rules and the asset owner's electrical-safety rules.
- Data-sharing and release approval remain required before any MKRF-derived content is made public.

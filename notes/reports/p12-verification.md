# P12 verification report

## Criteria

| # | Criterion | Status | Evidence | Gap |
| --- | --- | --- | --- | --- |
| 1 | End-to-end synthetic corridor | met | fixture/CLI/studio tests and run artifacts | Synthetic evidence only. |
| 2 | Growth and treatment validation | partial | P4 held-out synthetic validation and model card | No field plots. |
| 3 | FEMIC-extended instance builder | partial | P2 provider pin, template, catalogue, fetch and capability tests | No live FEMIC/FreshForge build. |
| 4 | Agent capability | met | P2.6 offline fake provider and validators | Offline harness. |
| 5 | LiDAR state initialization | partial | P3 LiDAR/terrain/canopy/state/coverage contracts | No live bundle in this verification run. |
| 6 | Low-vegetation calibration | not_met | P4 synthetic calibration and model-card domain | No field calibration or mature-EFI transfer. |
| 7 | Demo portal | met | P11 static five-instance synthetic portal and validation | Public/synthetic only. |
| 8 | Exact small-instance check | met | P5 tiny optimum and exact replay | 324 assignments. |
| 9 | Search quality under a stated budget | partial | P5 tiny/local budget and archive tests | No broad validation set. |
| 10 | Business-as-usual comparison | met | P6 case: optimized 0.707/920, BAU 0.413/360 | Synthetic case. |
| 11 | Monitoring value | met | P8 adaptive 5.0 vs fixed 1.33 regret/dollar | Synthetic expected-loss proxy. |
| 12 | Owner-contractor agreement | met | P9 plan 120 reproduced; bid differences traced | Synthetic rates. |
| 13 | Studio contract | met | P10 artifact-only API and read-only reviewer skin tests | Static/synthetic content. |
| 14 | Reproducibility | met | P6 scenario portfolio/report digests replayed twice | Same case and seed. |
| 15 | Scale | not_met | Measured small-case build: 0.033s for 10 periods/3 segments | 10,000 segments/1,000 evaluations/8-core target not attempted. |
| 16 | Quality gates | met | pytest, coverage, validator and docs gates | Local dashboard green. |

## BAU case

{
  "optimized_service": 0.7066666666666669,
  "optimized_cost": 920.0,
  "bau_service": 0.41266666666666674,
  "bau_cost": 360.0
}

## Monitoring value

{
  "adaptive_regret_per_dollar": 5.0,
  "fixed_regret_per_dollar": 1.3333333333,
  "beats_calendar": true
}

## Owner-contractor exchange

{
  "plan_cost": 120.0,
  "same_artifact": true,
  "attributable": true
}

## Performance and scale

{
  "segments": 3,
  "periods": 10,
  "seconds": 0.0331,
  "target_segments": 10000,
  "target_met": 0.0
}

## Reproducibility

Replayed: True

## Recommendation

Release candidate for an internal prototype, not a production or field-calibrated release. Close the field-calibration and scale gaps before a public operational claim.

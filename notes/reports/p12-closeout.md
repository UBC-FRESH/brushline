# Phase close-out report: P12 Verification and the BAU case

Parent issue: #112
Pull request: pending
Evidence head: `568234a`
Status: queued for approval. Not merged.

P12.1–P12.7 are delivered. The 16-criterion verification report is `notes/reports/p12-verification.md`; the machine record is `notes/reference/p12-verification.v1.json`.

Verified: optimized service 0.707 vs BAU 0.413; costs 920 vs 360; monitoring regret/dollar 5.0 vs 1.33; owner-contractor plan cost 120 with attributable bid differences; deterministic replay. Named gaps: field calibration and mature-EFI transfer are not met; the 10,000-segment/1,000-evaluation/8-core target is not attempted (small-case measurement only). Recommendation: internal prototype release candidate, not a production or field-calibrated release.

Local dashboard `OVERALL: GREEN`; pytest 775 passed with 98% coverage. No merge, branch deletion, parent close, tag, release, or settings change has been performed.

Recommendation: merge, close #112, and launch P13 (Release and deploy) only after accepting the stated gaps.

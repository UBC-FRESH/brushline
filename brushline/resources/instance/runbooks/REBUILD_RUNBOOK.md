# Brushline instance rebuild runbook

This runbook covers the FEMIC stages and the Brushline provider stages.

## 1. FEMIC preflight

```bash
femic prep validate-case --run-config config/run_profile.case_template.yaml
femic prep geospatial-preflight
```

## 2. FEMIC rebuild

```bash
femic instance validate-spec --instance-root . --spec config/rebuild.spec.yaml
femic instance rebuild \
  --instance-root . \
  --spec config/rebuild.spec.yaml \
  --baseline config/rebuild.baseline.json \
  --allowlist config/rebuild.allowlist.yaml
```

The FEMIC spec intentionally contains only FEMIC stages. FEMIC's rebuild runner owns that stage list.

## 3. Brushline extension

Review `config/brushline/rebuild.steps.yaml`. It lists the provider stages:

- `brushline.validate_aoi`
- `brushline.segment_corridor`
- `brushline.compile_dataset`
- `brushline.seed_vegetation_state`
- `brushline.validate_scenario`
- `brushline.build_demo` (optional)

The provider nodes call the Brushline CLI. They do not reimplement the compiler or the simulator.

## 4. Review

- Confirm the dataset manifest validates.
- Confirm the segment count and the state distribution.
- Confirm the coverage gaps and the open questions.
- Confirm the model cards and the licences.
- Do not publish or promote the instance without the maintainer's approval.

## Evidence

Archive:

- `runtime/logs/instance_rebuild_report-<run_id>.json`
- the dataset manifest,
- the corridor and state artifacts,
- the coverage and gap report,
- the model cards.

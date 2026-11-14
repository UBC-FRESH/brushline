# Brushline instance template

This overlay is installed on a FEMIC deployment instance. It adds Brushline configuration, two rebuild
specs, a runbook, and evidence placeholders. It does not replace the FEMIC instance layout.

## Install

From a FEMIC instance root:

```bash
femic instance init --instance-root <path> --no-download-bc-vri
brushline instance template --instance-root <path>
```

`femic instance init` already writes `config/rebuild.spec.yaml`, `config/rebuild.allowlist.yaml`, `QUICKSTART.md`, and `runbooks/REBUILD_RUNBOOK.md`. The overlay skips those files unless `--force` is passed. Use `--force` on a fresh FEMIC instance when you want the Brushline versions; otherwise the FEMIC defaults are kept.

## The two rebuild specs

- `config/rebuild.spec.yaml` is the FEMIC-compatible spec. It is validated by
  `femic instance validate-spec` and describes the FEMIC stages only.
- `config/brushline/rebuild.steps.yaml` is the Brushline extension spec. It describes the
  `brushline.*` provider stages that run after the FEMIC stages. It is not passed to FEMIC's rebuild
  runner.

FEMIC's rebuild schema allows only `femic_command`, `manual_boundary`, and `quality_gate` steps, and its
runner owns a fixed FEMIC stage list. Keeping the Brushline stages in a separate spec is deliberate: the
FEMIC spec stays executable, and the Brushline extension stays inspectable.

## Next

- `brushline instance template --instance-root <path>`
- `femic instance validate-spec --instance-root <path> --spec config/rebuild.spec.yaml`
- Fill in `config/brushline/scenario.yaml`, `targets.yaml`, and `standards.yaml`.
- Follow `runbooks/REBUILD_RUNBOOK.md`.

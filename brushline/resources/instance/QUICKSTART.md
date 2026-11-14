# Brushline instance quickstart

1. Create or open a FEMIC deployment instance:

   ```bash
   femic instance init --instance-root <path> --no-download-bc-vri
   ```

2. Install the Brushline overlay:

   ```bash
   brushline instance template --instance-root <path> --force

   On a fresh `femic instance init`, `--force` replaces the four shared files with the Brushline versions. Without it, those four are skipped.
   ```

3. Validate the FEMIC rebuild spec:

   ```bash
   femic instance validate-spec --instance-root <path> --spec config/rebuild.spec.yaml
   ```

4. Edit `config/brushline/scenario.yaml`, `targets.yaml`, and `standards.yaml`.

5. Review `config/brushline/rebuild.steps.yaml`; it lists the Brushline provider stages.

6. Run the FEMIC stages first, then the Brushline provider graph. See
   `runbooks/REBUILD_RUNBOOK.md`.

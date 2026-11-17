# Release readiness

## Audit

`python tools/audit_release.py` passes:

- no tracked paths under `runtime/`, `data/private/`, `local/`, `tmp/`, or `outputs/`;
- `runtime/` and `data/private/` are ignored;
- no tracked local absolute paths;
- the public synthetic demo has no BC network or MKRF references.

At audit time the private directory contained 62 files and none were tracked. The public demo
remains synthetic.

## External gates

The repository boundary is clean, but release is not approved. The following remain external:

- data-sharing agreement and permissions for BC network-derived artifacts;
- release approval for private model artifacts;
- field validation, which has not been performed;
- asset-owner review of safety, access, outage, and clearance assumptions.

## Status

Ready for release review, not released. Do not publish network-derived artifacts until the
external gates are cleared.

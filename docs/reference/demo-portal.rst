Public demo portal
==================

P11 builds a static, public-data-only, read-only demo portal from `brushline.demo.v1` manifests. The portfolio has five curated narratives over the synthetic corridor. `brushline demo build --out build/demo --artifact-root examples/synthetic-corridor` generates the index, five instance pages, pilot page, style, demo script, portfolio JSON, health JSON, and deploy metadata.

Each instance page separates "What this shows" from "What this does not show", lists source licences, and includes a 2D corridor, 3D context canvas with pre/post toggle, plan actions, and Pareto table. The optional service is read-only; `health.json` records that. No private data or uploads are part of the public surface.

# Changelog

## 0.2.0 - 2026-11-24

Moved the pipeline to the new ontology (`ontology/new_design/`).

- Removed: AI system module and its queries, role reuse and grounding, authored-vs-imported report, pattern-coverage report, old `shapes/` folder.
- Added 156 curated mitigation links as `ak:mitigates` (`build/manual_mitigation_links.nt`).
- Added AI Incident Database and AI Vulnerability Database snapshots (`staging/incidents.csv`).
- `validate` now reads the shapes file from the config and writes risk-motif detections to `build/reports/motif_detections.csv`. New `coverage` report.
- Added `extractor/` with `llm_mitigation` and `llm_motif` (LLM proposals, human review).

## 0.1.0 - 2026-11-17

First version of the pipeline.

- Fetches IBM AI Atlas Nexus (pinned commit), DPV and BEAM; checksums in `sources/manifest.json`.
- Imports 133 risks (IBM 99, MIT 24, OWASP LLM Top 10 10), 108 crosswalks and 831 MIT mitigation controls via RML (Morph-KGC).
- Merges into `build/airkg-core-kg.ttl`; validates with HermiT and SHACL.
- Reports and a static site with one page per entry.
- Added `llm_mitigation/` .

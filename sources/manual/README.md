# Manually placed sources

Files that the pipeline cannot download from a pinned source. `fetch` records their SHA-256 in `sources/manifest.json`.

| File | Used by | Notes |
|---|---|---|
| `beam_core.ttl` | not used by any step yet | BEAM core vocabulary (<https://semsys.ai.wu.ac.at/beam/beam_core.ttl>); `fetch` downloads it when missing. The ontology's process classes (Generate, Train, Engineer, Transform, Infer) follow BEAM. Licence not stated, so it is not redistributed in the KG. |
| `iso22989_roles.csv` | not used by any step yet | Stakeholder role names of ISO/IEC 22989:2022 clause 5.19 (columns `id,name,parent_id,clause`), from a secondary source. Candidate source for `Stakeholder` values. |
| `ai_models/` | not used by any step yet | Epoch AI "Data on AI models" (CC BY 4.0; see `ai_models/README.md`). Candidate source for `Model` instances. |

The curated mitigation links are in `sources/mapping/` (see `docs/mitigations.md`); `stage` reads them through `manual_mitigation_links` in `config/pipeline.yaml`.

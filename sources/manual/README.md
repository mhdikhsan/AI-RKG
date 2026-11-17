# Manually placed sources

| File | Status | Notes |
|---|---|---|
| `iso22989_roles.csv` | template (empty) | Columns `id,name,parent_id,clause`. `id`: short kebab-case id (becomes `{base_iri}role/iso22989/{id}`); `parent_id`: id of the broader role or empty; `clause`: ISO/IEC 22989:2022 clause number (stored in `ak:identifier`; `ak:source` = ISO standard URL). |
| `beam_core.ttl` | missing | Download of https://semsys.ai.wu.ac.at/beam/beam_core.ttl |
## `role_grounding.csv` (ground authored roles in external vocabularies)

One row per link from an authored role to an external term. Columns:

| Column | Content | Example |
|---|---|---|
| `role` | local name of a role in `ak:` (or a full IRI, e.g. a reused role) | `TrainingDataRole` |
| `predicate` | one of `seeAlso`, `exactMatch`, `closeMatch`, `broadMatch`, `narrowMatch`, `relatedMatch` (`rdfs:seeAlso` / `skos:*`) | `closeMatch` |
| `target` | full IRI, or CURIE with `beam:`, `dpv:`, `ai:` (DPV-AI), `airo:` | `ai:TrainingData` |
| `note` | why (optional, not imported) | `same meaning` |

Rules: the role must exist; BEAM/DPV/DPV-AI targets must exist in the fetched vocabularies (typo protection); other namespaces are accepted but reported as unverified. `skos:exactMatch` only if the meanings are the same; `closeMatch` for very similar; `broadMatch`/`narrowMatch` when the target is broader/narrower than the role; `seeAlso` for a loose pointer.
Run `python -m scripts.run roles merge validate report`. Suggestions (by name only, not applied): `build/reports/role_grounding_candidates.md`.
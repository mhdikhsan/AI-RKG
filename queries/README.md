# Queries

## Competency questions (you provide)

Put each competency question as `queries/<ID>.rq` (e.g. `Q7.rq`, `Q16.rq`, `Q17.rq` — the ones that run on the core graph) and the expected **row count** per file in `queries/expected.json`:

```json
{ "Q7.rq": 12, "Q16.rq": 3, "Q17.rq": 5 }
```

`python -m scripts.run validate` runs every `queries/*.rq` against `build/airkg-core-kg.ttl` and reports a mismatch as an error. A `.rq` without an entry in `expected.json` is run and reported, not checked.
Compare text values with `STR(?x) = "…"` (Protégé stores typed strings).

## `system/` — AI system module baseline (pipeline-authored)

Run against the AI system module loaded with (a) the original core module and (b) the merged core graph; the result rows must be identical. They follow the system module's existing paths (workflow → patterns → risks/mitigations, components → roles, motifs → roles, consequences → stakeholders).

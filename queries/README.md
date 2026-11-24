# Queries

## Competency questions

Put each competency question as `queries/<ID>.rq` (for example `Q1.rq`) and the expected **row count** per file in `queries/expected.json`:

```json
{ "Q1.rq": 12, "Q2.rq": 3 }
```

`python -m scripts.run validate` runs every `queries/*.rq` against `build/airkg-core-kg.ttl` and reports a mismatch as an error. A `.rq` without an entry in `expected.json` is run and reported, not checked.

Notes for writing queries against the merged graph:

- rdflib does no reasoning: to find instances of a class and its subclasses, use `?x a/rdfs:subClassOf* :Model`.
- Compare text values with `STR(?x) = "…"` (strings may be typed).
- Risk-motif detections are not stored in the graph; they are in `build/reports/motif_detections.csv` (written by `validate`).

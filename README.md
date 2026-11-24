# AI-RKG

AI Risk Pattern Knowledge Graph.

| Path | Content |
|---|---|
| `ontology/new_design/` | ontology (`airkg.ttl`) and SHACL shapes (`shapes.ttl`) |
| `config/pipeline.yaml` | pinned sources, licences, paths |
| `scripts/` | pipeline: fetch, stage, map, merge, validate, coverage, report, site |
| `mappings/` | RML mappings (CSV to RDF) |
| `extractor/` | LLM-assisted extraction with human review (`llm_mitigation`, `llm_motif`) |
| `build/` | the knowledge graph (`airkg-core-kg.ttl`) and reports |

Run with `python -m scripts.run all` or `make all`. Extractors: [extractor/README.md](extractor/README.md). Licences: [LICENSES.md](LICENSES.md).

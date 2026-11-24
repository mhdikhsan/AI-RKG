# Extractor

LLM-assisted extraction with LLM. A human reviews the proposals; only accepted rows enter the graph, through RML mappings.

| Tool | Proposes | Input | Accepted output | RML mapping |
|---|---|---|---|---|
| [llm_mitigation](llm_mitigation/README.md) | `mitigates` links | `staging/risks.csv`, `staging/mit_controls.csv` | `staging/accepted_mitigation_links.csv` | `mappings/accepted_mitigation_links.rml.ttl` |
| [llm_motif](llm_motif/README.md) | `RiskMotif`s from AIID and AVID | `staging/incidents.csv`, `staging/risks.csv` | `staging/accepted_motif*.csv` | `mappings/accepted_motifs.rml.ttl` |

- The ontology (file from `config/pipeline.yaml`) is given to the model as a fixed schema. Gaps are reported in `issues`.
- Answers are validated against a JSON schema; motifs also against the ontology's domain and range.
- Responses are cached by hash of prompt, input, model and settings. `--dry-run` and `estimate` make no API calls.
- Each proposal records model, model version, prompt SHA-256 and date. `apply` requires a reviewer per accepted row.

Install, from the repository root:

```
.venv/Scripts/python -m pip install -e extractor/llm_mitigation -e extractor/llm_motif
```

Set '`LLM-API-KEY`' in the environment or in a git-ignored `.env`.

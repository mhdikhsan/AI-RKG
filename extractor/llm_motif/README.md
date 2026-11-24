# llm-motif

Proposes `RiskMotif`s from AI incidents (AIID) and vulnerability records (AVID). Only risk motifs accepted by a reviewer input to the graph.

Reads `staging/incidents.csv`, `staging/risks.csv` and the ontology and shapes files from `config/pipeline.yaml`. Writes to `output/`, `cache/` and, via `apply`, `staging/accepted_motif*.csv` (mapped by `mappings/accepted_motifs.rml.ttl`).

## Install

Reuses the code of llm-mitigation.

```
.venv/Scripts/python -m pip install -e extractor/llm_mitigation -e extractor/llm_motif
```

Requires `ANTHROPIC_API_KEY`.

## Steps

| Step | Command | Does | API calls |
|---|---|---|---|
| 1 | `llm-motif run --stage profile` | Per incident: the system as an architecture (elements typed by ontology classes, `uses`/`produces` flows, contexts, failure point) and up to 3 risks from a TF-IDF shortlist. Evidence quotes are checked against the incident text. | one per incident |
| 2 | `llm-motif group` | General groups: same element classes and top risk (`min_support`). Specific groups: same element classes and one context value (`specific_min_support`), parent is the general group sharing most incidents. Deterministic; `motif_key` keeps IRIs stable. | none |
| 3 | `llm-motif run --stage abstract` | Per group: a generalised motif with common superclasses, needed contexts and a manifest condition. Specific motifs build on their general motif (architecture and context checked). | one per group |
| 4 | `llm-motif check` | Converts profiles and motifs to workflows and runs `MotifDetectionShape`. A good motif fires on all its supporting incidents; `fires_elsewhere` shows how widely it applies. | none |
| 5 | `llm-motif review-export [--xlsx]` | Writes `output/review_sheet.csv` with structure, contexts, support, evidence, check results and empty `reviewer`/`decision`. | none |
| 6 | `llm-motif apply --review output/review_sheet.csv` | Writes accepted rows; then run `python -m scripts.run map merge validate`. | none |

Before a real run: `run --stage profile --dry-run` renders prompts to `output/prompts_preview/`, and `estimate --stage profile` gives calls, tokens and cost. `all --limit 30` runs the chain on a pilot and asks before each API stage.

## Prompts

`prompts/extract_profile.md` and `prompts/abstract_motif.md` give the model the ontology as a fixed schema and forbid new classes or properties. The model returns JSON against a schema with per-call enums (element classes, contexts, shortlisted risks, supporting incidents). The code mints IRIs and checks `uses`/`produces` against the ontology's domain and range; invalid answers are retried once, then skipped and logged. The SHA-256 of both prompts is stored on every profile and motif.

## Licences

AIID is CC BY-SA 4.0 (only incident descriptions and classifications are used), AVID is MIT. Profiles and proposals quote incident text and are git-ignored. Accepted motifs are published as `build/accepted_motifs.nt` under CC BY-SA 4.0.

## Model

Default `claude-sonnet-5-5`; override with `--model`. Effort is `medium` for profiles and `high` for abstraction (`config.yaml`). Responses are cached, so reruns cost nothing.

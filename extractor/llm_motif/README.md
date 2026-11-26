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
| 2 | `llm-motif group` | General groups: same element classes and top risk (`min_support`). Specific groups: same element classes and one context value (`specific_min_support`), parent is the general group sharing most incidents. Deterministic. Each group sent to the LLM gets a readable ID (see below). | none |
| 3 | `llm-motif run --stage abstract` | Per group: a generalised motif with common superclasses, a role label per element, needed contexts and a manifest condition. Specific motifs build on their general motif (architecture and context checked). | one per group |
| 4 | `llm-motif check` | Converts profiles and motifs to workflows and runs `MotifDetectionShape`. A good motif matches all its own incidents; `matches_other_incidents` shows how widely it applies. Motifs already accepted in `staging/` are tested too: incidents they match that are not yet their sources go to `output/extensions.csv`. | none |
| 5 | `llm-motif review-export --reviewer NAME [--xlsx]` | Writes `output/review_sheet_<name>.csv`: `new motif` rows (already accepted motifs are left out) and `add incident to accepted motif` rows. Without `--reviewer`: `output/review_sheet.csv`. | none |
| 6 | `llm-motif review-status --review A.csv --review B.csv` | Optional: votes and outcome per row in `output/review_status.csv`, to settle disagreements first. | none |
| 7 | `llm-motif apply --review A.csv [--review B.csv ...]` | Adds accepted rows to `staging/accepted_motif*.csv`; then run `python -m scripts.run map merge validate`. | none |

### Evolving the graph

`apply` only adds. A motif in `staging/accepted_motifs.csv` is never rewritten or removed by a later run, even when the same motif is proposed and accepted again: the reviewed version stays. When new incidents arrive, rerun profile, group, abstract and check. New patterns come out as `new motif` rows. New incidents that fit an accepted motif come out as `add incident to accepted motif` rows: accepting one adds an `ak:source` to that motif (with reviewer and date in `accepted_motif_sources.csv`), rejecting one records it in `staging/excluded_motif_sources.csv` so it is not offered again.

To change or remove an accepted motif, edit the staging CSVs by hand.

### Several reviewers

Each reviewer exports and fills their own sheet. `apply` combines the decisions per row with `review.rule` in `config.yaml`: `all` (accepted only if nobody rejects), `majority` (a tie stays undecided) or `any`. Rows with fewer than `review.min_reviewers` decisions stay undecided. A reviewer may decide a row only once over all sheets. The `reviewer` column of an accepted motif lists everyone who accepted it.

### Motif IDs

A group is recognised by a hash of its grouping key, which is stable across runs. The first time a group is sent to the LLM it gets a readable ID: `M-0001` for a general motif, `M-0001.1`, `M-0001.2`, ... for specific motifs under it (a specific motif without a general one gets its own `M-` number). `staging/motif_ids.csv` keeps the hash -> ID mapping, so an ID never changes and is never reused; numbers of groups that were proposed but not accepted leave gaps. The ID is the motif's IRI (`.../motif/M-0001`) and `ak:identifier`.

### Columns

| File | Column | Meaning |
|---|---|---|
| review sheet | `review_item` | `new motif` or `add incident to accepted motif` |
| review sheet, groups | `motif_level`, `general_motif_id` | general or specific; the general motif a specific one builds on |
| review sheet | `specific_for_context` | the context value a specific motif adds |
| review sheet | `architecture` | `inputs -> [process] -> outputs`, elements as `role (Class)`; `[!]` marks where the risk appears |
| review sheet | `required_contexts`, `risk_appears_at` | contexts a system must have; the manifest-condition element |
| review sheet, check | `based_on_incidents`, `number_of_incidents` | the incidents the motif was written from |
| review sheet | `few_incidents` | `yes` below `group.min_support_flag` |
| review sheet | `quotes_found_in_text` | element evidence quotes found verbatim in the incident text, e.g. `5 of 8` |
| review sheet, check | `matches_own_incidents` | own incidents the motif matches with `MotifDetectionShape`, e.g. `2 of 2` |
| check | `own_incidents_not_matched` | own incidents it does not match |
| review sheet, check | `matches_other_incidents` | other profiled incidents it matches (how general it is); listed in `all_matched_incidents` |
| review sheet, check | `broader_motif_same_risk` | motifs with the same risk that already match this one; `(accepted)` if accepted |
| review sheet | `llm_confidence`, `llm_notes` | the model's confidence and issues |
| groups | `top_risk`, `architecture_classes`, `shared_context` | the grouping key |
| groups | `sent_to_llm` | `yes`, or why the group is not abstracted |

Before a real run: `run --stage profile --dry-run` renders prompts to `output/prompts_preview/`, and `estimate --stage profile` gives calls, tokens and cost. `all --limit 30` runs the chain on a pilot and asks before each API stage.

## Prompts

`prompts/extract_profile.md` and `prompts/abstract_motif.md` give the model the ontology as a fixed schema and forbid new classes or properties. The model returns JSON against a schema with per-call enums (element classes, contexts, shortlisted risks, supporting incidents). The code mints IRIs and checks `uses`/`produces` against the ontology's domain and range; invalid answers are retried once, then skipped and logged. The SHA-256 of both prompts is stored on every profile and motif.

## Licences

AIID is CC BY-SA 4.0 (only incident descriptions and classifications are used), AVID is MIT. Profiles and proposals quote incident text and are git-ignored. Accepted motifs are published as `build/accepted_motifs.nt` under CC BY-SA 4.0.

## Model

Default `claude-sonnet-5-5`; override with `--model`. Effort is `medium` for profiles and `high` for abstraction (`config.yaml`). Responses are cached, so reruns cost nothing.

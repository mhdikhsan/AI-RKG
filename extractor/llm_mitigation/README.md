# llm-mitigation

Proposes `mitigation ak:mitigates risk` links between MIT controls and catalogue risks. Only rows accepted by a reviewer enter the graph.

Reads `staging/risks.csv`, `mit_controls.csv` and `mit_control_groups.csv`. Writes to `output/`, `cache/` and, via `apply`, `staging/accepted_mitigation_links.csv`.

## Install

```
.venv/Scripts/python -m pip install -e extractor/llm_mitigation
```

Requires `ANTHROPIC_API_KEY`. `llm-mitigation all` runs shortlist, estimate (asks for confirmation), run and review-export.

## Commands

| Command | Does | API calls |
|---|---|---|
| `shortlist` | Top-k (default 20) controls per risk by TF-IDF cosine, deterministic. Writes `output/shortlist.csv`. | none |
| `estimate [--limit N] [--exact]` | Calls, tokens and cost per model; cached answers are free. `--exact` uses token counting. | none |
| `run --dry-run [--limit N]` | Renders prompts and schema to `output/prompts_preview/`. | none |
| `run [--limit N]` | One call per risk. Validates against `schema/response.schema.json`, retries once, then skips. Writes `output/candidates.csv`, `output/run_log.csv`. | one per uncached risk |
| `review-export [--xlsx]` | Writes `output/review_sheet.csv` with empty `reviewer` and `decision` columns. Won't overwrite decisions without `--force`. | none |
| `apply --review output/review_sheet.csv` | Keeps `decision=accept` rows (reviewer required). | none |

Options: `--config path`, `--model claude-haiku-5-5`.

## Candidate columns

`risk_id, mitigation_id, confidence (high|medium|low), rationale, model, model_version, prompt_sha256, run_date, reviewer, decision`

## Review

1. Open `output/review_sheet.csv`.
2. Fill `reviewer` and set `decision` to `accept` or `reject`. Empty rows are not applied.
3. Accept only if the control prevents the risk, makes it detectable or reduces its consequences. Topic overlap is not enough.
4. Run `llm-mitigation apply --review output/review_sheet.csv`, then `python -m scripts.run map merge validate`.

## Reproducibility

- No temperature is sent; both models reject non-default sampling parameters, so fresh calls can vary.
- Valid answers are cached in `cache/<sha256>.json` (git-ignored), keyed by provider, model, effort, max_tokens, fallback setting, rendered prompt and schema. Reruns cost nothing and give identical output.
- The per-call schema lists the shortlisted ids as an enum. Answers are also re-validated locally.

## Limitation

OWASP risks have only a name, so their shortlists are shorter (3-17 controls).

## Tests

```
.venv/Scripts/python -m pytest -q extractor/llm_mitigation/tests
```

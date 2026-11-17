# llm-mitigation

Proposes links **mitigation `ak:mitigates` risk** between the MIT AI Risk Repository controls and the catalogue risks of the AI-RKG core graph, with an LLM, for **human review**. Nothing produced here enters the graph except rows a reviewer accepted.

It reads only the staged CSVs of the main pipeline (`../staging/risks.csv`, `mit_controls.csv`, `mit_control_groups.csv`) and writes only to `output/`, `cache/` and — via `apply` — `../staging/accepted_mitigation_links.csv`.

## Install

From the repository root, inside the pipeline's virtual environment:

```
.venv/Scripts/python -m pip install -e llm_mitigation      # Windows (.venv/bin/python on Linux)
```

This installs the `llm-mitigation` command. Credentials: the Anthropic SDK reads `ANTHROPIC_API_KEY` from the environment. The tool never writes the key anywhere.

## One command

```
llm-mitigation all            # shortlist -> estimate -> asks for confirmation -> run -> review-export
```

## Step by step

| Command | What it does | API calls |
|---|---|---|
| `llm-mitigation shortlist` | For each risk, top-k (default 20) controls by TF-IDF cosine over control name + MIT category names + description vs. risk name + description. Deterministic (ties by id); zero-score controls never offered. → `output/shortlist.csv` | none |
| `llm-mitigation estimate [--limit N] [--exact]` | Number of calls, approximate input/output tokens, cost per model in `config.yaml`. Cached answers count as free. `--exact` counts input tokens with the token-counting endpoint (needs credentials, no generation). | none (or token counting) |
| `llm-mitigation run --dry-run [--limit N]` | Renders every prompt + the response schema to `output/prompts_preview/`. | none |
| `llm-mitigation run [--limit N]` | One call per risk with its shortlist; validates the answer against `schema/response.schema.json`; retries once on invalid JSON / schema violation, then logs and skips; ids not on the shortlist are rejected. → `output/candidates.csv`, `output/run_log.csv` | one per uncached risk |
| `llm-mitigation review-export [--xlsx]` | `output/review_sheet.csv` (or `.xlsx` with an accept/reject dropdown), sorted by risk then confidence, empty `reviewer` and `decision` columns. Refuses to overwrite a sheet that already holds decisions (use `--force`). | none |
| `llm-mitigation apply --review output/review_sheet.csv` | Keeps `decision=accept` rows (reviewer required, decision must be accept/reject/empty) → `../staging/accepted_mitigation_links.csv`. The main pipeline maps it with `mappings/accepted_mitigation_links.rml.ttl` → `build/accepted_mitigation_links.nt`. | none |

Global options: `--config path/to/config.yaml`, `--model claude-haiku-5-5` (cheaper run).

## Candidate row format

`risk_id, mitigation_id, confidence (high|medium|low), rationale (≤ 2 sentences), model, model_version, prompt_sha256, run_date, reviewer, decision`

- `model` = the configured model; `model_version` = the model id the API reports for the answer (differs from `model` only if a server-side refusal fallback answered).
- `prompt_sha256` = SHA-256 of `prompts/link_mitigations.md` (the template file).
- `run_date` = date of the API call (kept from the cache on reruns).

## How to review

1. Open `output/review_sheet.csv` (or run `review-export --xlsx`).
2. For each row write your name/initials in `reviewer` and `accept` or `reject` in `decision`. Leave undecided rows empty; they are not applied.
3. Accept a link only if the control, *as described*, prevents the risk, makes it detectable, or reduces its consequences. Topic overlap is not enough.
4. Run `llm-mitigation apply --review output/review_sheet.csv`, then `python -m scripts.run map merge validate` in the repository root.

## Model, prices, cost

Provider: Claude via the Anthropic API, official `anthropic` Python SDK (2.9.0). Implemented providers: `anthropic` and `fake` (deterministic, offline, used by the tests). Another provider can be added by subclassing `Provider` in `llm_mitigation/providers.py`.

| Model id | Input $/MTok | Output $/MTok | Notes |
|---|---|---|---|
| `claude-sonnet-5-5` (default) | 2.00 | 10.00 | server-side refusal fallback enabled (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`) |
| `claude-haiku-5-5` | 0.10 | 0.50 | prompts up to 100K tokens; no server-side fallback |

Prices: Anthropic first-party API, checked 2026-11-17 against Anthropic's model table (cached 2026-11-03). Verify at <https://platform.claude.com/docs/en/about-claude/pricing> before a large run; they are in `config.yaml` → `pricing`.

Cost drivers: ~133 calls (one per risk), each ~3.3K input tokens on average (up to 20 controls with descriptions; estimate of 2026-11-17: 435K input tokens in total). Output = the short JSON answer plus adaptive-thinking tokens (billed as output); `estimate` assumes a per-effort thinking allowance (`config.yaml` → `estimate`). Lower cost: `--model claude-haiku-5-5`, `effort: low`, or a smaller `shortlist.k`.

## Reproducibility

- **No temperature is sent.** The pipeline prompt asked for temperature 0, but `claude-sonnet-5-5` and `claude-haiku-5-5` reject non-default sampling parameters (HTTP 400). Outputs of a fresh call can therefore vary slightly.
- **Cache:** every valid answer is stored in `cache/<sha256>.json`, keyed by provider + model + effort + max_tokens + fallback setting + the fully rendered prompt + the response schema. Reruns read the cache: no cost, byte-identical `candidates.csv`. Invalid answers are never cached. Changing the prompt template, the shortlist or the model gives new keys.
- `cache/` is git-ignored (it is the raw record of LLM answers; keep it if you need to audit a run).
- Structured outputs (`output_config.format` with a JSON schema) constrain the answer; the schema sent per call lists the shortlisted ids as an `enum`, so the model cannot name a control outside its shortlist. The answer is still re-validated locally (limits on number of links and rationale length).

## Known limitation

OWASP risks carry only their name (OWASP descriptions are not copied, see `LICENSES.md`), so their shortlists are short (3–17 controls instead of 20).

## Tests

```
.venv/Scripts/python -m pytest -q llm_mitigation/tests
```

Cover shortlist determinism, schema validation, cache reuse, retry-then-skip, out-of-shortlist ids, dry run, estimate, review export protection and apply. No network (fake provider).

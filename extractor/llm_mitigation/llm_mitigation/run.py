"""`run` and `estimate`: one LLM call per risk with its shortlist; responses cached by hash."""
from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

import jsonschema

from .config import Config, load_inputs, read_csv, sha256_bytes, stable_json, write_csv
from .prompting import api_schema, prompt_sha256, render, validation_schema
from .providers import Provider, ProviderError, get_provider

CANDIDATE_COLS = ["risk_id", "mitigation_id", "confidence", "rationale", "model", "model_version",
                  "prompt_sha256", "run_date", "reviewer", "decision"]
LOG_COLS = ["risk_id", "status", "attempts", "cached", "n_links", "rejected_ids", "input_tokens",
            "output_tokens", "model_version", "issues", "message"]


def load_shortlists(cfg: Config) -> dict[str, list[str]]:
    path = Path(cfg.path("output_dir")) / "shortlist.csv"
    if not path.exists():
        raise SystemExit(f"{path} not found - run `llm-mitigation shortlist` first")
    by_risk = defaultdict(list)
    for r in sorted(read_csv(path), key=lambda r: (r["risk_id"], int(r["rank"]))):
        by_risk[r["risk_id"]].append(r["mitigation_id"])
    return dict(by_risk)


def cache_key(cfg: Config, system: str, user: str, schema: dict) -> str:
    """hash(prompt + input + model + generation settings)."""
    payload = {"provider": cfg["provider"], "system": system, "user": user, "schema": schema, "model": cfg["model"],
               "effort": cfg["effort"], "max_tokens": cfg["max_tokens"],
               "fallback": bool(cfg.get("server_side_fallback"))}
    return sha256_bytes(stable_json(payload).encode("utf-8"))


class Cache:
    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def get(self, key: str) -> dict | None:
        p = self.folder / f"{key}.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def put(self, key: str, value: dict) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / f"{key}.json").write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False),
                                                 encoding="utf-8")


def parse_answer(text: str, schema: dict) -> dict:
    """Parse + validate. Raises ValueError with a readable reason."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON: {e.msg}") from e
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        raise ValueError(f"schema violation: {e.message[:200]}") from e
    return data


def plan(cfg: Config, limit: int | None = None):
    """Yield (risk, shortlist ids, system, user, validation schema) for each risk in scope."""
    risks, controls, groups = load_inputs(cfg)
    shortlists = load_shortlists(cfg)
    n = 0
    for risk in risks:
        ids = shortlists.get(risk["nexus_id"], [])
        if not ids:
            continue
        if limit is not None and n >= limit:
            break
        n += 1
        system, user = render(cfg, risk, ids, controls, groups)
        yield risk, ids, system, user, validation_schema(cfg, ids)


def dry_run(cfg: Config, limit: int | None = None) -> int:
    out = Path(cfg.path("output_dir")) / "prompts_preview"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.md"):
        old.unlink()
    n = 0
    for risk, ids, system, user, schema in plan(cfg, limit):
        (out / f"{risk['nexus_id']}.md").write_text(
            f"# Prompt preview: {risk['nexus_id']}\n\nmodel: {cfg['model']} | effort: {cfg['effort']} | "
            f"prompt_sha256: {prompt_sha256(cfg)}\n\n## System\n\n{system}\n\n## User\n\n{user}\n\n"
            f"## Response schema (sent as output_config.format)\n\n```json\n"
            f"{json.dumps(api_schema(schema), indent=2)}\n```\n", encoding="utf-8")
        n += 1
    return n


def run(cfg: Config, provider: Provider | None = None, limit: int | None = None, log=print) -> dict:
    provider = provider or get_provider(cfg)
    cache = Cache(cfg.path("cache_dir"))
    psha = prompt_sha256(cfg)
    today = dt.date.today().isoformat()
    candidates, log_rows = [], []
    stats = defaultdict(int)
    for risk, ids, system, user, schema in plan(cfg, limit):
        rid = risk["nexus_id"]
        key = cache_key(cfg, system, user, api_schema(schema))
        entry, attempts, cached, err = cache.get(key), 0, True, ""
        data = None
        if entry is not None:
            data = parse_answer(entry["text"], schema)  # cached entries were valid when stored
        else:
            cached = False
            for attempt in range(1 + int(cfg.get("retries_on_invalid", 1))):
                attempts = attempt + 1
                try:
                    res = provider.complete(system, user, api_schema(schema))
                except ProviderError as e:
                    err = str(e)
                    break
                try:
                    data = parse_answer(res.text, schema)
                except ValueError as e:
                    err = str(e)
                    continue
                entry = {"text": res.text, "model_version": res.model_version, "run_date": today,
                         "usage": res.usage, "risk_id": rid, "prompt_sha256": psha}
                cache.put(key, entry)
                err = ""
                break
        if data is None:
            stats["skipped"] += 1
            log(f"  SKIP {rid}: {err}")
            log_rows.append({"risk_id": rid, "status": "skipped", "attempts": attempts, "cached": cached,
                             "message": err})
            continue
        allowed, seen, rejected = set(ids), set(), []
        for link in data["links"]:
            mid = link["mitigation_id"]
            if mid not in allowed:          # defence in depth (the enum already restricts this)
                rejected.append(mid)
                continue
            if mid in seen:
                continue
            seen.add(mid)
            candidates.append({"risk_id": rid, "mitigation_id": mid, "confidence": link["confidence"],
                               "rationale": " ".join(link["rationale"].split()), "model": cfg["model"],
                               "model_version": entry["model_version"], "prompt_sha256": psha,
                               "run_date": entry["run_date"], "reviewer": "", "decision": ""})
        stats["cached" if cached else "called"] += 1
        u = entry.get("usage", {})
        log_rows.append({"risk_id": rid, "status": "ok", "attempts": attempts, "cached": cached,
                         "n_links": len(seen), "rejected_ids": " ".join(rejected),
                         "input_tokens": u.get("input_tokens", ""), "output_tokens": u.get("output_tokens", ""),
                         "model_version": entry["model_version"],
                         "issues": " | ".join(" ".join(i.split()) for i in data.get("issues") or [])})
    candidates.sort(key=lambda r: (r["risk_id"], r["mitigation_id"]))
    out = Path(cfg.path("output_dir"))
    write_csv(out / "candidates.csv", CANDIDATE_COLS, candidates)
    write_csv(out / "run_log.csv", LOG_COLS, log_rows)
    stats["candidates"] = len(candidates)
    return dict(stats)


def estimate(cfg: Config, limit: int | None = None, exact: bool = False) -> dict:
    """Approximate calls, tokens and cost. No API call unless exact=True (token counting endpoint)."""
    est = cfg["estimate"]
    cache = Cache(cfg.path("cache_dir"))
    counter = get_provider(cfg) if exact else None
    calls = cached = 0
    in_tokens = 0
    for risk, ids, system, user, schema in plan(cfg, limit):
        sch = api_schema(schema)
        if cache.get(cache_key(cfg, system, user, sch)) is not None:
            cached += 1
            continue
        calls += 1
        if counter is not None and hasattr(counter, "count_tokens"):
            in_tokens += counter.count_tokens(system, user, sch)
        else:
            in_tokens += round((len(system) + len(user) + len(json.dumps(sch))) / est["chars_per_token"])
    out_per_call = est["answer_tokens_per_call"] + est["thinking_tokens_per_call"][cfg["effort"]]
    out_tokens = calls * out_per_call
    rows = {}
    for model, price in cfg["pricing"].items():
        cost = in_tokens / 1e6 * price["input"] + out_tokens / 1e6 * price["output"]
        rows[model] = round(cost, 4)
    return {"model": cfg["model"], "effort": cfg["effort"], "calls": calls, "cached_free": cached,
            "input_tokens": in_tokens, "output_tokens_assumed": out_tokens,
            "output_tokens_per_call_assumed": out_per_call, "token_count_method": "count_tokens API" if exact else
            f"chars/{est['chars_per_token']}", "cost_usd_by_model": rows,
            "cost_usd_configured_model": rows.get(cfg["model"])}

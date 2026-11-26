
from __future__ import annotations
import datetime as dt
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from llm_mitigation.config import Config, read_csv, write_csv
from llm_mitigation.prompting import load_template, prompt_files_sha256
from llm_mitigation.providers import Provider, ProviderError
from llm_mitigation.run import Cache, cache_key, parse_answer
from llm_mitigation.shortlist import TfIdf, tokens

from .core import (Vocab, api_schema, check_structure, dumps, evidence_report, fill_schema, stage_cfg,
                   structure_text)
CONF_RANK = {"high": 0, "medium": 1, "low": 2}
# inputs
def load_incidents(cfg: Config) -> list[dict]:
    sc = cfg["scope"]
    out = []
    for r in read_csv(cfg.path("incidents")):
        if r["source"] not in sc["sources"]:
            continue
        if r["source"] == "aiid" and sc.get("aiid_require_gmf") and not (r["gmf_technology"] or r["gmf_goal"]
                                                                          or r["gmf_potential_technology"]):
            continue
        if r["source"] == "avid" and r["record_class"] not in sc.get("avid_record_classes", []):
            continue
        out.append(r)
    out.sort(key=lambda r: r["incident_id"])
    per = sc.get("per_source") or {}        
    if per:
        seen = {}
        kept = []
        for r in out:
            n = seen.get(r["source"], 0)
            if n < per.get(r["source"], 0):
                kept.append(r)
            seen[r["source"]] = n + 1
        out = kept
    return out


def load_risks(cfg: Config) -> dict[str, dict]:
    cats = set(cfg["shortlist"]["catalogues"])
    return {r["nexus_id"]: r for r in read_csv(cfg.path("risks")) if r["catalogue"] in cats}


def incident_text(inc: dict) -> str:
    return " ".join(inc[k] for k in ("title", "description", "deployer", "developer", "harmed_parties", "gmf_goal",
                                     "gmf_technology", "gmf_failure", "gmf_potential_technology", "gmf_potential_failure",
                                     "cset_sector", "cset_ai_task", "cset_data_inputs", "avid_artifacts") if inc.get(k))


def incident_block(inc: dict) -> str:
    rows = [("id", inc["incident_id"]), ("source", f"{inc['source']} ({inc['record_class']})"), ("title", inc["title"]),
            ("description", inc["description"]), ("date", inc["date"]), ("deployer", inc["deployer"]),
            ("developer", inc["developer"]), ("harmed or nearly harmed parties", inc["harmed_parties"]),
            ("known AI goal (GMF)", inc["gmf_goal"]), ("known AI technology (GMF)", inc["gmf_technology"]),
            ("known technical failure (GMF)", inc["gmf_failure"]),
            ("potential AI technology (GMF)", inc["gmf_potential_technology"]),
            ("potential technical failure (GMF)", inc["gmf_potential_failure"]),
            ("sector of deployment (CSET)", inc["cset_sector"]), ("autonomy level (CSET)", inc["cset_autonomy"]),
            ("AI task (CSET)", inc["cset_ai_task"]), ("data inputs (CSET)", inc["cset_data_inputs"]),
            ("affected artifacts (AVID)", inc["avid_artifacts"]), ("lifecycle stage (AVID)", inc["avid_lifecycle"]),
            ("vulnerability type (AVID)", inc["avid_sep"])]
    return "\n".join(f"- {k}: {v}" for k, v in rows if v)


def risks_block(ids: list[str], risks: dict[str, dict], max_desc: int = 400) -> str:
    out = []
    for rid in ids:
        r = risks[rid]
        d = (r.get("description") or "").strip()
        out.append(f"- id: {rid}\n  catalogue: {r['catalogue']} ({r['catalogue_identifier']})\n  name: {r['name']}"
                   + (f"\n  description: {d[:max_desc]}{'...' if len(d) > max_desc else ''}" if d else ""))
    return "\n".join(out) or "(none)"


# shortlist: incident and risk
def build_risk_shortlist(cfg: Config, incidents: list[dict], risks: dict[str, dict]) -> dict[str, list[str]]:
    index = TfIdf({rid: tokens(f"{r['name']} {r.get('description', '')}") for rid, r in risks.items()})
    k = cfg["shortlist"]["k_risks"]
    out = {}
    for inc in incidents:
        q = index.vector(tokens(incident_text(inc)))
        scored = sorted(((round(index.cosine(q, v), 6), rid) for rid, v in index.vecs.items()), key=lambda x: (-x[0], x[1]))
        ids = [rid for s, rid in scored if s > 0][:k]
        if cfg["shortlist"].get("always_include_aiid_mit"):
            for rid in inc["mit_risk_ids"].split():
                if rid in risks and rid not in ids:
                    ids.append(rid)
        out[inc["incident_id"]] = ids
    return out


# generic cached call
def call(cfg: Config, provider: Provider, cache: Cache, system: str, user: str, schema: dict, check, tag: str,
         log=print) -> tuple[dict | None, dict, dict]:
    api = api_schema(schema)
    key = cache_key(cfg, system, user, api)
    entry, attempts, cached, err = cache.get(key), 0, True, ""
    data = None
    if entry is not None:
        data = parse_answer(entry["text"], schema)
    else:
        cached = False
        for attempt in range(1 + int(cfg.get("retries_on_invalid", 1))):
            attempts = attempt + 1
            try:
                res = provider.complete(system, user, api)
            except ProviderError as e:
                err = str(e)
                break
            try:
                data = parse_answer(res.text, schema)
                problems = check(data)
                if problems:
                    raise ValueError("ontology check: " + "; ".join(problems[:5]))
            except ValueError as e:
                data, err = None, str(e)
                continue
            entry = {"text": res.text, "model_version": res.model_version, "run_date": dt.date.today().isoformat(),
                     "usage": res.usage, "tag": tag}
            cache.put(key, entry)
            err = ""
            break
    if data is None:
        log(f"  SKIP {tag}: {err}")
    u = (entry or {}).get("usage", {})
    row = {"id": tag, "status": "ok" if data is not None else "skipped", "attempts": attempts, "cached": cached,
           "input_tokens": u.get("input_tokens", ""), "output_tokens": u.get("output_tokens", ""),
           "model_version": (entry or {}).get("model_version", ""),
           "issues": " | ".join(" ".join(i.split()) for i in (data or {}).get("issues") or []), "message": err}
    return data, entry or {}, row


def render(template: Path, mapping: dict) -> tuple[str, str]:
    system, user = load_template(template)
    for k, v in mapping.items():
        system, user = system.replace("{" + k + "}", str(v)), user.replace("{" + k + "}", str(v))
    return system, user


def prompt_sha(cfg: Config) -> str:
    return prompt_files_sha256([cfg.path("prompt_profile"), cfg.path("prompt_abstract")])


#  stage 1: profiles
def plan_profiles(cfg: Config, vocab: Vocab, limit: int | None = None):
    incidents = load_incidents(cfg)
    risks = load_risks(cfg)
    shortlist = build_risk_shortlist(cfg, incidents, risks)
    base = json.loads(cfg.path("schema_profile").read_text(encoding="utf-8"))
    pc = cfg["profile"]
    common = {"ontology_block": vocab.onto.render(), "element_classes_block": vocab.element_classes_block(),
              "context_values_block": vocab.context_values_block(), "evidence_max_chars": pc["evidence_max_chars"],
              "max_elements": pc["max_elements"], "max_flows": pc["max_flows"], "max_contexts": pc["max_contexts"],
              "max_risks": pc["max_risks"]}
    for n, inc in enumerate(incidents):
        if limit is not None and n >= limit:
            break
        ids = shortlist[inc["incident_id"]]
        system, user = render(cfg.path("prompt_profile"), {**common, "incident_block": incident_block(inc),
                                                           "risks_block": risks_block(ids, risks)})
        schema = fill_schema(base, element_classes=vocab.element_classes, context_classes=vocab.context_classes,
                             existing_ids=vocab.existing_ids(), risk_ids=ids,
                             limits={"elements": pc["max_elements"], "flows": pc["max_flows"],
                                     "contexts": pc["max_contexts"], "risks": pc["max_risks"]})
        yield inc, ids, system, user, schema


def run_profiles(cfg: Config, provider: Provider, vocab: Vocab, limit: int | None = None, log=print) -> dict:
    scfg = stage_cfg(cfg, "profile")
    cache, psha, out = Cache(cfg.path("cache_dir")), prompt_sha(cfg), Path(cfg.path("output_dir"))
    rows, logs, stats = [], [], defaultdict(int)
    for inc, ids, system, user, schema in plan_profiles(cfg, vocab, limit):
        data, entry, lrow = call(scfg, provider, cache, system, user, schema,
                                 lambda d: check_structure(d, vocab, "failure_point"), inc["incident_id"], log)
        logs.append(lrow)
        stats["cached" if lrow["cached"] else "called"] += lrow["status"] == "ok"
        if data is None:
            stats["skipped"] += 1
            continue
        data["risks"] = [r for r in data["risks"] if r["risk_id"] in ids]
        found, total = evidence_report(data, incident_text(inc))
        rows.append({"incident_id": inc["incident_id"], "title": inc["title"], "url": inc["url"],
                     "source": inc["source"], "candidate_risks": ids, "answer": data,
                     "evidence_found": found, "evidence_total": total, "model": cfg["model"],
                     "model_version": entry.get("model_version", ""), "prompt_sha256": psha,
                     "run_date": entry.get("run_date", "")})
    out.mkdir(parents=True, exist_ok=True)
    (out / "profiles.jsonl").write_text("".join(dumps(r) + "\n" for r in rows), encoding="utf-8")
    write_csv(out / "profile_log.csv", list(logs[0].keys()) if logs else ["id"], logs)
    stats["profiles"] = len(rows)
    stats["evidence_found"] = sum(r["evidence_found"] for r in rows)
    stats["evidence_total"] = sum(r["evidence_total"] for r in rows)
    return dict(stats)


def read_jsonl(path: Path) -> list[dict]:
    if not Path(path).exists():
        return []
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


#  readable motif IDs: staging/motif_ids.csv maps the stable group hash to M-0001 (specific: M-0001.1)
REG_COLS = ["motif_id", "motif_hash", "motif_level", "general_motif_id", "first_seen"]


def registry_path(cfg: Config) -> Path:
    return Path(cfg.path("accepted_dir")) / "motif_ids.csv"


def read_registry(cfg: Config) -> list[dict]:
    return read_csv(registry_path(cfg)) if registry_path(cfg).exists() else []


def next_id(reg: list[dict], parent: str = "") -> str:
    if parent:
        n = max([int(r["motif_id"].rsplit(".", 1)[1]) for r in reg if r["motif_id"].startswith(parent + ".")] or [0])
        return f"{parent}.{n + 1}"
    n = max([int(r["motif_id"].split(".")[0][2:]) for r in reg] or [0])
    return f"M-{n + 1:04d}"


def assign_ids(cfg: Config, groups: list[dict]) -> None:
    """General groups first. Only groups sent to the LLM get an ID; an ID is never changed or reused."""
    reg = read_registry(cfg)
    ids = {r["motif_hash"]: r["motif_id"] for r in reg}
    for g in groups:
        h, parent = g["motif_hash"], ids.get(g.pop("parent_hash", ""), "")
        if h not in ids and g["sent_to_llm"] == "yes":
            ids[h] = next_id(reg, parent if g["motif_level"] == "specific" else "")
            reg.append({"motif_id": ids[h], "motif_hash": h, "motif_level": g["motif_level"],
                        "general_motif_id": parent, "first_seen": dt.date.today().isoformat()})
        g["motif_id"], g["general_motif_id"] = ids.get(h, ""), parent
    write_csv(registry_path(cfg), REG_COLS, reg)


#  grouping
GROUP_COLS = ["motif_id", "motif_level", "top_risk", "architecture_classes", "shared_context", "general_motif_id",
              "number_of_incidents", "sent_to_llm", "incidents", "motif_hash"]
DEFAULT_SPECIFIC_CLASSES = ["Domain", "Task", "DataCategory", "DeploymentEnvironment", "Stakeholder", "AutonomyLevel",
                            "RegulatoryContext"]


def top_risk(answer: dict) -> str:
    rs = sorted(enumerate(answer["risks"]), key=lambda x: (CONF_RANK[x[1]["confidence"]], x[0]))
    return rs[0][1]["risk_id"] if rs else ""


def shape_of(answer: dict) -> str:
    return ",".join(sorted({e["class"] for e in answer["elements"]}))


def profile_contexts(answer: dict) -> set[str]:
    return {f"{c['class']}={c['existing']}" for c in answer["contexts"] if c["existing"] != "new"}


def group_profiles(cfg: Config) -> list[dict]:
    g = cfg["group"]
    profiles = [p for p in read_jsonl(Path(cfg.path("output_dir")) / "profiles.jsonl") if top_risk(p["answer"])]
    min_support = int(g.get("min_support", 1))
    spec_min = int(g.get("specific_min_support", min_support))
    spec_classes = set(g.get("specific_context_classes") or DEFAULT_SPECIFIC_CLASSES)

    general = defaultdict(list)
    for p in profiles:
        general[(top_risk(p["answer"]), shape_of(p["answer"]))].append(p["incident_id"])
    rows = []
    for (risk, classes), ids in sorted(general.items()):
        key = "m" + hashlib.sha256(f"{risk}|{classes}".encode()).hexdigest()[:10]
        rows.append({"motif_hash": key, "motif_level": "general", "top_risk": risk, "architecture_classes": classes,
                     "shared_context": "", "number_of_incidents": len(ids),
                     "sent_to_llm": "yes" if len(ids) >= min_support else f"no (< min_support {min_support})",
                     "incidents": " ".join(sorted(ids))})
    kept_general = [r for r in rows if r["sent_to_llm"] == "yes"]

    specific = defaultdict(list)
    for p in profiles:
        for ctx in profile_contexts(p["answer"]):
            if ctx.split("=", 1)[0] in spec_classes:
                specific[(shape_of(p["answer"]), ctx)].append(p)
    for (classes, ctx), members in sorted(specific.items()):
        ids = sorted(p["incident_id"] for p in members)
        risks = defaultdict(int)
        for p in members:
            risks[top_risk(p["answer"])] += 1
        risk = sorted(risks.items(), key=lambda x: (-x[1], x[0]))[0][0]      # most frequent top risk (for reading)
        overlap = sorted(((len(set(ids) & set(r["incidents"].split())), r["number_of_incidents"], r["motif_hash"], r)
                          for r in kept_general if r["architecture_classes"] == classes),
                         key=lambda x: (-x[0], -x[1], x[2]))
        parent = overlap[0][3] if overlap and overlap[0][0] else None
        if len(ids) < spec_min:
            status = f"no (< specific_min_support {spec_min})"
        elif parent and sorted(parent["incidents"].split()) == ids:
            status = "no (same incidents as its general motif)"
        else:
            status = "yes"
        key = "m" + hashlib.sha256(f"{classes}|{ctx}".encode()).hexdigest()[:10]
        rows.append({"motif_hash": key, "motif_level": "specific", "top_risk": risk, "architecture_classes": classes,
                     "shared_context": ctx, "parent_hash": parent["motif_hash"] if parent else "",
                     "number_of_incidents": len(ids), "sent_to_llm": status, "incidents": " ".join(ids)})
    assign_ids(cfg, rows)
    write_csv(Path(cfg.path("output_dir")) / "groups.csv", GROUP_COLS, rows)
    return rows


def level_block(g: dict, parent: dict | None) -> str:
    if g.get("motif_level", "general") == "general":
        return ("Level: **general**. These incidents share one architecture and the same top risk. Write the general "
                "motif of this architecture: require an application context only when the risk cannot arise without it.")
    cls, val = g["shared_context"].split("=", 1)
    lines = [f"Level: **specific**. These incidents share the architecture ({g['architecture_classes']}) and the application "
             f"context value `{val}` ({cls}). Write a more specific motif on top of the general one:",
             f"- keep the architecture (same element classes and the same uses/produces relations);",
             f"- require the context: class `{cls}`, existing `{val}` (you may add other values that "
             f"all these incidents share and that the risk needs);",
             "- choose the risk that this context makes characteristic. It may differ from the general motif's risk."]
    if parent:
        a = parent["answer"]
        ctx = "; ".join(f"{c['class']}={c['existing']}" for c in a["contexts"]) or "none"
        lines += ["", "The general motif of this architecture (keep its elements and relations):",
                  f"- name: {a['name']}", f"- risk: {a['risk_id']}", f"- architecture: {structure_text(a, mark=False)}",
                  f"- contexts: {ctx}", f"- manifest condition: {a['manifest_condition']}"]
    else:
        lines += ["", "No general motif of this architecture is available; take the architecture the profiles share."]
    return "\n".join(lines)


def shape_signature(answer: dict) -> tuple:
    cls = {e["id"]: e["class"] for e in answer["elements"]}
    return (tuple(sorted(cls.values())),
            tuple(sorted((cls.get(f["from"], "?"), f["relation"], cls.get(f["to"], "?")) for f in answer["flows"])))


def level_check(g: dict, parent: dict | None):
    if g.get("motif_level", "general") == "general":
        return lambda d: []
    cls, val = g["shared_context"].split("=", 1)

    def check(d: dict) -> list[str]:
        errs = []
        if not any(c["class"] == cls and c["existing"] == val for c in d["contexts"]):
            errs.append(f"specific motif must require the context {cls}={val}")
        if parent and shape_signature(d) != shape_signature(parent["answer"]):
            errs.append("specific motif must keep the general motif's architecture (element classes and relations)")
        return errs
    return check


# stage 2: abstraction
def profiles_block(profiles: list[dict]) -> str:
    out = []
    for p in profiles:
        a = p["answer"]
        cls = {e["id"]: e["class"] for e in a["elements"]}
        out.append(f"- incident: {p['incident_id']}\n  title: {p['title']}\n  architecture: {structure_text(a, mark=False)}\n"
                   f"  elements: " + "; ".join(f"{e['id']} {e['class']} ({e['label']})" for e in a["elements"]) + "\n"
                   f"  contexts: " + ("; ".join(f"{c['class']}={c['existing'] if c['existing'] != 'new' else c['value']}"
                                               for c in a["contexts"]) or "none") + "\n"
                   f"  failure point: {cls.get(a['failure_point'], 'not stated')}\n"
                   f"  risks: " + ("; ".join(f"{r['risk_id']} ({r['confidence']})" for r in a["risks"]) or "none") + "\n"
                   f"  certainty of the architecture: {a['confidence']}")
    return "\n".join(out)


def plan_motifs(cfg: Config, vocab: Vocab, limit: int | None = None, done: dict | None = None):
    done = done if done is not None else {}
    profiles = {p["incident_id"]: p for p in read_jsonl(Path(cfg.path("output_dir")) / "profiles.jsonl")}
    groups = read_csv(Path(cfg.path("output_dir")) / "groups.csv") if (Path(cfg.path("output_dir")) / "groups.csv").exists() else []
    risks = load_risks(cfg)
    base = json.loads(cfg.path("schema_motif").read_text(encoding="utf-8"))
    common = {"ontology_block": vocab.onto.render(), "element_classes_block": vocab.element_classes_block(),
              "context_values_block": vocab.context_values_block(), "max_elements": cfg["profile"]["max_elements"]}
    n = 0
    for g in groups:
        if limit is not None and n >= limit:
            break
        if g.get("sent_to_llm", "yes") != "yes":
            continue
        members = [profiles[i] for i in g["incidents"].split() if i in profiles][: cfg["group"]["max_profiles_per_call"]]
        if not members:
            continue
        n += 1
        cand = []
        for p in members:
            for r in p["answer"]["risks"]:
                if r["risk_id"] not in cand and r["risk_id"] in risks:
                    cand.append(r["risk_id"])
        parent = done.get(g.get("general_motif_id") or "")
        system, user = render(cfg.path("prompt_abstract"), {**common, "risks_block": risks_block(cand, risks),
                                                            "profiles_block": profiles_block(members),
                                                            "level_block": level_block(g, parent)})
        schema = fill_schema(base, element_classes=vocab.element_classes, context_classes=vocab.context_classes,
                             existing_ids=vocab.existing_ids(), risk_ids=cand,
                             support_ids=[p["incident_id"] for p in members],
                             limits={"elements": cfg["profile"]["max_elements"]})
        yield g, members, parent, system, user, schema


def run_motifs(cfg: Config, provider: Provider, vocab: Vocab, limit: int | None = None, log=print) -> dict:
    scfg = stage_cfg(cfg, "abstract")
    cache, psha, out = Cache(cfg.path("cache_dir")), prompt_sha(cfg), Path(cfg.path("output_dir"))
    rows, logs, stats, done = [], [], defaultdict(int), {}
    for g, members, parent, system, user, schema in plan_motifs(cfg, vocab, limit, done):
        extra = level_check(g, parent)
        data, entry, lrow = call(scfg, provider, cache, system, user, schema,
                                 lambda d: check_structure(d, vocab, "manifest_condition") +
                                 ([] if d["manifest_condition"] else ["manifest_condition is empty"]) + extra(d),
                                 g["motif_id"], log)
        logs.append(lrow)
        stats["cached" if lrow["cached"] else "called"] += lrow["status"] == "ok"
        if data is None:
            stats["skipped"] += 1
            continue
        row = {"motif_key": g["motif_id"], "motif_hash": g["motif_hash"], "level": g.get("motif_level", "general"),
               "context": g.get("shared_context", ""), "parent_key": g.get("general_motif_id", ""),
               "group_risk_id": g["top_risk"], "group_element_classes": g["architecture_classes"],
               "group_incident_ids": g["incidents"].split(),
               "answer": data, "model": cfg["model"], "model_version": entry.get("model_version", ""),
               "prompt_sha256": psha, "run_date": entry.get("run_date", "")}
        rows.append(row)
        done[g["motif_id"]] = row
    out.mkdir(parents=True, exist_ok=True)
    (out / "motifs.jsonl").write_text("".join(dumps(r) + "\n" for r in rows), encoding="utf-8")
    write_csv(out / "motif_log.csv", list(logs[0].keys()) if logs else ["id"], logs)
    stats["motifs"] = len(rows)
    return dict(stats)


# dry run and estimate
def remember_cached(scfg: Config, cache: Cache, stage: str, item: dict, system: str, user: str, schema: dict,
                    done: dict) -> bool:
    entry = cache.get(cache_key(scfg, system, user, api_schema(schema)))
    if entry is None:
        return False
    if stage == "abstract" and item.get("motif_level", "general") == "general":
        try:
            done[item["motif_id"]] = {"answer": json.loads(entry["text"])}
        except (ValueError, KeyError):
            pass
    return True


def dry_run(cfg: Config, vocab: Vocab, stage: str, limit: int | None = None) -> int:
    folder = Path(cfg.path("output_dir")) / "prompts_preview" / stage
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.md"):
        old.unlink()
    scfg, cache, done = stage_cfg(cfg, stage), Cache(cfg.path("cache_dir")), {}
    plan = plan_profiles(cfg, vocab, limit) if stage == "profile" else plan_motifs(cfg, vocab, limit, done)
    n = 0
    for t in plan:
        item, (system, user, schema) = t[0], t[-3:]
        remember_cached(scfg, cache, stage, item, system, user, schema, done)
        name = item["incident_id"] if stage == "profile" else item["motif_id"]
        (folder / f"{name}.md").write_text(
            f"# Prompt preview ({stage}): {name}\n\nmodel: {cfg['model']} | effort: {cfg['effort'][stage]} | "
            f"prompt_sha256: {prompt_sha(cfg)}\n\n## System\n\n{system}\n\n## User\n\n{user}\n\n"
            f"## Response schema (sent as output_config.format)\n\n```json\n{json.dumps(api_schema(schema), indent=2)}\n```\n",
            encoding="utf-8")
        n += 1
    return n


def estimate(cfg: Config, vocab: Vocab, stage: str, limit: int | None = None) -> dict:
    scfg = stage_cfg(cfg, stage)
    est, cache = cfg["estimate"], Cache(cfg.path("cache_dir"))
    done = {}
    plan = plan_profiles(cfg, vocab, limit) if stage == "profile" else plan_motifs(cfg, vocab, limit, done)
    calls = cached = in_tokens = 0
    for t in plan:
        item, (system, user, schema) = t[0], t[-3:]
        api = api_schema(schema)
        if remember_cached(scfg, cache, stage, item, system, user, schema, done):
            cached += 1
            continue
        calls += 1
        in_tokens += round((len(system) + len(user) + len(json.dumps(api))) / est["chars_per_token"])
    per_call = est["answer_tokens_per_call"][stage] + est["thinking_tokens_per_call"][scfg["effort"]]
    out_tokens = calls * per_call
    costs = {m: round(in_tokens / 1e6 * p["input"] + out_tokens / 1e6 * p["output"], 4) for m, p in cfg["pricing"].items()}
    return {"stage": stage, "model": cfg["model"], "effort": scfg["effort"], "calls": calls, "cached_free": cached,
            "input_tokens": in_tokens, "output_tokens_assumed": out_tokens, "output_tokens_per_call_assumed": per_call,
            "token_count_method": f"chars/{est['chars_per_token']}", "cost_usd_by_model": costs,
            "cost_usd_configured_model": costs.get(cfg["model"])}

from __future__ import annotations
import datetime as dt
from collections import defaultdict
from pathlib import Path
from llm_mitigation.config import Config, read_csv, write_csv
from . import accepted as accepted_mod
from .core import Vocab, element_text, slug, structure_text
from .stages import read_jsonl

NEW, EXTEND = "new motif", "add incident to accepted motif"
SHEET_COLS = ["review_item", "motif_id", "motif_level", "general_motif_id", "specific_for_context", "name",
              "description", "risk_id", "risk_name", "architecture", "required_contexts", "risk_appears_at",
              "based_on_incidents", "number_of_incidents", "few_incidents", "quotes_found_in_text",
              "matches_own_incidents", "matches_other_incidents", "broader_motif_same_risk", "llm_confidence",
              "llm_notes", "reviewer", "decision", "review_note", "model", "model_version", "prompt_sha256", "run_date"]
VALID = {"accept", "reject", ""}
RULES = ("all", "majority", "any")
STATUS_COLS = ["review_item", "motif_id", "based_on_incidents", "name", "number_of_decisions", "accept", "reject",
               "outcome", "reason", "reviewers"]


def sheet_path(cfg: Config, xlsx: bool = False, reviewer: str | None = None) -> Path:
    stem = f"review_sheet_{slug(reviewer)}" if reviewer else "review_sheet"
    return Path(cfg.path("output_dir")) / (stem + (".xlsx" if xlsx else ".csv"))


def read_sheet(path: Path) -> list[dict]:
    from llm_mitigation.apply import read_sheet as _read
    return [{**r, "review_item": (r.get("review_item") or "").strip()} for r in _read(Path(path))]


def _contexts_text(a: dict) -> str:
    return "; ".join(f"{x['class']}={x['existing'] if x['existing'] != 'new' else 'NEW ' + x['value']}"
                     for x in a["contexts"]) or "none"


def export(cfg: Config, xlsx: bool = False, force: bool = False, reviewer: str | None = None,
           vocab: Vocab | None = None) -> Path:
    out = sheet_path(cfg, xlsx, reviewer)
    if out.exists() and not force:
        if any((r.get("decision") or "").strip() for r in read_sheet(out)):
            raise SystemExit(f"{out} already holds review decisions; use --force to overwrite")
    risks = {r["nexus_id"]: r for r in read_csv(cfg.path("risks"))}
    out_dir = Path(cfg.path("output_dir"))
    profiles = {p["incident_id"]: p for p in read_jsonl(out_dir / "profiles.jsonl")}
    checks = {r["motif_id"]: r for r in read_csv(out_dir / "check.csv")} if (out_dir / "check.csv").exists() else {}
    acc_keys = accepted_mod.accepted_keys(cfg)
    rows = []
    for m in read_jsonl(out_dir / "motifs.jsonl"):
        if m["motif_key"] in acc_keys:                  # already reviewed and accepted: kept as it is
            continue
        a = m["answer"]
        sup = [s for s in a["support"] if s in profiles]
        c = checks.get(m["motif_key"], {})
        rows.append({
            "review_item": NEW, "motif_id": m["motif_key"], "motif_level": m.get("level", "general"),
            "general_motif_id": m.get("parent_key", ""), "specific_for_context": m.get("context", ""),
            "name": a["name"], "description": a["description"], "risk_id": a["risk_id"],
            "risk_name": risks.get(a["risk_id"], {}).get("name", ""), "architecture": structure_text(a),
            "required_contexts": _contexts_text(a), "risk_appears_at": element_text(a, a["manifest_condition"]),
            "based_on_incidents": " ".join(sup), "number_of_incidents": len(sup),
            "few_incidents": "yes" if len(sup) < cfg["group"]["min_support_flag"] else "",
            "quotes_found_in_text": f"{sum(profiles[s]['evidence_found'] for s in sup)} of "
                                    f"{sum(profiles[s]['evidence_total'] for s in sup)}",
            "matches_own_incidents": c.get("matches_own_incidents", ""),
            "matches_other_incidents": c.get("matches_other_incidents", ""),
            "broader_motif_same_risk": c.get("broader_motif_same_risk", ""),
            "llm_confidence": a["confidence"], "llm_notes": " | ".join(a["issues"]), "model": m["model"],
            "model_version": m["model_version"], "prompt_sha256": m["prompt_sha256"], "run_date": m["run_date"],
            "reviewer": reviewer or "", "decision": "", "review_note": ""})
    # each general motif, followed by the specific motifs built on it
    rows.sort(key=lambda r: (r["general_motif_id"] or r["motif_id"], r["motif_level"] != "general",
                             r["specific_for_context"], r["motif_id"]))
    rows += _extension_rows(cfg, vocab, profiles, risks, reviewer)
    if xlsx:
        from openpyxl import Workbook
        from openpyxl.worksheet.datavalidation import DataValidation
        wb = Workbook()
        ws = wb.active
        ws.append(SHEET_COLS)
        for r in rows:
            ws.append([r[c] for c in SHEET_COLS])
        dv = DataValidation(type="list", formula1='"accept,reject"', allow_blank=True)
        ws.add_data_validation(dv)
        col = chr(ord("A") + SHEET_COLS.index("decision"))
        dv.add(f"{col}2:{col}{len(rows) + 1}")
        out.parent.mkdir(parents=True, exist_ok=True)
        wb.save(out)
    else:
        write_csv(out, SHEET_COLS, rows)
    return out


def _extension_rows(cfg: Config, vocab: Vocab | None, profiles: dict, risks: dict, reviewer: str | None) -> list[dict]:
    path = Path(cfg.path("output_dir")) / "extensions.csv"
    ext = read_csv(path) if path.exists() else []
    if not ext:
        return []
    vocab = vocab or Vocab()
    acc = {m["motif_key"]: m for m in accepted_mod.load(cfg, vocab, {})}
    rows = []
    for e in sorted(ext, key=lambda x: (x["motif_id"], x["incident_id"])):
        m, p = acc.get(e["motif_id"]), profiles.get(e["incident_id"])
        if not m or not p:                              # stale file (motif or profile gone)
            continue
        a = m["answer"]
        rows.append({
            "review_item": EXTEND, "motif_id": e["motif_id"], "motif_level": "", "general_motif_id": "",
            "specific_for_context": "", "name": a["name"],
            "description": f"New incident {e['incident_id']}: {e['incident_title']} ({e['incident_url']}). "
                           f"Accept to add it as a source of this accepted motif.",
            "risk_id": a["risk_id"], "risk_name": risks.get(a["risk_id"], {}).get("name", ""),
            "architecture": structure_text(a), "required_contexts": _contexts_text(a),
            "risk_appears_at": element_text(a, a["manifest_condition"]),
            "based_on_incidents": e["incident_id"], "number_of_incidents": 1, "few_incidents": "",
            "quotes_found_in_text": f"{p['evidence_found']} of {p['evidence_total']}",
            "matches_own_incidents": "1 of 1", "matches_other_incidents": "", "broader_motif_same_risk": "",
            "llm_confidence": p["answer"].get("confidence", ""),
            "llm_notes": " | ".join(p["answer"].get("issues") or []), "model": p.get("model", ""),
            "model_version": p.get("model_version", ""), "prompt_sha256": p.get("prompt_sha256", ""),
            "run_date": p.get("run_date", ""), "reviewer": reviewer or "", "decision": "", "review_note": ""})
    return rows


#  combining several reviewers
def item_key(r: dict) -> tuple:
    return (r["review_item"], r["motif_id"], r["based_on_incidents"].strip() if r["review_item"] == EXTEND else "")


def collect(paths: list[Path]) -> tuple[dict[tuple, dict], list[str]]:
    """item -> {"row": first row seen, "votes": {reviewer: decision}}; plus sheet errors."""
    items, errors = {}, []
    for path in paths:
        for i, r in enumerate(read_sheet(Path(path)), start=2):
            where = f"{Path(path).name} row {i}"
            d = (r.get("decision") or "").strip().lower()
            who = (r.get("reviewer") or "").strip()
            if d not in VALID:
                errors.append(f"{where}: decision {r.get('decision')!r} is not accept/reject/empty")
                continue
            it = items.setdefault(item_key(r), {"row": r, "votes": {}})
            if not d:
                continue
            if not who:
                errors.append(f"{where}: {d} without a reviewer")
                continue
            if who in it["votes"]:
                errors.append(f"{where}: {who} already decided on this row in another sheet")
                continue
            it["votes"][who] = d
    return items, errors


def resolve(votes: dict[str, str], rule: str, min_reviewers: int) -> tuple[str, str]:
    """('accept' | 'reject' | '', reason)."""
    n, acc = len(votes), sum(1 for v in votes.values() if v == "accept")
    rej = n - acc
    if n == 0:
        return "", "no decision"
    if n < min_reviewers:
        return "", f"{n} of {min_reviewers} required reviewers"
    if rule == "all":
        return ("accept", "all accepted") if rej == 0 else ("reject", f"{rej} reject")
    if rule == "any":
        return ("accept", f"{acc} accept") if acc else ("reject", "all rejected")
    if acc > rej:
        return "accept", f"majority {acc}:{rej}"
    if rej > acc:
        return "reject", f"majority {rej}:{acc}"
    return "", f"tie {acc}:{rej}"


def review_rule(cfg: Config) -> tuple[str, int]:
    rc = cfg.get("review") or {}
    rule, mn = rc.get("rule", "all"), int(rc.get("min_reviewers", 1))
    if rule not in RULES:
        raise SystemExit(f"config review.rule {rule!r} is not one of {', '.join(RULES)}")
    return rule, max(mn, 1)


def status(cfg: Config, paths: list[Path]) -> dict:
    items, errors = collect(paths)
    rule, mn = review_rule(cfg)
    rows = []
    for k, it in sorted(items.items()):
        out, why = resolve(it["votes"], rule, mn)
        v = it["votes"]
        rows.append({"review_item": k[0], "motif_id": k[1], "based_on_incidents": it["row"]["based_on_incidents"],
                     "name": it["row"].get("name", ""), "number_of_decisions": len(v),
                     "accept": sum(1 for d in v.values() if d == "accept"),
                     "reject": sum(1 for d in v.values() if d == "reject"), "outcome": out or "undecided",
                     "reason": why, "reviewers": "; ".join(f"{w}={d}" for w, d in sorted(v.items()))})
    path = Path(cfg.path("output_dir")) / "review_status.csv"
    write_csv(path, STATUS_COLS, rows)
    return {"file": str(path), "rule": rule, "min_reviewers": mn, "rows": len(rows),
            "accept": sum(r["outcome"] == "accept" for r in rows), "reject": sum(r["outcome"] == "reject" for r in rows),
            "undecided": sum(r["outcome"] == "undecided" for r in rows),
            "disagreements": sum(1 for r in rows if r["accept"] and r["reject"]), "sheet_errors": errors}


#  apply
def apply(cfg: Config, review: Path | list[Path], vocab: Vocab | None = None) -> dict:
    paths = [Path(p) for p in (review if isinstance(review, (list, tuple)) else [review])]
    vocab = vocab or Vocab()
    base, ns = vocab.base, vocab.ns
    risks = {r["nexus_id"]: r for r in read_csv(cfg.path("risks"))}
    out_dir = Path(cfg.path("output_dir"))
    motifs = {m["motif_key"]: m for m in read_jsonl(out_dir / "motifs.jsonl")}
    profiles = {p["incident_id"]: p for p in read_jsonl(out_dir / "profiles.jsonl")}
    old = accepted_mod.read_tables(cfg)
    acc_keys = {r["identifier"] for r in old["motifs"]}
    rule, mn = review_rule(cfg)
    items, errors = collect(paths)
    decided = defaultdict(int)
    new_motifs, extends, kept, excluded = [], [], [], []
    for k, it in sorted(items.items()):
        outcome, _ = resolve(it["votes"], rule, mn)
        decided[outcome or "undecided"] += 1
        item, key, inc = k
        if outcome == "reject" and item == EXTEND and inc in profiles and profiles[inc].get("url"):
            excluded.append((key, inc, "; ".join(sorted(w for w, d in it["votes"].items() if d == "reject"))))
        if outcome != "accept":
            continue
        who = "; ".join(sorted(w for w, d in it["votes"].items() if d == "accept"))
        if item == NEW:
            if key in acc_keys:
                kept.append(key)                         # accepted earlier: the reviewed version stays
            elif key not in motifs:
                errors.append(f"motif {key}: unknown motif_id (not in output/motifs.jsonl)")
            elif motifs[key]["answer"]["risk_id"] not in risks:
                errors.append(f"motif {key}: risk {motifs[key]['answer']['risk_id']!r} not in staging/risks.csv")
            else:
                new_motifs.append((motifs[key], who))
        elif item == EXTEND:
            if key not in acc_keys and key not in {m["motif_key"] for m, _ in new_motifs}:
                errors.append(f"extend {key} {inc}: motif is not accepted")
            elif inc not in profiles or not profiles[inc].get("url"):
                errors.append(f"extend {key} {inc}: incident has no profile with a URL")
            else:
                extends.append((key, inc, who))
        else:
            errors.append(f"{key}: unknown review_item {item!r}")
    if errors:
        raise SystemExit("apply: review sheets have errors, nothing written:\n  " + "\n  ".join(errors))

    t = {k: [] for k in accepted_mod.TABLES}
    for m, who in sorted(new_motifs, key=lambda x: x[0]["motif_key"]):
        a, key = m["answer"], m["motif_key"]
        motif_iri, arch = f"{base}motif/{key}", f"{base}motif/{key}/architecture"
        el = lambda eid: f"{base}motif/{key}/{eid}"
        t["motifs"].append({"motif_iri": motif_iri, "identifier": key, "name": a["name"], "description": a["description"],
                            "risk_iri": risks[a["risk_id"]]["iri"], "manifest_iri": el(a["manifest_condition"]),
                            "architecture_iri": arch, "architecture_name": f"{a['name']}: architecture",
                            "architecture_description": f"{structure_text(a, mark=False)}. The risk appears at "
                                                        f"{element_text(a, a['manifest_condition'])}.",
                            "model": m["model"], "model_version": m["model_version"], "prompt_sha256": m["prompt_sha256"],
                            "run_date": m["run_date"], "reviewer": who})
        for e in a["elements"]:
            t["elements"].append({"architecture_iri": arch, "element_iri": el(e["id"]), "class_iri": ns + e["class"],
                                  "label": e.get("label", "")})
        for f in a["flows"]:
            t["flows"].append({"subject_iri": el(f["from"]), "predicate_iri": ns + f["relation"], "object_iri": el(f["to"])})
        for c in a["contexts"]:
            iri = vocab.context_iri(c)
            t["contexts"].append({"motif_iri": motif_iri, "context_iri": iri})
            if c["existing"] == "new":
                t["new_contexts"].append({"context_iri": iri, "class_iri": ns + c["class"], "name": c["value"],
                                          "description": f"{c['class']} value proposed by llm-motif (motif {key}); "
                                                         f"reviewed with the motif."})
        for s in a["support"]:
            if s in profiles and profiles[s].get("url"):
                t["sources"].append({"motif_iri": motif_iri, "source_url": profiles[s]["url"]})
    today = dt.date.today().isoformat()
    for key, inc, who in extends:
        t["sources"].append({"motif_iri": f"{base}motif/{key}", "source_url": profiles[inc]["url"], "reviewer": who,
                             "review_date": today})
    for key, inc, who in excluded:
        t["excluded_sources"].append({"motif_iri": f"{base}motif/{key}", "source_url": profiles[inc]["url"],
                                      "reviewer": who, "review_date": today})
    merged, added = accepted_mod.merge(old, t)
    accepted_mod.write_tables(cfg, merged)
    return {"sheets": len(paths), "rule": rule, "min_reviewers": mn, "rows": len(items),
            "accepted": decided["accept"], "rejected": decided["reject"], "undecided": decided["undecided"],
            "new_motifs": added["motifs"], "kept_already_accepted": len(kept), "new_sources": added["sources"],
            "rejected_sources_recorded": added["excluded_sources"],
            "accepted_motifs_total": len(merged["motifs"]), "elements_added": added["elements"],
            "flows_added": added["flows"], "new_context_values": added["new_contexts"]}

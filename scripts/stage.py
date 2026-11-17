"""Stage: clean, deterministic CSV inputs for the RML mappings (staging/).

Outputs (all sorted, LF, UTF-8):
  risks.csv                       one row per imported risk (+ minted IRIs, licence)
  catalogues.csv                  one row per catalogue (dataset description)
  crosswalks.csv                  risk<->risk SKOS links, both ends in risks.csv
  mit_controls.csv                MIT controls (-> ak:Mitigation)
  mit_control_groups.csv          MIT mitigation taxonomy (4 categories, 23 subcategories)
  mit_control_categorisation.csv  control -> group (+ top category)
  excluded_risks.csv, excluded_crosswalks.csv, excluded_causal_facets.csv, excluded_controls.csv
  stage_summary.json              counts
"""
from __future__ import annotations

import ast
import csv
import re
from collections import Counter
from pathlib import Path

import yaml

from scripts.common import (NEXUS_DIR, ROOT, STAGING, load_config, log, manifest, write_csv,
                            write_json)

EXPECTED = {"ibm": 99, "owasp": 10, "mit": 33}  # raw entry counts at the pinned Nexus commit


def y(rel: str) -> dict:
    with open(NEXUS_DIR / rel, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def read_sssom(rel: str) -> tuple[dict, list[dict]]:
    """Return (header metadata, rows) of an SSSOM TSV. Header lines start with '#'."""
    text = (NEXUS_DIR / rel).read_text(encoding="utf-8")
    lines = text.splitlines()
    meta = yaml.safe_load("\n".join(l[1:] for l in lines if l.startswith("#"))) or {}
    rows = list(csv.DictReader([l for l in lines if not l.startswith("#")], delimiter="\t"))
    return meta, rows


def as_list(v) -> list[str]:
    """Nexus stores some lists as their Python repr string: "['a', 'b']"."""
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    s = str(v).strip()
    if s.startswith("["):
        return [str(x) for x in ast.literal_eval(s)]
    return [s]


def clean(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def local(curie: str) -> str:
    return curie.split(":", 1)[1] if ":" in curie else curie


OWASP_CODE = re.compile(r"^LLM(\d{2}):(\d{4})$")
OWASP_ID = re.compile(r"^llm(\d{2})(\d{4})?-")


def owasp_code(name: str, nexus_id: str, issues: list) -> str:
    token = name.split()[0]
    if OWASP_CODE.match(token):
        return token
    m = OWASP_ID.match(nexus_id)
    if m and m.group(2):
        code = f"LLM{m.group(1)}:{m.group(2)}"
        issues.append(f"OWASP `{nexus_id}`: name token `{token}` has no year; identifier `{code}` derived from the id.")
        return code
    raise SystemExit(f"ERROR: cannot parse OWASP code from {name!r} / {nexus_id!r}")


def stage_risks(cfg: dict, issues: list) -> tuple[list[dict], list[dict], list[dict]]:
    base, nexus_iri = cfg["base_iri"], cfg["sources"]["nexus"]["entry_iri"]
    risks, excluded, catalogues = [], [], []
    for cat, c in cfg["catalogues"].items():
        data = y(c["nexus_file"])
        entries = [e for e in data["entries"] if e.get("type") == "Risk"]
        if len(entries) != EXPECTED[cat]:
            issues.append(f"{cat}: expected {EXPECTED[cat]} Risk entries, found {len(entries)}.")
        tax = {t["id"]: t for t in data.get("taxonomies", [])}
        main_tax = tax[c["taxonomy_id"]]
        catalogues.append({
            "catalogue": cat, "title": c["title"], "taxonomy_id": c["taxonomy_id"],
            "taxonomy_name": clean(main_tax["name"]), "catalogue_url": main_tax.get("url", ""),
            "license": c["license"], "license_name": c["license_name"],
            "rights_holder": c["rights_holder"], "attribution": c["attribution"],
            "copy_descriptions": str(bool(cfg["copy_descriptions"][cat])).lower(),
            "dataset_iri": f"{base}dataset/imported-risks-{cat}",
        })
        for e in entries:
            nid, name = e["id"], clean(e["name"])
            if e.get("isDefinedByTaxonomy") != c["taxonomy_id"]:
                if cat == "mit" and not cfg.get("mit_include_causal_facets", False):
                    excluded.append({"nexus_id": nid, "catalogue": cat, "name": name,
                                     "taxonomy_id": e.get("isDefinedByTaxonomy", ""),
                                     "reason": "MIT causal-taxonomy facet (entity/intent/timing), not a risk"})
                    continue
            if cat == "owasp":
                ident = owasp_code(name, nid, issues)
            elif cat == "mit":
                m = re.match(r"^mit-ai-risk-subdomain-(\d+\.\d+)$", nid)
                ident = m.group(1) if m else nid
            else:
                ident = nid
            url, note = e.get("url"), ""
            if not url:
                url = main_tax.get("url", "")
                note = "entry has no url; taxonomy url used"
            risks.append({
                "nexus_id": nid, "catalogue": cat, "name": name, "catalogue_identifier": ident,
                "source_url": url, "source_url_note": note,
                "taxonomy_id": e.get("isDefinedByTaxonomy", ""),
                "description": clean(e.get("description")) if cfg["copy_descriptions"][cat] else "",
                "iri": f"{base}risk/{nid}", "nexus_iri": nexus_iri.format(nexus_id=nid),
                "license": c["license"], "catalogue_url": main_tax.get("url", ""),
            })
    risks.sort(key=lambda r: (r["catalogue"], r["nexus_id"]))
    excluded.sort(key=lambda r: r["nexus_id"])
    dup = [k for k, v in Counter(r["nexus_id"] for r in risks).items() if v > 1]
    if dup:
        raise SystemExit(f"ERROR: duplicate nexus_id in risks: {dup}")
    return risks, excluded, catalogues


SKOS = "http://www.w3.org/2004/02/skos/core#"


def stage_crosswalks(cfg: dict, risk_ids: set[str]) -> tuple[list[dict], list[dict], list[dict], dict]:
    base = cfg["base_iri"]
    kept, excluded, causal, per_file = [], [], [], {}
    seen = set()
    for spec in cfg["crosswalks"]:
        rel = spec["file"]
        meta, rows = read_sssom(rel)
        fname = Path(rel).name
        stats = Counter(raw=len(rows))
        for r in rows:
            s, o, p = local(r["subject_id"]), local(r["object_id"]), r["predicate_id"]
            date = r.get("mapping_date") or str(meta.get("mapping_date", ""))
            row = {"subject_nexus_id": s, "predicate": p.split(":", 1)[1], "object_nexus_id": o,
                   "justification": r.get("mapping_justification", ""), "author": r.get("author_label", ""),
                   "mapping_date": date, "mapping_file": fname}
            reason = None
            if r["object_id"] == "sssom:NoTermFound":
                reason = "object sssom:NoTermFound"
            elif (r.get("predicate_modifier") or "").strip() == "Not" and cfg.get("crosswalk_drop_negated", True):
                reason = "predicate_modifier Not (negated mapping)"
            elif r["object_id"].startswith("mit-ai-risk-repository-causal:"):
                causal.append({**row, "reason": "object is an MIT causal-taxonomy facet, not a risk"})
                stats["causal_facet"] += 1
                continue
            elif not p.startswith("skos:"):
                reason = f"predicate {p} is not SKOS"
            elif s not in risk_ids or o not in risk_ids:
                reason = "an end is not an imported risk"
            elif (s, row["predicate"], o) in seen:
                reason = "duplicate row"
            if reason:
                excluded.append({**row, "reason": reason})
                stats[reason] += 1
                continue
            seen.add((s, row["predicate"], o))
            kept.append({**row, "subject_iri": f"{base}risk/{s}", "predicate_iri": SKOS + row["predicate"],
                         "object_iri": f"{base}risk/{o}"})
            stats["kept"] += 1
        per_file[fname] = dict(sorted(stats.items()))
    key = lambda r: (r["mapping_file"], r["subject_nexus_id"], r["predicate"], r["object_nexus_id"])
    return sorted(kept, key=key), sorted(excluded, key=key), sorted(causal, key=key), per_file


def stage_mitigations(cfg: dict, issues: list) -> dict:
    base, nexus_iri, mm = cfg["base_iri"], cfg["sources"]["nexus"]["entry_iri"], cfg["mit_mitigations"]
    gdata = y(mm["groups_file"])
    tax_url = gdata["taxonomies"][0]["url"]
    docs = {d["id"]: d.get("url", "") for d in gdata.get("documents", [])}
    groups = {}
    for g in gdata["groups"]:
        broader = as_list(g.get("broader"))
        groups[g["id"]] = {"group_id": g["id"], "name": clean(g["name"]), "description": clean(g.get("description")),
                           "broader_id": broader[0] if broader else "", "level": 2 if broader else 1}
    top_name = lambda gid: groups[gid]["name"] if not groups[gid]["broader_id"] else groups[groups[gid]["broader_id"]]["name"]
    top_id = lambda gid: gid if not groups[gid]["broader_id"] else groups[gid]["broader_id"]
    tech = mm["technical_category_name"]
    if not any(re.sub(r"^\d+\.\s*", "", g["name"]) == tech for g in groups.values() if g["level"] == 1):
        raise SystemExit(f"ERROR: technical category {tech!r} not found among MIT top categories")

    _, cat_rows = read_sssom(mm["categorisation_file"])
    categorisation, cat_of = [], {}
    for r in cat_rows:
        cid, gid = local(r["subject_id"]), local(r["object_id"])
        cat_of.setdefault(cid, []).append(gid)
        categorisation.append({"control_id": cid, "group_id": gid, "top_category_id": top_id(gid),
                               "justification": r.get("mapping_justification", ""),
                               "author": r.get("author_label", ""), "mapping_date": r.get("mapping_date", "")})

    controls, excluded, unknown_docs = [], [], Counter()
    seen = set()
    for c in y(mm["controls_file"])["controls"]:
        cid = c["id"]
        if cid in seen:
            excluded.append({"control_id": cid, "reason": "duplicate id"})
            continue
        seen.add(cid)
        doc_ids = as_list(c.get("hasDocumentation"))
        urls = [docs[d] for d in doc_ids if docs.get(d)]
        for d in doc_ids:
            if not docs.get(d):
                unknown_docs[d] += 1
        gids = sorted(set(cat_of.get(cid, [])))
        tops = sorted({re.sub(r"^\d+\.\s*", "", top_name(g)) for g in gids})
        if not gids:
            klass, note = "Mitigation", "not categorised in the MIT mitigation taxonomy"
        elif len(tops) > 1:
            klass, note = "Mitigation", f"categorised under several top categories: {tops}"
        else:
            klass = "TechnicalMitigation" if tops[0] == tech else "OrganisationalMitigation"
            note = ""
        controls.append({
            "nexus_id": cid, "name": clean(c["name"]),
            "description": clean(c.get("description")) if cfg["copy_descriptions"]["mit"] else "",
            "group_ids": " ".join(gids), "top_category": tops[0] if len(tops) == 1 else "",
            "mitigation_class": klass, "class_note": note,
            "source_url": urls[0] if urls else tax_url,
            "source_url_note": "" if urls else f"document {doc_ids} has no url in Nexus; taxonomy url used",
            "documentation_ids": " ".join(doc_ids),
            "iri": f"{base}mitigation/{cid}", "nexus_iri": nexus_iri.format(nexus_id=cid),
            "license": mm["license"], "catalogue_url": mm["source_url"],
        })
    if unknown_docs:
        issues.append("MIT controls cite documentation ids without a url in `mit_ai_risk_mitigation_data.yaml` "
                      f"(taxonomy url used as `ak:source`): {dict(sorted(unknown_docs.items()))}.")
    controls.sort(key=lambda r: r["nexus_id"])
    categorisation.sort(key=lambda r: (r["control_id"], r["group_id"]))
    return {"controls": controls, "groups": sorted(groups.values(), key=lambda g: g["group_id"]),
            "categorisation": categorisation, "excluded": excluded}


def stage_ibm_hints(cfg: dict, risk_ids: set[str]) -> list[dict]:
    """IBM Risk Atlas fields that say where a risk arises (used only for the pattern-coverage report)."""
    data = y(cfg["catalogues"]["ibm"]["nexus_file"])
    groups = {g["id"]: clean(g["name"]) for g in data.get("groups", [])}
    rows = []
    for e in data["entries"]:
        if e["id"] not in risk_ids:
            continue
        rows.append({"nexus_id": e["id"], "risk_type": clean(e.get("risk_type")),
                     "descriptors": "; ".join(clean(d) for d in as_list(e.get("descriptor"))),
                     "ibm_group_id": e.get("isPartOf", ""), "ibm_group": groups.get(e.get("isPartOf", ""), "")})
    return sorted(rows, key=lambda r: r["nexus_id"])


RISK_COLS = ["nexus_id", "catalogue", "name", "catalogue_identifier", "source_url", "source_url_note",
             "taxonomy_id", "description", "iri", "nexus_iri", "license", "catalogue_url"]
XW_COLS = ["subject_nexus_id", "predicate", "object_nexus_id", "justification", "author", "mapping_date",
           "mapping_file"]
CTL_COLS = ["nexus_id", "name", "description", "group_ids", "top_category", "mitigation_class", "class_note",
            "source_url", "source_url_note", "documentation_ids", "iri", "nexus_iri", "license", "catalogue_url"]


def main() -> None:
    if not (NEXUS_DIR / "knowledge_graph").exists():
        log("stage: sources/nexus missing - run fetch first; skipped")
        return
    cfg = load_config()
    issues: list[str] = []
    risks, ex_risks, catalogues = stage_risks(cfg, issues)
    xw, ex_xw, causal, xw_stats = stage_crosswalks(cfg, {r["nexus_id"] for r in risks})
    mit = stage_mitigations(cfg, issues)
    hints = stage_ibm_hints(cfg, {r["nexus_id"] for r in risks})

    write_csv(STAGING / "ibm_risk_hints.csv", ["nexus_id", "risk_type", "descriptors", "ibm_group_id", "ibm_group"], hints)
    write_csv(STAGING / "risks.csv", RISK_COLS, risks)
    write_csv(STAGING / "catalogues.csv", list(catalogues[0].keys()), sorted(catalogues, key=lambda c: c["catalogue"]))
    write_csv(STAGING / "crosswalks.csv", XW_COLS + ["subject_iri", "predicate_iri", "object_iri"], xw)
    write_csv(STAGING / "excluded_risks.csv", ["nexus_id", "catalogue", "name", "taxonomy_id", "reason"], ex_risks)
    write_csv(STAGING / "excluded_crosswalks.csv", XW_COLS + ["reason"], ex_xw)
    write_csv(STAGING / "excluded_causal_facets.csv", XW_COLS + ["reason"], causal)
    write_csv(STAGING / "mit_controls.csv", CTL_COLS, mit["controls"])
    write_csv(STAGING / "mit_control_groups.csv", ["group_id", "name", "description", "broader_id", "level"], mit["groups"])
    write_csv(STAGING / "mit_control_categorisation.csv",
              ["control_id", "group_id", "top_category_id", "justification", "author", "mapping_date"], mit["categorisation"])
    write_csv(STAGING / "excluded_controls.csv", ["control_id", "reason"], mit["excluded"])

    summary = {
        "nexus_commit": manifest().get("nexus", {}).get("commit", ""),
        "fetched": manifest().get("nexus", {}).get("fetched", ""),
        "risks_per_catalogue": dict(sorted(Counter(r["catalogue"] for r in risks).items())),
        "risks_excluded": len(ex_risks),
        "crosswalks_kept": len(xw),
        "crosswalks_per_predicate": dict(sorted(Counter(r["predicate"] for r in xw).items())),
        "crosswalks_per_file": xw_stats,
        "crosswalks_excluded_causal_facets": len(causal),
        "mit_controls": len(mit["controls"]),
        "mit_controls_per_class": dict(sorted(Counter(c["mitigation_class"] for c in mit["controls"]).items())),
        "mit_control_groups": len(mit["groups"]),
        "mit_categorisation_rows": len(mit["categorisation"]),
        "issues": issues,
    }
    write_json(STAGING / "stage_summary.json", summary)
    for k, v in summary.items():
        if k != "issues":
            log(f"  {k}: {v}")
    for i in issues:
        log(f"  ISSUE: {i}")
    log(f"stage: wrote {len(list(STAGING.glob('*.csv')))} CSV files to {STAGING.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()

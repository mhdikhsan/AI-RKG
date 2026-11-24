"""Stage: clean, deterministic CSV inputs for the RML mappings (staging/).

Outputs (all sorted, LF, UTF-8):
  risks.csv                       one row per imported risk (+ minted IRIs, licence)
  catalogues.csv                  one row per catalogue (dataset description)
  crosswalks.csv                  risk<->risk SKOS links, both ends in risks.csv
  mit_controls.csv                MIT controls (-> ak:Mitigation)
  mit_control_groups.csv          MIT mitigation taxonomy (4 categories, 23 subcategories)
  mit_control_categorisation.csv  control -> group (+ top category)
  excluded_risks.csv, excluded_crosswalks.csv, excluded_causal_facets.csv, excluded_controls.csv
  manual_mitigation_links.csv     author-curated control -> risk links (config manual_mitigation_links)
  incidents.csv                   AIID incidents + AVID records for llm_motif (git-ignored: CC BY-SA text)
  stage_summary.json              counts
"""
from __future__ import annotations

import ast
import csv
import json
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


MANUAL_LINK_COLS = ["risk_id", "risk_iri", "mitigation_id", "mitigation_iri", "via", "skos_match_type",
                    "reviewer", "source_file"]


def stage_manual_links(cfg: dict, risks: list[dict], controls: list[dict]) -> list[dict]:
    """Author-curated risk -> mitigation links (reviewed). Each row links the MIT control to both the
    OWASP and the IBM risk of the row. Unknown ids stop the step (nothing is guessed)."""
    mcfg = cfg.get("manual_mitigation_links")
    if not mcfg:
        return []
    path = ROOT / mcfg["file"]
    if not path.exists():
        log(f"stage: {mcfg['file']} missing; no manual mitigation links")
        return []
    risk_iri = {r["nexus_id"]: r["iri"] for r in risks}
    ctl_iri = {c["nexus_id"]: c["iri"] for c in controls}

    def fix(cid: str) -> str:
        cid = cid.strip()
        for f in mcfg.get("id_fixes", []):
            cid = cid.replace(f["find"], f["replace"])
        return cid

    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    out, seen, problems = [], set(), []
    for i, r in enumerate(rows, start=2):
        mid = fix(r["mit_action_id"])
        if mid not in ctl_iri:
            problems.append(f"row {i}: MIT control {r['mit_action_id']!r} (fixed: {mid!r}) not in staging/mit_controls.csv")
            continue
        for via, rid in (("owasp", r["owasp_id"].strip()), ("ibm", r["ibm_risk_id"].strip())):
            if rid not in risk_iri:
                problems.append(f"row {i}: risk {rid!r} not in staging/risks.csv")
                continue
            if (rid, mid) in seen:
                continue
            seen.add((rid, mid))
            out.append({"risk_id": rid, "risk_iri": risk_iri[rid], "mitigation_id": mid, "mitigation_iri": ctl_iri[mid],
                        "via": via, "skos_match_type": r.get("skos_match_type", "").strip(),
                        "reviewer": mcfg.get("reviewer", ""), "source_file": mcfg["file"]})
    if problems:
        raise SystemExit("stage: manual mitigation links have unknown ids:\n  " + "\n  ".join(problems))
    return sorted(out, key=lambda r: (r["risk_id"], r["mitigation_id"]))


INCIDENT_COLS = ["incident_id", "source", "record_class", "title", "description", "url", "date",
                 "deployer", "developer", "harmed_parties",
                 "mit_risk_ids", "mit_entity", "mit_timing", "mit_intent",
                 "gmf_goal", "gmf_technology", "gmf_failure", "gmf_potential_technology", "gmf_potential_failure",
                 "gmf_published",
                 "cset_sector", "cset_autonomy", "cset_ai_task", "cset_data_inputs",
                 "avid_artifacts", "avid_lifecycle", "avid_sep", "avid_risk_domain", "license"]
MIT_SUBDOMAIN = re.compile(r"^\s*(\d+\.\d+)\.")


def _cell(v) -> str:
    s = "" if v is None else str(v)
    return "" if s.lower() == "nan" else clean(s)


def _join(values) -> str:
    """'; '-joined, de-duplicated, order kept (multi-valued taxonomy fields)."""
    out = []
    for v in values:
        for part in str(v).split(","):
            p = clean(part)
            if p and p.lower() != "nan" and p not in out:
                out.append(p)
    return "; ".join(out)


def stage_incidents(cfg: dict, risks: list[dict]) -> tuple[list[dict], dict]:
    """AIID incidents (with MIT / GMF / CSETv1 classifications) and AVID records -> one table.

    MIT subdomain labels ('7.3. Lack of ...') are resolved to the imported MIT risks
    (nexus id mit-ai-risk-subdomain-7.3); everything else stays as text for the LLM step.
    """
    icfg, out, stats = cfg.get("incidents", {}), [], Counter()
    mit_ids = {r["catalogue_identifier"]: r["nexus_id"] for r in risks if r["catalogue"] == "mit"}
    a = cfg["sources"].get("aiid")
    ex = ROOT / "sources" / "aiid" / "extracted"
    if a and (ex / "incidents.csv").exists():
        def table(name):
            with open(ex / name, encoding="utf-8-sig", newline="") as fh:
                return list(csv.DictReader(fh))
        by_inc = lambda rows: {str(r["Incident ID"]).strip(): r for r in rows}
        mit, cset = table("classifications_MIT.csv"), by_inc(table("classifications_CSETv1.csv"))
        gmf = by_inc(r for r in table("classifications_GMF.csv")
                     if not icfg.get("aiid", {}).get("gmf_published_only") or r.get("Published") == "True")
        mit_by = {}
        for r in mit:
            mit_by.setdefault(str(r["Incident ID"]).strip(), []).append(r)
        for inc in table("incidents.csv"):
            iid = str(inc["incident_id"]).strip()
            m, g, c = mit_by.get(iid, []), gmf.get(iid, {}), cset.get(iid, {})
            risk_ids, unresolved = [], []
            for r in m:
                k = MIT_SUBDOMAIN.match(r.get("Risk Subdomain") or "")
                (risk_ids if k and k.group(1) in mit_ids else unresolved).append(
                    mit_ids[k.group(1)] if k and k.group(1) in mit_ids else (r.get("Risk Subdomain") or ""))
            stats["aiid_unresolved_mit_labels"] += len([u for u in unresolved if u])
            out.append({
                "incident_id": f"aiid-{iid}", "source": "aiid", "record_class": "AIID incident",
                "title": _cell(inc.get("title")), "description": _cell(inc.get("description")),
                "url": a["incident_url"].format(incident_id=iid), "date": _cell(inc.get("date")),
                "deployer": _cell(inc.get("Alleged deployer of AI system")),
                "developer": _cell(inc.get("Alleged developer of AI system")),
                "harmed_parties": _cell(inc.get("Alleged harmed or nearly harmed parties")),
                "mit_risk_ids": " ".join(sorted(set(risk_ids))),
                "mit_entity": _join(r.get("Entity", "") for r in m), "mit_timing": _join(r.get("Timing", "") for r in m),
                "mit_intent": _join(r.get("Intent", "") for r in m),
                "gmf_goal": _join([g.get("Known AI Goal", "")]), "gmf_technology": _join([g.get("Known AI Technology", "")]),
                "gmf_failure": _join([g.get("Known AI Technical Failure", "")]),
                "gmf_potential_technology": _join([g.get("Potential AI Technology", "")]),
                "gmf_potential_failure": _join([g.get("Potential AI Technical Failure", "")]),
                "gmf_published": (g.get("Published", "") or "").lower() if g else "",
                # CSET values contain commas inside a value (e.g. "Arts, entertainment and recreation"): no splitting
                "cset_sector": _cell(c.get("Sector of Deployment")), "cset_autonomy": _cell(c.get("Autonomy Level")),
                "cset_ai_task": _cell(c.get("AI Task")), "cset_data_inputs": _cell(c.get("Data Inputs")),
                "avid_artifacts": "", "avid_lifecycle": "", "avid_sep": "", "avid_risk_domain": "",
                "license": a["license"]})
            stats["aiid"] += 1
            stats["aiid_with_mit"] += bool(risk_ids)
            stats["aiid_with_gmf"] += bool(g)
            stats["aiid_with_cset"] += bool(c)
    v = cfg["sources"].get("avid")
    root = ROOT / "sources" / "avid"
    if v and root.exists():
        excl = set(icfg.get("avid", {}).get("exclude_classof", []))
        for p in v["paths"]:
            for f in sorted((root / p).rglob("*.json")):
                d = json.loads(f.read_text(encoding="utf-8"))
                pt = d.get("problemtype") or {}
                klass = pt.get("classof") or ""
                if klass in excl:
                    stats["avid_excluded"] += 1
                    continue
                meta = d.get("metadata") or {}
                rid = meta.get("report_id") or meta.get("vuln_id") or f.stem
                av = (d.get("impact") or {}).get("avid") or {}
                aff = d.get("affects") or {}
                refs = [r.get("url") for r in d.get("references") or [] if r.get("url")]
                out.append({
                    "incident_id": f"avid-{rid}", "source": "avid", "record_class": klass or "(none)",
                    "title": _cell((pt.get("description") or {}).get("value")),
                    "description": _cell((d.get("description") or {}).get("value")),
                    "url": refs[0] if refs else "", "date": d.get("reported_date") or d.get("published_date") or "",
                    "deployer": "; ".join(aff.get("deployer") or []), "developer": "; ".join(aff.get("developer") or []),
                    "harmed_parties": "", "mit_risk_ids": "", "mit_entity": "", "mit_timing": "", "mit_intent": "",
                    "gmf_goal": "", "gmf_technology": "", "gmf_failure": "", "gmf_potential_technology": "",
                    "gmf_potential_failure": "", "gmf_published": "",
                    "cset_sector": "", "cset_autonomy": "", "cset_ai_task": "", "cset_data_inputs": "",
                    "avid_artifacts": "; ".join(f"{x.get('type')}: {x.get('name')}" for x in aff.get("artifacts") or []),
                    "avid_lifecycle": "; ".join(av.get("lifecycle_view") or []), "avid_sep": "; ".join(av.get("sep_view") or []),
                    "avid_risk_domain": "; ".join(av.get("risk_domain") or []), "license": v["license"]})
                stats["avid"] += 1
    return sorted(out, key=lambda r: (r["source"], r["incident_id"])), dict(sorted(stats.items()))


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
    manual_links = stage_manual_links(cfg, risks, mit["controls"])
    incidents, incident_stats = stage_incidents(cfg, risks)
    if incidents:
        write_csv(STAGING / "incidents.csv", INCIDENT_COLS, incidents)

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
    if cfg.get("manual_mitigation_links"):
        write_csv(STAGING / "manual_mitigation_links.csv", MANUAL_LINK_COLS, manual_links)

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
        "manual_mitigation_links": len(manual_links),
        "manual_mitigation_links_per_catalogue": dict(sorted(Counter(r["via"] for r in manual_links).items())),
        "incidents": incident_stats,
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

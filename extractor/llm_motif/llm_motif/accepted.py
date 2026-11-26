from __future__ import annotations
from pathlib import Path
from llm_mitigation.config import Config, read_csv, write_csv

MOTIF_COLS = ["motif_iri", "identifier", "name", "description", "risk_iri", "manifest_iri", "architecture_iri",
              "architecture_name", "architecture_description", "model", "model_version", "prompt_sha256", "run_date",
              "reviewer"]
ELEMENT_COLS = ["architecture_iri", "element_iri", "class_iri", "label"]
FLOW_COLS = ["subject_iri", "predicate_iri", "object_iri"]
CONTEXT_COLS = ["motif_iri", "context_iri"]
NEW_CONTEXT_COLS = ["context_iri", "class_iri", "name", "description"]
SOURCE_COLS = ["motif_iri", "source_url", "reviewer", "review_date"]

TABLES = {"motifs": ("accepted_motifs.csv", MOTIF_COLS, ("motif_iri",)),
          "elements": ("accepted_motif_elements.csv", ELEMENT_COLS, ("element_iri",)),
          "flows": ("accepted_motif_flows.csv", FLOW_COLS, ("subject_iri", "predicate_iri", "object_iri")),
          "contexts": ("accepted_motif_contexts.csv", CONTEXT_COLS, ("motif_iri", "context_iri")),
          "new_contexts": ("accepted_motif_new_contexts.csv", NEW_CONTEXT_COLS, ("context_iri",)),
          "sources": ("accepted_motif_sources.csv", SOURCE_COLS, ("motif_iri", "source_url")),
          "excluded_sources": ("excluded_motif_sources.csv", SOURCE_COLS, ("motif_iri", "source_url"))}


def read_tables(cfg: Config) -> dict[str, list[dict]]:
    adir = Path(cfg.path("accepted_dir"))
    out = {}
    for name, (fname, cols, _) in TABLES.items():
        p = adir / fname
        out[name] = [{c: r.get(c, "") or "" for c in cols} for r in read_csv(p)] if p.exists() else []
    return out


def accepted_keys(cfg: Config) -> set[str]:
    return {r["identifier"] for r in read_tables(cfg)["motifs"]}


def merge(old: dict[str, list[dict]], new: dict[str, list[dict]]) -> tuple[dict[str, list[dict]], dict[str, int]]:
    out, added = {}, {}
    for name, (_, cols, key) in TABLES.items():
        rows = list(old.get(name, []))
        seen = {tuple(r[k] for k in key) for r in rows}
        n = 0
        for r in new.get(name, []):
            k = tuple(r[c] for c in key)
            if k in seen:
                continue
            seen.add(k)
            rows.append({c: r.get(c, "") for c in cols})
            n += 1
        out[name], added[name] = rows, n
    return out, added


def write_tables(cfg: Config, tables: dict[str, list[dict]]) -> None:
    adir = Path(cfg.path("accepted_dir"))
    for name, (fname, cols, _) in TABLES.items():
        rows = sorted(({c: r.get(c, "") for c in cols} for r in tables.get(name, [])),
                      key=lambda x: tuple(x[c] for c in cols))
        write_csv(adir / fname, cols, rows)


def load(cfg: Config, vocab, incident_by_url: dict[str, str]) -> list[dict]:
    t = read_tables(cfg)
    if not t["motifs"]:
        return []
    ns, base = vocab.ns, vocab.base
    risk_id = {r["iri"]: r["nexus_id"] for r in read_csv(cfg.path("risks"))}
    ctx_class = {f"{ns}{i}": c for c, vals in vocab.existing.items() for i, _ in vals}
    ctx_class.update({r["context_iri"]: r["class_iri"][len(ns):] for r in t["new_contexts"]})
    ctx_name = {r["context_iri"]: r["name"] for r in t["new_contexts"]}
    local = lambda iri: iri.rsplit("/", 1)[-1]
    out = []
    for m in t["motifs"]:
        key, prefix = m["identifier"], f"{base}motif/{m['identifier']}/"
        els = [{"id": local(e["element_iri"]), "class": e["class_iri"][len(ns):], "label": e["label"]}
               for e in t["elements"] if e["architecture_iri"] == m["architecture_iri"]]
        flows = [{"from": local(f["subject_iri"]), "relation": f["predicate_iri"][len(ns):], "to": local(f["object_iri"])}
                 for f in t["flows"] if f["subject_iri"].startswith(prefix)]
        ctxs = []
        for c in t["contexts"]:
            if c["motif_iri"] != m["motif_iri"]:
                continue
            iri = c["context_iri"]
            existing = iri[len(ns):] if iri.startswith(ns) else "new"
            ctxs.append({"class": ctx_class.get(iri, "ApplicationContext"), "existing": existing,
                         "value": ctx_name.get(iri, existing), "iri": iri})
        urls = {s["source_url"] for s in t["sources"] if s["motif_iri"] == m["motif_iri"]}
        excluded = {s["source_url"] for s in t["excluded_sources"] if s["motif_iri"] == m["motif_iri"]}
        out.append({"motif_key": key, "accepted": True, "sources": urls, "excluded": excluded, "answer": {
            "name": m["name"], "description": m["description"],
            "risk_id": risk_id.get(m["risk_iri"], m["risk_iri"]), "risk_iri": m["risk_iri"],
            "elements": els, "flows": flows, "contexts": ctxs, "manifest_condition": local(m["manifest_iri"]),
            "support": sorted(incident_by_url[u] for u in urls if u in incident_by_url),
            "confidence": "", "issues": []}})
    return out


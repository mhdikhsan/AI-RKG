"""Review sheet (one row per motif proposal) and `apply`: accepted motifs goes flat CSVs for RML."""
from __future__ import annotations

from pathlib import Path

from llm_mitigation.config import Config, read_csv, write_csv

from .core import Vocab, slug, structure_text
from .stages import read_jsonl

SHEET_COLS = ["motif_key", "level", "required_context", "parent", "name", "description", "risk_id", "risk_name", "structure", "contexts", "manifest_condition",
              "support", "n_support", "small_group", "evidence_found", "evidence_total", "check_fires_on_support",
              "check_fires_elsewhere", "covered_by", "confidence", "issues", "model", "model_version", "prompt_sha256", "run_date",
              "reviewer", "decision", "review_note"]
VALID = {"accept", "reject", ""}

MOTIF_COLS = ["motif_iri", "identifier", "name", "description", "risk_iri", "manifest_iri", "architecture_iri",
              "architecture_name", "architecture_description", "model", "model_version", "prompt_sha256", "run_date",
              "reviewer"]
ELEMENT_COLS = ["architecture_iri", "element_iri", "class_iri"]
FLOW_COLS = ["subject_iri", "predicate_iri", "object_iri"]
CONTEXT_COLS = ["motif_iri", "context_iri"]
NEW_CONTEXT_COLS = ["context_iri", "class_iri", "name", "description"]
SOURCE_COLS = ["motif_iri", "source_url"]


def sheet_path(cfg: Config, xlsx: bool = False) -> Path:
    return Path(cfg.path("output_dir")) / ("review_sheet.xlsx" if xlsx else "review_sheet.csv")


def export(cfg: Config, xlsx: bool = False, force: bool = False) -> Path:
    out = sheet_path(cfg, xlsx)
    if out.exists() and not force:
        from llm_mitigation.apply import read_sheet
        if any((r.get("decision") or "").strip() for r in read_sheet(out)):
            raise SystemExit(f"{out} already holds review decisions; use --force to overwrite")
    risks = {r["nexus_id"]: r for r in read_csv(cfg.path("risks"))}
    out_dir = Path(cfg.path("output_dir"))
    profiles = {p["incident_id"]: p for p in read_jsonl(out_dir / "profiles.jsonl")}
    checks = {r["motif_key"]: r for r in read_csv(out_dir / "check.csv")} if (out_dir / "check.csv").exists() else {}
    rows = []
    for m in read_jsonl(out_dir / "motifs.jsonl"):
        a = m["answer"]
        sup = [s for s in a["support"] if s in profiles]
        c = checks.get(m["motif_key"], {})
        rows.append({
            "motif_key": m["motif_key"], "level": m.get("level", "general"), "required_context": m.get("context", ""),
            "parent": m.get("parent_key", ""), "name": a["name"], "description": a["description"], "risk_id": a["risk_id"],
            "risk_name": risks.get(a["risk_id"], {}).get("name", ""), "structure": structure_text(a),
            "contexts": "; ".join(f"{x['class']}={x['existing'] if x['existing'] != 'new' else 'NEW ' + x['value']}"
                                  for x in a["contexts"]) or "none",
            "manifest_condition": a["manifest_condition"] + " " + next((e["class"] for e in a["elements"]
                                                                        if e["id"] == a["manifest_condition"]), "?"),
            "support": " ".join(sup), "n_support": len(sup),
            "small_group": "yes" if len(sup) < cfg["group"]["min_support_flag"] else "",
            "evidence_found": sum(profiles[s]["evidence_found"] for s in sup),
            "evidence_total": sum(profiles[s]["evidence_total"] for s in sup),
            "check_fires_on_support": c.get("fires_on_support", ""), "check_fires_elsewhere": c.get("fires_elsewhere", ""),
            "covered_by": c.get("covered_by", ""),
            "confidence": a["confidence"], "issues": " | ".join(a["issues"]), "model": m["model"],
            "model_version": m["model_version"], "prompt_sha256": m["prompt_sha256"], "run_date": m["run_date"],
            "reviewer": "", "decision": "", "review_note": ""})
    # each general motif, followed by the specific motifs built on it
    rows.sort(key=lambda r: (r["parent"] or r["motif_key"], r["level"] != "general", r["required_context"], r["motif_key"]))
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


def apply(cfg: Config, review: Path, vocab: Vocab | None = None) -> dict:
    """Accepted rows -> staging/accepted_motif*.csv (IRIs minted from the stable motif_key)."""
    from llm_mitigation.apply import read_sheet
    vocab = vocab or Vocab()
    base, ns = vocab.base, vocab.ns
    risks = {r["nexus_id"]: r for r in read_csv(cfg.path("risks"))}
    out_dir = Path(cfg.path("output_dir"))
    motifs = {m["motif_key"]: m for m in read_jsonl(out_dir / "motifs.jsonl")}
    profiles = {p["incident_id"]: p for p in read_jsonl(out_dir / "profiles.jsonl")}
    errors, acc = [], []
    rows = read_sheet(Path(review))
    for i, r in enumerate(rows, start=2):
        d = (r.get("decision") or "").strip().lower()
        if d not in VALID:
            errors.append(f"row {i}: decision {r.get('decision')!r} is not accept/reject/empty")
        elif d == "accept":
            if not (r.get("reviewer") or "").strip():
                errors.append(f"row {i}: accepted without a reviewer")
            elif r["motif_key"] not in motifs:
                errors.append(f"row {i}: unknown motif_key {r['motif_key']!r}")
            elif motifs[r["motif_key"]]["answer"]["risk_id"] not in risks:
                errors.append(f"row {i}: risk {motifs[r['motif_key']]['answer']['risk_id']!r} not in staging/risks.csv")
            else:
                acc.append((r, motifs[r["motif_key"]]))
    if errors:
        raise SystemExit("apply: review sheet has errors, nothing written:\n  " + "\n  ".join(errors))
    t = {k: [] for k in ("motifs", "elements", "flows", "contexts", "new_contexts", "sources")}
    new_ctx = {}
    for r, m in sorted(acc, key=lambda x: x[1]["motif_key"]):
        a, key = m["answer"], m["motif_key"]
        motif_iri, arch = f"{base}motif/{key}", f"{base}motif/{key}/architecture"
        el = lambda eid: f"{base}motif/{key}/{eid}"
        t["motifs"].append({"motif_iri": motif_iri, "identifier": key, "name": a["name"], "description": a["description"],
                            "risk_iri": risks[a["risk_id"]]["iri"], "manifest_iri": el(a["manifest_condition"]),
                            "architecture_iri": arch, "architecture_name": f"{a['name']}: architecture",
                            "architecture_description": "Elements and flows of the motif: " + structure_text(a),
                            "model": m["model"], "model_version": m["model_version"], "prompt_sha256": m["prompt_sha256"],
                            "run_date": m["run_date"], "reviewer": r["reviewer"].strip()})
        for e in a["elements"]:
            t["elements"].append({"architecture_iri": arch, "element_iri": el(e["id"]), "class_iri": ns + e["class"]})
        for f in a["flows"]:
            t["flows"].append({"subject_iri": el(f["from"]), "predicate_iri": ns + f["relation"], "object_iri": el(f["to"])})
        for c in a["contexts"]:
            iri = vocab.context_iri(c)
            t["contexts"].append({"motif_iri": motif_iri, "context_iri": iri})
            if c["existing"] == "new":
                new_ctx[iri] = {"context_iri": iri, "class_iri": ns + c["class"], "name": c["value"],
                                "description": f"{c['class']} value proposed by llm-motif (motif {key}); reviewed with the motif."}
        for s in a["support"]:
            if s in profiles and profiles[s].get("url"):
                t["sources"].append({"motif_iri": motif_iri, "source_url": profiles[s]["url"]})
    t["new_contexts"] = sorted(new_ctx.values(), key=lambda x: x["context_iri"])
    adir = Path(cfg.path("accepted_dir"))
    for name, cols in (("motifs", MOTIF_COLS), ("elements", ELEMENT_COLS), ("flows", FLOW_COLS),
                       ("contexts", CONTEXT_COLS), ("new_contexts", NEW_CONTEXT_COLS), ("sources", SOURCE_COLS)):
        rows_out = sorted(t[name], key=lambda x: tuple(x[c] for c in cols))
        write_csv(adir / f"accepted_motif_{name}.csv" if name != "motifs" else adir / "accepted_motifs.csv", cols, rows_out)
    return {"rows": len(rows), "accepted": len(acc),
            "rejected": sum(1 for r in rows if (r.get("decision") or "").strip().lower() == "reject"),
            "undecided": sum(1 for r in rows if not (r.get("decision") or "").strip()),
            "elements": len(t["elements"]), "flows": len(t["flows"]), "new_context_values": len(t["new_contexts"])}

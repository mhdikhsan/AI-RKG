from __future__ import annotations
from pathlib import Path
from .config import Config, load_inputs, read_csv, write_csv
from .shortlist import group_names

REVIEW_COLS = ["risk_id", "risk_name", "mitigation_id", "mitigation_name", "mitigation_category",
               "confidence", "rationale", "model", "model_version", "prompt_sha256", "run_date",
               "reviewer", "decision"]
CONF_ORDER = {"high": 0, "medium": 1, "low": 2}


def export(cfg: Config, xlsx: bool = False, force: bool = False) -> Path:
    out = Path(cfg.path("output_dir"))
    sheet = out / ("review_sheet.xlsx" if xlsx else "review_sheet.csv")
    if sheet.exists() and not force and not xlsx:
        existing = read_csv(sheet)
        if any(r.get("decision") or r.get("reviewer") for r in existing):
            raise SystemExit(f"{sheet} already contains review decisions; use --force to overwrite")
    cands = read_csv(out / "candidates.csv")
    risks, controls, groups = load_inputs(cfg)
    rname = {r["nexus_id"]: r["name"] for r in risks}
    rows = []
    for c in cands:
        ctl = controls.get(c["mitigation_id"], {})
        rows.append({**c, "risk_name": rname.get(c["risk_id"], ""), "mitigation_name": ctl.get("name", ""),
                     "mitigation_category": group_names(ctl, groups) if ctl else "", "reviewer": "", "decision": ""})
    rows.sort(key=lambda r: (r["risk_id"], CONF_ORDER.get(r["confidence"], 9), r["mitigation_id"]))
    if xlsx:
        from openpyxl import Workbook
        from openpyxl.worksheet.datavalidation import DataValidation
        wb = Workbook()
        ws = wb.active
        ws.title = "review"
        ws.append(REVIEW_COLS)
        for r in rows:
            ws.append([r.get(k, "") for k in REVIEW_COLS])
        dv = DataValidation(type="list", formula1='"accept,reject"', allow_blank=True)
        ws.add_data_validation(dv)
        col = chr(ord("A") + REVIEW_COLS.index("decision"))
        dv.add(f"{col}2:{col}{len(rows) + 1}")
        ws.freeze_panes = "A2"
        sheet.parent.mkdir(parents=True, exist_ok=True)
        wb.save(sheet)
    else:
        write_csv(sheet, REVIEW_COLS, rows)
    return sheet

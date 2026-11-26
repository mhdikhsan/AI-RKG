from __future__ import annotations
from pathlib import Path
from .config import Config, read_csv, write_csv

ACCEPTED_COLS = ["risk_id", "risk_iri", "mitigation_id", "mitigation_iri", "confidence", "model",
                 "model_version", "prompt_sha256", "run_date", "reviewer"]
VALID = {"accept", "reject", ""}


def read_sheet(path: Path) -> list[dict]:
    if path.suffix.lower() == ".xlsx":
        from openpyxl import load_workbook
        ws = load_workbook(path, read_only=True).active
        it = ws.iter_rows(values_only=True)
        header = [str(h) for h in next(it)]
        return [{h: ("" if v is None else str(v)) for h, v in zip(header, row)} for row in it]
    return read_csv(path)


def apply(cfg: Config, review: Path) -> dict:
    rows = read_sheet(Path(review))
    risks = {r["nexus_id"]: r for r in read_csv(cfg.path("risks"))}
    controls = {c["nexus_id"]: c for c in read_csv(cfg.path("controls"))}
    errors, accepted, seen = [], [], set()
    for i, r in enumerate(rows, start=2):
        d = (r.get("decision") or "").strip().lower()
        if d not in VALID:
            errors.append(f"row {i}: decision {r.get('decision')!r} is not accept/reject/empty")
            continue
        if d != "accept":
            continue
        if not (r.get("reviewer") or "").strip():
            errors.append(f"row {i}: accepted without a reviewer")
            continue
        rid, mid = r["risk_id"], r["mitigation_id"]
        if rid not in risks or mid not in controls:
            errors.append(f"row {i}: unknown risk {rid!r} or mitigation {mid!r}")
            continue
        if (rid, mid) in seen:
            continue
        seen.add((rid, mid))
        accepted.append({"risk_id": rid, "risk_iri": risks[rid]["iri"], "mitigation_id": mid,
                         "mitigation_iri": controls[mid]["iri"], "confidence": r.get("confidence", ""),
                         "model": r.get("model", ""), "model_version": r.get("model_version", ""),
                         "prompt_sha256": r.get("prompt_sha256", ""), "run_date": r.get("run_date", ""),
                         "reviewer": r["reviewer"].strip()})
    if errors:
        raise SystemExit("apply: review sheet has errors, nothing written:\n  " + "\n  ".join(errors))
    accepted.sort(key=lambda r: (r["risk_id"], r["mitigation_id"]))
    write_csv(cfg.path("accepted_out"), ACCEPTED_COLS, accepted)
    return {"rows": len(rows), "accepted": len(accepted),
            "rejected": sum(1 for r in rows if (r.get("decision") or "").strip().lower() == "reject"),
            "undecided": sum(1 for r in rows if not (r.get("decision") or "").strip())}

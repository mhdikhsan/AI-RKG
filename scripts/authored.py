"""Authored knowledge: compare authored example risks in the core module with imported risks.

Writes build/reports/authored_vs_imported_risks.md. Nothing is merged or rewritten.
"""
from __future__ import annotations

from rdflib import RDF, Graph, Namespace

from scripts.common import REPORTS, ROOT, STAGING, load_config, log, provenance_line, read_csv, write_text


def main() -> None:
    cfg = load_config()
    if not (STAGING / "risks.csv").exists():
        log("authored: staging/risks.csv missing - run stage first; skipped")
        return
    AK = Namespace(cfg["ak_namespace"])
    core = Graph().parse(ROOT / cfg["ontology"]["core"])
    risks = read_csv(STAGING / "risks.csv")
    by_code = {r["catalogue_identifier"]: r for r in risks}
    by_id = {r["nexus_id"]: r for r in risks}
    xw = read_csv(STAGING / "crosswalks.csv")

    rows = []
    for s in sorted(core.subjects(RDF.type, AK.Risk)):
        ident = str(core.value(s, AK.identifier) or "")
        name = str(core.value(s, AK.name) or "")
        src = str(core.value(s, AK.source) or "")
        match, how = None, "no match"
        if ident in by_id:
            match, how = by_id[ident], "identifier = Nexus id"
        elif ident in by_code:
            match, how = by_code[ident], "identifier = catalogue code"
        related = []
        if match:
            for x in xw:
                if x["predicate"] in ("exactMatch", "closeMatch") and match["nexus_id"] in (x["subject_nexus_id"], x["object_nexus_id"]):
                    other = x["object_nexus_id"] if x["subject_nexus_id"] == match["nexus_id"] else x["subject_nexus_id"]
                    related.append(f"skos:{x['predicate']} `{other}`")
        n_patterns = len(set(core.subjects(AK.indicatesRisk, s)))
        n_mitpat = len(set(core.subjects(AK.addressesRisk, s)))
        n_mits = len(set(core.subjects(AK.mitigates, s)))
        n_cons = len(set(core.objects(s, AK.hasConsequence)))
        rows.append((s, ident, name, src, match, how, related, n_patterns, n_mitpat, n_mits, n_cons))

    L = ["# Authored example risks vs. imported catalogue risks", "", provenance_line(), "",
         "Authored risks are the `ak:Risk` individuals in `ontology/airkg-core.ttl`; imported risks are in "
         "`build/imported_risks_*.nt`. Nothing is merged or rewritten.", "",
         "| Authored risk | `ak:identifier` | Name | `ak:source` | Matching imported risk | Matched by | Other exact/close matches of the imported risk | Used by (risk patterns / mitigation patterns / mitigations / consequences) |",
         "|---|---|---|---|---|---|---|---|"]
    for s, ident, name, src, m, how, rel, p, mp, mi, c in rows:
        mtxt = f"`{m['iri'].replace(cfg['base_iri'], '')}` ({m['name']})" if m else "**no match**"
        L.append(f"| `ak:{s.split('#')[-1]}` | {ident or '—'} | {name} | {src} | {mtxt} | {how} | "
                 f"{', '.join(rel) or '—'} | {p} / {mp} / {mi} / {c} |")
    matched = sum(1 for r in rows if r[4])
    L += ["", f"{matched} of {len(rows)} authored risks have an imported counterpart.", "",
          "## Observations", "",
          "- Authored OWASP risks cite `https://genai.owasp.org/llm-top-10/` as `ak:source`; the imported ones cite the per-entry page.",
          "- Authored risks carry the hand-written structure (consequences, risk patterns, mitigation patterns, mitigations); "
          "imported risks carry catalogue metadata and crosswalks. The two sets are not linked in RDF.",
          "- Options (not applied): (a) keep both and link authored → imported with `skos:exactMatch`; "
          "(b) re-point the authored patterns/consequences/mitigations to the imported IRIs and drop the authored risks "
          "(requires editing the core module); (c) keep as is (two separate example sets)."]
    write_text(REPORTS / "authored_vs_imported_risks.md", "\n".join(L) + "\n")
    log(f"  authored risks: {len(rows)}, matched to imported: {matched}")


if __name__ == "__main__":
    main()

"""Statistics report: build/reports/stats.md (every count carries source date + Nexus commit)."""
from __future__ import annotations

import json
from collections import Counter

from rdflib import OWL, RDF, RDFS, Graph, Namespace, URIRef
from rdflib.namespace import SKOS

from scripts.common import BUILD, REPORTS, ROOT, STAGING, load_config, log, provenance_line, read_csv, write_text

LLM_OUT = ROOT / "extractor" / "llm_mitigation" / "output"
MATCH = [SKOS.exactMatch, SKOS.closeMatch, SKOS.relatedMatch, SKOS.broadMatch, SKOS.narrowMatch]


def table(header: list[str], rows: list[list]) -> list[str]:
    return ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] + \
           ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]


def main() -> None:
    cfg = load_config()
    kg = BUILD / "airkg-core-kg.ttl"
    if not kg.exists():
        log("report: build/airkg-core-kg.ttl missing - run merge first; skipped")
        return
    base, ak = cfg["base_iri"], cfg["ak_namespace"]
    AK = Namespace(ak)
    g = Graph().parse(kg)
    L =["# AI-RKG core knowledge graph – statistics", "", provenance_line(),
         f"Merged graph: `build/airkg-core-kg.ttl`, {len(g)} triples.", ""]

    # per class (asserted types; authored vs pipeline by IRI namespace), for every class the ontology declares
    onto = Graph().parse(ROOT / cfg["ontology"]["core"])
    classes = sorted(str(c)[len(ak):] for c in onto.subjects(RDF.type, OWL.Class)
                     if isinstance(c, URIRef) and str(c).startswith(ak))
    rows = []
    for c in classes:
        inst = {s for s in g.subjects(RDF.type, AK[c]) if isinstance(s, (URIRef,))}
        blank = sum(1 for s in g.subjects(RDF.type, AK[c]) if not isinstance(s, URIRef))
        a = sum(1 for s in inst if str(s).startswith(ak))
        rows.append([f"`ak:{c}`", a, len(inst) - a, blank, len(inst) + blank])
    L += ["## Individuals per class (asserted `rdf:type`)", "",
          "Authored = in `ak:` (ontology file); pipeline = minted from `base_iri` (imported); "
          "blank = blank nodes (e.g. architectural contexts written inline).", ""]
    L += table(["Class", "Authored", "Pipeline", "Blank", "Total"], rows) + [""]

    # per catalogue
    risks = read_csv(STAGING / "risks.csv")
    by_cat = Counter(r["catalogue"] for r in risks)
    with_desc = Counter(r["catalogue"] for r in risks if r["description"])
    cats = {c["catalogue"]: c for c in read_csv(STAGING / "catalogues.csv")}
    excl = Counter(r["catalogue"] for r in read_csv(STAGING / "excluded_risks.csv"))
    L += ["## Imported risks per catalogue", ""]
    L += table(["Catalogue", "Risks", "With description", "Excluded", "Licence"],
               [[cats[c]["title"], by_cat[c], with_desc[c], excl.get(c, 0), cats[c]["license_name"]]
                for c in sorted(by_cat)] + [["**Total**", sum(by_cat.values()), sum(with_desc.values()),
                                              sum(excl.values()), ""]]) + [""]

    # crosswalks
    xw = read_csv(STAGING / "crosswalks.csv")
    summ = json.loads((STAGING / "stage_summary.json").read_text(encoding="utf-8"))
    L += ["## Crosswalks between imported risks", ""]
    L += table(["Predicate", "Links"], [[f"`skos:{p}`", n] for p, n in sorted(Counter(r["predicate"] for r in xw).items())]
               + [["**Total**", len(xw)]]) + [""]
    L += table(["Nexus mapping file", "Rows", "Kept", "Dropped (reason: count)"],
               [[f, s.get("raw", 0), s.get("kept", 0),
                 ", ".join(f"{k}: {v}" for k, v in s.items() if k not in ("raw", "kept")) or "—"]
                for f, s in summ["crosswalks_per_file"].items()]) + [""]

    # mitigations + candidate links
    ctl = read_csv(STAGING / "mit_controls.csv")
    L += ["## Mitigations", ""]
    L += table(["Type rule result (MIT top category)", "Controls"],
               [[f"`ak:{k}`", v] for k, v in sorted(Counter(c["mitigation_class"] for c in ctl).items())]
               + [["**Total MIT controls**", len(ctl)]]) + [""]
    proposed = read_csv(LLM_OUT / "candidates.csv") if (LLM_OUT / "candidates.csv").exists() else []
    accepted = read_csv(STAGING / "accepted_mitigation_links.csv") if (STAGING / "accepted_mitigation_links.csv").exists() else []
    manual = read_csv(STAGING / "manual_mitigation_links.csv") if (STAGING / "manual_mitigation_links.csv").exists() else []
    mitigates = list(g.triples((None, AK.mitigates, None)))
    L += ["Mitigation→risk links (`ak:mitigates`):", "",
          f"- curated and reviewed by the authors: {len(manual)} "
          f"({', '.join(f'{k}: {v}' for k, v in sorted(Counter(r['via'] for r in manual).items())) or 'none'}), "
          f"covering {len({r['risk_id'] for r in manual})} risks and {len({r['mitigation_id'] for r in manual})} controls",
          f"- proposed by the LLM (`extractor/llm_mitigation/`): {len(proposed)}" + (" (LLM run not done yet)" if not proposed else
                                                                            f" for {len({r['risk_id'] for r in proposed})} risks"),
          f"- LLM proposals accepted by review: {len(accepted)}",
          f"- `ak:mitigates` triples in the graph: {len(mitigates)} "
          f"({sum(1 for s, _, _ in mitigates if str(s).startswith(ak))} authored in the ontology file, "
          f"{sum(1 for s, _, _ in mitigates if str(s).startswith(base))} on imported controls)", ""]

    # risk motifs
    motifs = sorted(set(g.subjects(RDF.type, AK.RiskMotif)), key=str)
    det = REPORTS / "motif_detections.csv"
    L += ["## Risk motifs", "", f"- `ak:RiskMotif` individuals: {len(motifs)}",
          f"- risks indicated by a motif: {len(set(g.objects(None, AK.indicatesRisk)))}",
          f"- detections in the last validation run: {len(read_csv(det)) if det.exists() else 'not run yet'} "
          "(`build/reports/motif_detections.csv`)", ""]

    # validation summary pointer
    val = REPORTS / "validation.md"
    if val.exists():
        status = next((l for l in val.read_text(encoding="utf-8").splitlines() if l.startswith("**PASS") or l.startswith("**FAIL")), "")
        L += ["## Validation", "", f"{status} (details: `build/reports/validation.md`).", ""]
    write_text(REPORTS / "stats.md", "\n".join(L))
    log("  wrote build/reports/stats.md")


if __name__ == "__main__":
    main()

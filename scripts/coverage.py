from __future__ import annotations
from collections import Counter, defaultdict
from rdflib import RDF, Graph, Namespace, URIRef
from rdflib.namespace import SKOS

from scripts.common import BUILD, REPORTS, STAGING, load_config, log, provenance_line, read_csv, write_csv, write_text


def main() -> None:
    cfg = load_config()
    kg = BUILD / "airkg-core-kg.ttl"
    if not kg.exists():
        log("coverage: build/airkg-core-kg.ttl missing - run merge first; skipped")
        return
    ak, base = cfg["ak_namespace"], cfg["base_iri"]
    AK = Namespace(ak)
    g = Graph().parse(kg)
    short = lambda s: "ak:" + str(s)[len(ak):] if str(s).startswith(ak) else str(s)[len(base):]
    name = lambda s: str(g.value(s, AK.name) or short(s))

    catalogue = {URIRef(r["iri"]): r["catalogue"] for r in read_csv(STAGING / "risks.csv")}
    risks = sorted(set(g.subjects(RDF.type, AK.Risk)), key=lambda s: (catalogue.get(s, "authored"), str(s)))
    near = defaultdict(set)
    for p in (SKOS.exactMatch, SKOS.closeMatch):
        for s, o in g.subject_objects(p):
            if s in catalogue or o in catalogue:
                near[s].add(o)
                near[o].add(s)
    motifs_of = lambda r: set(g.subjects(AK.indicatesRisk, r))

    rows = []
    for r in risks:
        direct = motifs_of(r)
        via = set().union(*(motifs_of(n) for n in near.get(r, ()))) - direct if near.get(r) else set()
        mitig = set(g.subjects(AK.mitigates, r))
        rows.append({"risk": short(r), "name": name(r), "catalogue": catalogue.get(r, "authored"),
                     "motif_coverage": "direct" if direct else "via exact/close match" if via else "none",
                     "motifs": " ".join(sorted(short(m) for m in direct | via)),
                     "mitigations": len(mitig)})

    total = Counter(x["catalogue"] for x in rows)
    with_motif = Counter(x["catalogue"] for x in rows if x["motif_coverage"] != "none")
    with_mit = Counter(x["catalogue"] for x in rows if x["mitigations"])
    cats = [c for c in ["authored", "ibm", "mit", "owasp"] if total[c]] + sorted(set(total) - {"authored", "ibm", "mit", "owasp"})
    L = ["# Risk coverage: risk motifs and mitigations", "", provenance_line(), "",
         "Nothing here is asserted in the graph. *Motif* = at least one `ak:RiskMotif` indicates the risk, or a risk "
         "linked to it by `skos:exactMatch`/`skos:closeMatch`. *Mitigation* = at least one `ak:mitigates` link. "
         "Machine-readable: `build/reports/coverage.csv`.", "",
         "## Summary per catalogue", "", "| Catalogue | Risks | With a risk motif | With a mitigation |", "|---|---|---|---|"]
    L += [f"| {c} | {total[c]} | {with_motif[c]} | {with_mit[c]} |" for c in cats]
    L += [f"| **all** | {sum(total.values())} | {sum(with_motif.values())} | {sum(with_mit.values())} |", "",
          "## Risks with a motif or a mitigation", "",
          "| Risk | Catalogue | Motif coverage | Motifs | Mitigations |", "|---|---|---|---|---|"]
    L += [f"| {x['name']} (`{x['risk']}`) | {x['catalogue']} | {x['motif_coverage']} | {x['motifs'] or '—'} | {x['mitigations']} |"
          for x in rows if x["motif_coverage"] != "none" or x["mitigations"]]
    L += ["", f"Risks with neither: {sum(1 for x in rows if x['motif_coverage'] == 'none' and not x['mitigations'])} "
          "(listed in `coverage.csv`)."]
    write_text(REPORTS / "coverage.md", "\n".join(L) + "\n")
    write_csv(REPORTS / "coverage.csv", ["risk", "name", "catalogue", "motif_coverage", "motifs", "mitigations"], rows)
    log(f"  coverage: {sum(with_motif.values())} of {len(rows)} risks have a motif, {sum(with_mit.values())} a mitigation")


if __name__ == "__main__":
    main()

"""Statistics report: build/reports/stats.md (every count carries source date + Nexus commit)."""
from __future__ import annotations

import json
from collections import Counter

from rdflib import OWL, RDF, RDFS, Graph, Namespace, URIRef
from rdflib.namespace import SKOS

from scripts.common import BUILD, REPORTS, ROOT, STAGING, load_config, log, provenance_line, read_csv, write_text

LLM_OUT = ROOT / "llm_mitigation" / "output"
MATCH = [SKOS.exactMatch, SKOS.closeMatch, SKOS.relatedMatch, SKOS.broadMatch, SKOS.narrowMatch]


def role_grounded(g: Graph, s, AK, internal: tuple[str, ...]) -> bool:
    if (s, AK.source, None) in g:
        return True
    return any(isinstance(o, URIRef) and not str(o).startswith(internal)
               for p in [RDFS.seeAlso, *MATCH] for o in g.objects(s, p))


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
    internal = (ak, base)
    L = ["# AI-RKG core knowledge graph – statistics", "", provenance_line(),
         f"Merged graph: `build/airkg-core-kg.ttl`, {len(g)} triples.", ""]

    # per class (asserted types; authored vs imported/reused by IRI namespace)
    classes = ["Risk", "Consequence", "Mitigation", "TechnicalMitigation", "OrganisationalMitigation", "Role",
               "ComponentRole", "StakeholderRole", "Motif", "Condition", "RiskPattern", "MitigationPattern",
               "ContextElement", "AutonomyLevel", "DataType", "DeploymentEnvironment", "Domain", "Purpose", "Task"]
    rows = []
    for c in classes:
        inst = set(g.subjects(RDF.type, AK[c]))
        a = sum(1 for s in inst if str(s).startswith(ak))
        rows.append([f"`ak:{c}`", a, len(inst) - a, len(inst)])
    L += ["## Individuals per class (asserted `rdf:type`)", "",
          "Authored = in `ak:` (core module); pipeline = minted from `base_iri` (imported or reused).", ""]
    L += table(["Class", "Authored", "Pipeline", "Total"], rows) + [""]

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
    mitigates = list(g.triples((None, AK.mitigates, None)))
    L += ["Candidate mitigation→risk links (LLM, `llm_mitigation/`):", "",
          f"- proposed: {len(proposed)}" + (" (LLM run not done yet)" if not proposed else
                                             f" for {len({r['risk_id'] for r in proposed})} risks"),
          f"- accepted by review: {len(accepted)}",
          f"- `ak:mitigates` triples in the graph: {len(mitigates)} "
          f"({sum(1 for s, _, _ in mitigates if str(s).startswith(ak))} authored, "
          f"{sum(1 for s, _, _ in mitigates if str(s).startswith(base))} from accepted candidates)", ""]

    # roles grounded vs proposed
    rows = []
    for cls in ("ComponentRole", "StakeholderRole"):
        for origin, prefix in (("authored", ak), ("reused", base)):
            inst = [s for s in set(g.subjects(RDF.type, AK[cls])) if str(s).startswith(prefix)]
            gr = sum(1 for s in inst if role_grounded(g, s, AK, internal))
            rows.append([f"`ak:{cls}`", origin, len(inst), gr, len(inst) - gr])
    L += ["## Roles: grounded vs. proposed", "",
          "Grounded = has `ak:source`, or `rdfs:seeAlso` / `skos:*Match` to an external IRI. Proposed = neither.", ""]
    L += table(["Class", "Origin", "Roles", "Grounded", "Proposed"], rows) + [""]
    L += ["Reused roles: BEAM (`role/beam/*`, via `rdfs:seeAlso` to BEAM classes); ISO/IEC 22989 "
          "(`role/iso22989/*`, names from a secondary source, see `LICENSES.md`).", ""]

    # validation summary pointer
    val = REPORTS / "validation.md"
    if val.exists():
        status = next((l for l in val.read_text(encoding="utf-8").splitlines() if l.startswith("**PASS") or l.startswith("**FAIL")), "")
        L += ["## Validation", "", f"{status} (details: `build/reports/validation.md`).", ""]
    write_text(REPORTS / "stats.md", "\n".join(L))
    log("  wrote build/reports/stats.md")


if __name__ == "__main__":
    main()

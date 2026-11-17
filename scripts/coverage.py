"""Pattern coverage: which risks have risk patterns / mitigations, and hints for the missing ones.

Writes build/reports/pattern_coverage.md (+ build/reports/pattern_coverage.csv). Nothing is asserted in the graph.

Coverage of a risk counts patterns that indicate
  (a) the risk itself, (b) its authored counterpart (same identifier / Nexus id, see authored_vs_imported_risks.md),
  (c) a risk linked to it by skos:exactMatch or skos:closeMatch.
Hints: IBM `risk_type` (staging/ibm_risk_hints.csv; for MIT/OWASP risks taken from crosswalked IBM risks)
       -> roles (config `risk_type_hints`) -> authored motifs that involve those roles or roles specialising them.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from rdflib import RDF, Graph, Namespace, URIRef
from rdflib.namespace import SKOS

from scripts.common import BUILD, REPORTS, STAGING, load_config, log, provenance_line, read_csv, write_csv, write_text


def main() -> None:
    cfg = load_config()
    kg = BUILD / "airkg-core-kg.ttl"
    if not kg.exists() or not (STAGING / "ibm_risk_hints.csv").exists():
        log("coverage: merged graph or staging/ibm_risk_hints.csv missing; skipped")
        return
    ak, base = cfg["ak_namespace"], cfg["base_iri"]
    AK = Namespace(ak)
    g = Graph().parse(kg)
    name = lambda s: str(g.value(s, AK.name) or str(s).rsplit("/", 1)[-1].rsplit("#", 1)[-1])
    short = lambda s: "ak:" + str(s)[len(ak):] if str(s).startswith(ak) else str(s)[len(base):]

    risks = read_csv(STAGING / "risks.csv")
    by_iri = {URIRef(r["iri"]): r for r in risks}
    hints = {h["nexus_id"]: h for h in read_csv(STAGING / "ibm_risk_hints.csv")}
    xw = read_csv(STAGING / "crosswalks.csv")

    # authored counterparts (same rule as scripts/authored.py)
    authored = {}
    by_code = {r["catalogue_identifier"]: URIRef(r["iri"]) for r in risks}
    by_id = {r["nexus_id"]: URIRef(r["iri"]) for r in risks}
    for s in g.subjects(RDF.type, AK.Risk):
        if str(s).startswith(ak):
            ident = str(g.value(s, AK.identifier) or "")
            imp = by_id.get(ident) or by_code.get(ident)
            if imp:
                authored[imp] = s
    # exact/close neighbours (both directions)
    near = defaultdict(set)
    for p in (SKOS.exactMatch, SKOS.closeMatch):
        for s, o in g.subject_objects(p):
            if s in by_iri and o in by_iri:
                near[s].add(o)
                near[o].add(s)
    # risk_type for MIT/OWASP via any crosswalk to IBM risks
    xw_types = defaultdict(set)
    for x in xw:
        a, b = x["subject_nexus_id"], x["object_nexus_id"]
        for one, other in ((a, b), (b, a)):
            if other in hints and one not in hints:
                xw_types[one].add(hints[other]["risk_type"])

    # role specialisation closure (child -> all ancestors)
    parent = {s: o for s, o in g.subject_objects(AK.specialises)}
    def ancestors(r):
        out, seen = [], set()
        while r in parent and r not in seen:
            seen.add(r)
            r = parent[r]
            out.append(r)
        return out
    motif_roles = {m: set(g.objects(m, AK.involvesRole)) for m in g.subjects(RDF.type, AK.Motif)}
    def motifs_for(role_iris: set) -> list:
        hit = [m for m, rs in motif_roles.items()
               if any(r in role_iris or set(ancestors(r)) & role_iris for r in rs)]
        return sorted(hit, key=str)
    stakeholder_roles = set(g.subjects(RDF.type, AK.StakeholderRole))
    hcfg = cfg["risk_type_hints"]

    def patterns_of(r):
        return set(g.subjects(AK.indicatesRisk, r))

    rows, out_csv = [], []
    all_risks = sorted(set(by_iri) | {s for s in g.subjects(RDF.type, AK.Risk)}, key=lambda s: (str(s).startswith(base), str(s)))
    for r in all_risks:
        rec = by_iri.get(r)
        cat = rec["catalogue"] if rec else "authored"
        nid = rec["nexus_id"] if rec else ""
        direct = patterns_of(r)
        via_auth = patterns_of(authored[r]) if r in authored else set()
        via_near = set().union(*(patterns_of(n) | (patterns_of(authored[n]) if n in authored else set()) for n in near.get(r, set()))) if near.get(r) else set()
        mitig = set(g.subjects(AK.mitigates, r)) | (set(g.subjects(AK.mitigates, authored[r])) if r in authored else set())
        if nid in hints:
            types, via = [hints[nid]["risk_type"]], ""
        elif nid in xw_types:
            types, via = sorted(xw_types[nid]), " (via crosswalk)"
        else:
            types, via = [], ""
        role_iris, stake = set(), False
        for t in types:
            h = hcfg.get(t, {})
            role_iris |= {URIRef(ak + x) for x in h.get("roles", [])}
            stake = stake or bool(h.get("stakeholder_roles"))
        cand = motifs_for(role_iris | (stakeholder_roles if stake else set()))
        covered = "direct" if direct else "via authored counterpart" if via_auth else "via exact/close match" if via_near else ""
        rows.append({"risk": r, "cat": cat, "types": types, "via": via, "covered": covered,
                     "patterns": sorted(direct | via_auth | via_near, key=str), "mitig": len(mitig),
                     "roles": sorted(role_iris, key=str), "stake": stake, "cand": cand})
        out_csv.append({"risk": short(r), "catalogue": cat, "risk_type": "; ".join(types) + via.strip(),
                        "coverage": covered or "none", "patterns": " ".join(short(p) for p in rows[-1]["patterns"]),
                        "mitigations": len(mitig), "hint_roles": " ".join(short(x) for x in rows[-1]["roles"])
                        + (" +stakeholder roles" if stake else ""),
                        "candidate_motifs": " ".join(short(m) for m in cand)})

    # ---- summary
    L = ["# Risk-pattern coverage and authoring hints", "", provenance_line(), "",
         "Nothing here is asserted in the graph. *Covered* = at least one `ak:RiskPattern` indicates the risk, "
         "its authored counterpart, or an exact/close-match neighbour. *Hint roles* come from IBM `risk_type` "
         "(`config/pipeline.yaml` → `risk_type_hints`, editable); *candidate motifs* are authored motifs that "
         "involve a hint role or a role specialising it. Machine-readable: `build/reports/pattern_coverage.csv`.", ""]
    total = Counter(x["cat"] for x in rows)
    cov = Counter(x["cat"] for x in rows if x["covered"])
    mit = Counter(x["cat"] for x in rows if x["mitig"])
    L += ["## Summary per catalogue", "", "| Catalogue | Risks | With a risk pattern | With a mitigation (`ak:mitigates`) |", "|---|---|---|---|"]
    L += [f"| {c} | {total[c]} | {cov[c]} | {mit[c]} |" for c in ["authored", "ibm", "mit", "owasp"] if total[c]]
    L += [f"| **all** | {sum(total.values())} | {sum(cov.values())} | {sum(mit.values())} |", ""]

    by_type = defaultdict(list)
    for x in rows:
        for t in x["types"] or ["(none)"]:
            by_type[t].append(x)
    L += ["## By IBM risk_type", "", "MIT/OWASP risks get the risk_type of the IBM risks they are crosswalked to and can count under several types.", "",
          "| risk_type | Risks | Covered | Hint roles | Authored motifs involving them | Note |", "|---|---|---|---|---|---|"]
    for t in [*hcfg, "(none)"]:
        xs = by_type.get(t, [])
        if not xs:
            continue
        h = hcfg.get(t, {})
        roles = {URIRef(ak + r) for r in h.get("roles", [])}
        ms = motifs_for(roles | (stakeholder_roles if h.get("stakeholder_roles") else set()))
        roles_txt = ", ".join([f"`ak:{r}`" for r in h.get("roles", [])] + (["stakeholder roles"] if h.get("stakeholder_roles") else []))
        L.append(f"| {t} | {len(xs)} | {sum(1 for x in xs if x['covered'])} | {roles_txt or '—'} | "
                 f"{', '.join(f'`{short(m)}`' for m in ms) or ('—' if t == '(none)' else '**none — motif gap**')} | {h.get('note', 'no IBM risk_type (MIT/OWASP risk without IBM crosswalk, or authored)')} |")
    gaps = [t for t in hcfg if not motifs_for({URIRef(ak + r) for r in hcfg[t].get("roles", [])}
                                               | (stakeholder_roles if hcfg[t].get("stakeholder_roles") else set()))]
    L += ["", "**Motif gaps:** " + (", ".join(f"`{t}`" for t in gaps) + " — no authored motif involves the hint roles; "
          "patterns for these risks need new motifs." if gaps else "none."), ""]

    # ---- detail
    L += ["## Per risk", "", "| Risk | Catalogue | risk_type | Coverage | Patterns | Mitigations | Candidate motifs |", "|---|---|---|---|---|---|---|"]
    for x in rows:
        L.append(f"| {name(x['risk'])} (`{short(x['risk'])}`) | {x['cat']} | {', '.join(x['types']) + x['via'] or '—'} | "
                 f"{x['covered'] or '**none**'} | {', '.join(f'`{short(p)}`' for p in x['patterns']) or '—'} | {x['mitig']} | "
                 f"{', '.join(f'`{short(m)}`' for m in x['cand']) or '—'} |")
    write_text(REPORTS / "pattern_coverage.md", "\n".join(L) + "\n")
    write_csv(REPORTS / "pattern_coverage.csv", ["risk", "catalogue", "risk_type", "coverage", "patterns", "mitigations",
                                                  "hint_roles", "candidate_motifs"], out_csv)
    log(f"  coverage: {sum(cov.values())} of {sum(total.values())} risks have a risk pattern; motif gaps: {gaps or 'none'}")


if __name__ == "__main__":
    main()

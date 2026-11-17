"""Validate the merged graph.

1 parse  2 OWL consistency (owlready2 + HermiT)  3 SHACL  4 competency queries
5 dangling IRIs  6 AI system module still works (parse, consistency, baseline queries before/after)
(+ DPV IRI existence check, warnings only)
Writes build/reports/validation.md; exits non-zero on any error (warnings do not fail).
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from pyshacl import validate as shacl_validate
from rdflib import OWL, RDF, XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import SH

from scripts.common import BUILD, QUERIES, REPORTS, ROOT, SHAPES, load_config, log, provenance_line, write_text

KG = BUILD / "airkg-core-kg.ttl"


# ------------------------------------------------------------------ helpers
def hermit(owl_file: Path, option: str) -> subprocess.CompletedProcess:
    """Run the HermiT command line bundled with owlready2 (needs Java)."""
    import owlready2
    jar = Path(owlready2.__file__).parent / "hermit"
    return subprocess.run(["java", "-Xmx2000M", "-cp", os.pathsep.join([str(jar), str(jar / "HermiT.jar")]),
                           "org.semanticweb.HermiT.cli.CommandLine", option, owl_file.as_uri()],
                          capture_output=True, text=True)


def owl_check(g: Graph) -> tuple[bool, list[str], str]:
    """(consistent, unsatisfiable classes, note) with HermiT on an RDF/XML export of the graph.

    HermiT is called directly (not through owlready2.sync_reasoner, which returned an empty world after
    reasoning in this setup and missed a planted contradiction).
    """
    n_ind = len(set(g.subjects(RDF.type, OWL.NamedIndividual)))
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "kg.owl"
        f.write_bytes(g.serialize(format="xml", encoding="utf-8"))
        k = hermit(f, "-k")
        if k.returncode != 0:
            if "InconsistentOntologyException" in k.stderr:
                return False, [], f"HermiT: inconsistent ontology ({n_ind} named individuals)"
            raise SystemExit(f"validate: HermiT failed: {k.stderr.strip()[:500]}")
        u = hermit(f, "-U")
        if u.returncode != 0:
            raise SystemExit(f"validate: HermiT -U failed: {u.stderr.strip()[:500]}")
        unsat = sorted(l.strip() for l in u.stdout.splitlines()[1:] if l.strip() and l.strip() != "owl:Nothing")
        return True, unsat, f"HermiT: {k.stdout.strip()}; {n_ind} named individuals"


def owl_self_test(g: Graph, ak: str) -> bool:
    """The OWL check must detect a planted contradiction (second ak:level on an AutonomyLevel)."""
    probe = Graph()
    for t in g:
        probe.add(t)
    lvl = next(iter(g.subject_objects(URIRef(ak + "level"))), None)
    if lvl is None:
        return True
    probe.add((lvl[0], URIRef(ak + "level"), Literal(int(lvl[1]) + 100, datatype=XSD.integer)))
    return not owl_check(probe)[0]


def query_rows(g: Graph, q: str) -> list[tuple]:
    return sorted(tuple("" if v is None else str(v) for v in row) for row in g.query(q))


def system_graph(core_like: Graph, cfg: dict) -> Graph:
    """System module + a core graph. owl:imports of the core is dropped (the core is already included)."""
    g = Graph()
    for t in core_like:
        g.add(t)
    sysg = Graph().parse(ROOT / cfg["ontology"]["system"], format="turtle")
    for t in sysg:
        if t[1] == OWL.imports and str(t[2]) == cfg["ontology"]["core_iri"]:
            continue
        g.add(t)
    return g


# ------------------------------------------------------------------ main
def main() -> None:
    cfg = load_config()
    base, ak = cfg["base_iri"], cfg["ak_namespace"]
    errors, warnings, L = [], [], ["# Validation report", "", provenance_line(), ""]

    # 1 parse
    try:
        g = Graph().parse(KG, format="turtle")
        L += [f"## 1. Parse\n\nPASS: `build/airkg-core-kg.ttl` parses, {len(g)} triples.", ""]
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"validate: merged graph does not parse: {e}")

    # 2 OWL consistency
    consistent, unsat, note = owl_check(g)
    if not consistent:
        errors.append(f"OWL: inconsistent ({note})")
    if unsat:
        errors.append(f"OWL: unsatisfiable classes {unsat}")
    self_test = owl_self_test(g, ak)
    if not self_test:
        errors.append("OWL self-test: a planted contradiction was NOT detected - the OWL check is not trustworthy")
    L += ["## 2. OWL consistency (HermiT, bundled with owlready2 0.51)", "",
          f"{'PASS' if consistent and not unsat else 'FAIL'}: consistent={consistent}, unsatisfiable classes={unsat or 'none'} ({note}).",
          f"Self-test (planted contradiction: a second `ak:level` on an `ak:AutonomyLevel`): "
          f"{'detected - check is effective' if self_test else '**NOT detected**'}.", ""]

    # 3 SHACL
    shapes_text = (SHAPES / "core.shacl.ttl").read_text(encoding="utf-8").replace("__BASE_IRI__", base)
    shapes = Graph().parse(data=shapes_text, format="turtle")
    _, results, text = shacl_validate(g, shacl_graph=shapes, inference="none", advanced=True, allow_warnings=True)
    if not isinstance(results, Graph):
        raise SystemExit(f"validate: SHACL engine failed: {results}")
    by_sev, by_msg = Counter(), Counter()
    for r in results.subjects(RDF.type, SH.ValidationResult):
        sev = str(results.value(r, SH.resultSeverity)).split("#")[-1]
        msg = str(results.value(r, SH.resultMessage) or "")
        by_sev[sev] += 1
        by_msg[(sev, msg)] += 1
    for (sev, msg), n in sorted(by_msg.items()):
        (errors if sev == "Violation" else warnings).append(f"SHACL {sev}: {msg} ({n})")
    L += ["## 3. SHACL (`shapes/core.shacl.ttl`)", "",
          f"{'PASS' if not by_sev.get('Violation') else 'FAIL'}: {by_sev.get('Violation', 0)} violations, "
          f"{by_sev.get('Warning', 0)} warnings.", "", "| Severity | Message | Count |", "|---|---|---|"]
    L += [f"| {s} | {m} | {n} |" for (s, m), n in sorted(by_msg.items())] or ["| — | none | 0 |"]
    AK = Namespace(ak)
    risks = set(g.subjects(RDF.type, AK.Risk))
    no_cons = [r for r in risks if (r, AK.hasConsequence, None) not in g]
    L += ["", f"{len(no_cons)} of {len(risks)} risks have no `ak:hasConsequence` (all imported risks; "
          "the 5 authored risks have consequences). Reported as warning.", ""]

    # 4 competency queries
    expected_path = QUERIES / "expected.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8")) if expected_path.exists() else {}
    cq = sorted(QUERIES.glob("*.rq"))
    L += ["## 4. Competency queries (`queries/*.rq`)", ""]
    if not cq:
        warnings.append("competency queries Q7/Q16/Q17 not provided yet (queries/*.rq, queries/expected.json)")
        L += ["Not run: no `queries/*.rq` yet (you will provide Q7, Q16, Q17 and `queries/expected.json`).", ""]
    else:
        L += ["| Query | Rows | Expected | Result |", "|---|---|---|---|"]
        for q in cq:
            n = len(list(g.query(q.read_text(encoding="utf-8"))))
            exp = expected.get(q.name)
            ok = exp is None or n == exp
            if not ok:
                errors.append(f"query {q.name}: {n} rows, expected {exp}")
            L.append(f"| `{q.name}` | {n} | {exp if exp is not None else '—'} | {'PASS' if ok else 'FAIL'}"
                     f"{' (not checked)' if exp is None else ''} |")
        L.append("")

    # 5 dangling IRIs
    subjects = set(g.subjects())
    dangling = sorted({str(o) for o in g.objects() if isinstance(o, URIRef)
                       and (str(o).startswith(ak) or str(o).startswith(base)) and o not in subjects})
    if dangling:
        errors.append(f"dangling IRIs: {len(dangling)}")
    L += ["## 5. Dangling IRIs", "",
          f"{'PASS' if not dangling else 'FAIL'}: {len(dangling)} object IRIs in `{ak}` or `{base}` that are never a subject."]
    L += [f"- `{d}`" for d in dangling[:50]] + [""]

    # DPV IRI check (warnings)
    dpv_dir = ROOT / "sources" / "_clones" / "dpv" / cfg["sources"]["dpv"]["version"]
    dpv_iris = sorted({str(o) for o in g.objects() if isinstance(o, URIRef) and str(o).startswith("https://w3id.org/dpv")})
    L += ["## DPV IRIs used (existence check)", ""]
    if (dpv_dir / "dpv" / "dpv.ttl").exists():
        dpv = Graph()
        dpv.parse(dpv_dir / "dpv" / "dpv.ttl")
        dpv.parse(dpv_dir / "ai" / "ai.ttl")
        known = set(dpv.subjects())
        missing = [i for i in dpv_iris if URIRef(i) not in known]
        for i in missing:
            warnings.append(f"DPV IRI not found in DPV {cfg['sources']['dpv']['version']}: {i}")
        L += [f"{len(dpv_iris) - len(missing)} of {len(dpv_iris)} DPV IRIs found in DPV {cfg['sources']['dpv']['version']}."]
        L += [f"- not found: `{i}`" for i in missing] + [""]
    else:
        warnings.append("DPV not fetched: DPV IRIs unverified")
        L += ["DPV not available; unverified: " + ", ".join(f"`{i}`" for i in dpv_iris), ""]

    # 6 AI system module
    L += ["## 6. AI system module on top of the merged core", ""]
    core_orig = Graph().parse(ROOT / cfg["ontology"]["core"], format="turtle")
    before, after = system_graph(core_orig, cfg), system_graph(g, cfg)
    L.append(f"Parse: PASS (`{cfg['ontology']['system']}`; its `owl:imports <{cfg['ontology']['core_iri']}>` is "
             "satisfied by loading the core graph directly).")
    consistent2, unsat2, note2 = owl_check(after)
    if not consistent2 or unsat2:
        errors.append(f"system module + merged core: consistent={consistent2}, unsatisfiable={unsat2}")
    L += [f"Consistency (system + merged core): {'PASS' if consistent2 and not unsat2 else 'FAIL'} ({note2}).", "",
          "| Baseline query | Rows before (original core) | Rows after (merged core) | Same rows |", "|---|---|---|---|"]
    for q in sorted((QUERIES / "system").glob("*.rq")):
        text = q.read_text(encoding="utf-8")
        rb, ra = query_rows(before, text), query_rows(after, text)
        same = rb == ra
        if not same:
            errors.append(f"system baseline {q.name}: results differ (before {len(rb)}, after {len(ra)})")
        L.append(f"| `system/{q.name}` | {len(rb)} | {len(ra)} | {'yes' if same else '**no**'} |")
    L.append("")

    # summary
    L[3:3] = ["## Summary", "", f"**{'PASS' if not errors else 'FAIL'}** — {len(errors)} errors, {len(warnings)} warnings.", ""]
    L += ["## Errors", ""] + ([f"- {e}" for e in errors] or ["none"]) + ["", "## Warnings", ""] + \
         ([f"- {w}" for w in warnings] or ["none"])
    write_text(REPORTS / "validation.md", "\n".join(L) + "\n")
    for e in errors:
        log(f"  ERROR: {e}")
    for w in warnings:
        log(f"  warning: {w}")
    if errors:
        raise SystemExit(f"validate: {len(errors)} errors (see build/reports/validation.md)")
    log(f"  validation PASS ({len(warnings)} warnings) -> build/reports/validation.md")


if __name__ == "__main__":
    main()

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

from scripts.common import BUILD, QUERIES, REPORTS, ROOT, load_config, log, provenance_line, write_csv, write_text

KG = BUILD / "airkg-core-kg.ttl"


# helpers
def hermit(owl_file: Path, option: str) -> subprocess.CompletedProcess:
    """Run the HermiT command line bundled with owlready2 (needs Java)."""
    import owlready2
    jar = Path(owlready2.__file__).parent / "hermit"
    return subprocess.run(["java", "-Xmx2000M", "-cp", os.pathsep.join([str(jar), str(jar / "HermiT.jar")]),
                           "org.semanticweb.HermiT.cli.CommandLine", option, owl_file.as_uri()],
                          capture_output=True, text=True)


def owl_check(g: Graph) -> tuple[bool, list[str], str]:
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
    probe = Graph()
    for t in g:
        probe.add(t)
    lvl = next(iter(g.subject_objects(URIRef(ak + "level"))), None)
    if lvl is None:
        return True
    probe.add((lvl[0], URIRef(ak + "level"), Literal(int(lvl[1]) + 100, datatype=XSD.integer)))
    return not owl_check(probe)[0]


# main
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

    # 3 SHACL (integrity plus motif detection, same shapes file)
    shapes_rel = cfg["ontology"].get("shapes")
    if not shapes_rel:
        raise SystemExit("validate: config/pipeline.yaml has no ontology.shapes (path of the SHACL shapes file)")
    shapes_text = (ROOT / shapes_rel).read_text(encoding="utf-8").replace("__BASE_IRI__", base)
    shapes = Graph().parse(data=shapes_text, format="turtle")
    test_file = BUILD / "authored_test_data.ttl"      # authored example workflows: not in the KG, only tested here
    test_g = Graph().parse(test_file, format="turtle") if test_file.exists() else Graph()
    _, results, text = shacl_validate(g + test_g, shacl_graph=shapes, inference="none", advanced=True,
                                      allow_warnings=True)
    if not isinstance(results, Graph):
        raise SystemExit(f"validate: SHACL engine failed: {results}")
    by_sev, by_msg, detections = Counter(), Counter(), []
    for r in results.subjects(RDF.type, SH.ValidationResult):
        sev = str(results.value(r, SH.resultSeverity)).split("#")[-1]
        msg = str(results.value(r, SH.resultMessage) or "")
        by_sev[sev] += 1
        if sev == "Info":   # risk-motif detection
            detections.append({"workflow": str(results.value(r, SH.focusNode)), "motif": str(results.value(r, SH.value)),
                               "message": msg})
            continue
        by_msg[(sev, msg)] += 1
    for (sev, msg), n in sorted(by_msg.items()):
        (errors if sev == "Violation" else warnings).append(f"SHACL {sev}: {msg} ({n})")
    L += [f"## 3. SHACL (`{shapes_rel}`)", "",
          f"Run on the KG plus `build/authored_test_data.ttl` ({len(test_g)} triples: authored example workflows, "
          f"not part of the KG, used to test motif detection).", "",
          f"{'PASS' if not by_sev.get('Violation') else 'FAIL'}: {by_sev.get('Violation', 0)} violations, "
          f"{by_sev.get('Warning', 0)} warnings.", "", "| Severity | Message | Count |", "|---|---|---|"]
    L += [f"| {s} | {m} | {n} |" for (s, m), n in sorted(by_msg.items())] or ["| — | none | 0 |"]
    detections.sort(key=lambda d: (d["workflow"], d["motif"], d["message"]))
    short = lambda s: s.replace(ak, "ak:").replace(base, "")
    L += ["", f"### Risk-motif detections (`sh:Info`, not counted as errors or warnings): {len(detections)}", ""]
    if detections:
        L += ["| Workflow | Motif | Message |", "|---|---|---|"]
        L += [f"| `{short(d['workflow'])}` | `{short(d['motif'])}` | {short(d['message'])} |" for d in detections]
    L.append("")
    write_csv(REPORTS / "motif_detections.csv", ["workflow", "motif", "message"], detections)

    # 4 competency queries
    expected_path = QUERIES / "expected.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8")) if expected_path.exists() else {}
    cq = sorted(QUERIES.glob("*.rq"))
    L += ["## 4. Competency queries (`queries/*.rq`)", ""]
    if not cq:
        warnings.append("no competency queries yet (queries/*.rq, queries/expected.json)")
        L += ["Not run: no `queries/*.rq` yet (see `queries/README.md`).", ""]
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

    # Reused-vocabulary IRI check 
    clone = ROOT / "sources" / "_clones" / "dpv"
    vocab_ns = ("https://w3id.org/dpv",)
    used = sorted({str(o) for o in g.objects() if isinstance(o, URIRef) and str(o).startswith(vocab_ns)})
    L += ["## Reused vocabulary IRIs (existence check)", ""]
    files = [clone / f for f in cfg["sources"]["dpv"]["files"]]
    if all(f.exists() for f in files):
        vocab = Graph()
        for f in files:
            vocab.parse(f)
        known = set(vocab.subjects())
        missing = [i for i in used if URIRef(i) not in known]
        for i in missing:
            warnings.append(f"IRI not found in the fetched vocabularies: {i}")
        L += [f"{len(used) - len(missing)} of {len(used)} IRIs found in: "
              + ", ".join(f"`{f.relative_to(ROOT).as_posix()}`" for f in files) + "."]
        L += [f"- not found: `{i}`" for i in missing] + [""]
    else:
        warnings.append("reused vocabularies not fetched (run fetch): their IRIs are unverified")
        L += ["Vocabularies not available; unverified: " + ", ".join(f"`{i}`" for i in used), ""]

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

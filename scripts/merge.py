from __future__ import annotations

from rdflib import OWL, RDF, RDFS, Graph, Namespace, URIRef
from rdflib.compare import to_canonical_graph
from rdflib.namespace import DCTERMS, SKOS

from scripts.common import BUILD, ROOT, load_config, log, ontology_files, write_text
from scripts.map import to_nt

PARTS = [ 
    ("declarations.ttl", True),
    ("imported_risks_ibm.nt", True), ("imported_risks_mit.nt", True), ("imported_risks_owasp.nt", True),
    ("imported_crosswalks.nt", True), ("imported_mitigations.nt", True),
    ("manual_mitigation_links.nt", False), ("accepted_mitigation_links.nt", False),
    ("accepted_motifs.nt", False),
]


def declarations() -> Graph:
    g = Graph()
    for p in (SKOS.relatedMatch, SKOS.broadMatch, SKOS.narrowMatch, DCTERMS.license, DCTERMS.source):
        g.add((p, RDF.type, OWL.AnnotationProperty))
    return g


def bind_prefixes(g: Graph, cfg: dict) -> None:
    base = cfg["base_iri"]
    for prefix, ns in [("ak", cfg["ak_namespace"]), ("risk", base + "risk/"), ("mitigation", base + "mitigation/"),
                       ("nexus", "https://w3id.org/ai-atlas-nexus/"), ("skos", str(SKOS)), ("dct", str(DCTERMS)),
                       ("owl", str(OWL)), ("beam", "http://w3id.org/beam/core#"), ("dpv", "https://w3id.org/dpv#"),
                       ("airo", "https://w3id.org/airo#")]:
        g.bind(prefix, Namespace(ns), override=True, replace=True)


AUTHORED_KEEP = ["context_values", "mitigation_links", "risk_motifs"]


def split_authored(onto: Graph, cfg: dict) -> tuple[Graph, Graph, dict]:
    ak = cfg["ak_namespace"]
    AK = Namespace(ak)
    opts = cfg.get("authored_instances") or {}
    keep_opts, test_opts = set(opts.get("keep", AUTHORED_KEEP)), set(opts.get("test_data", []))
    inst = {s for s, o in onto.subject_objects(RDF.type) if str(o).startswith(ak) and (s, RDF.type, OWL.Class) not in onto}
    typed = lambda s, cls: any(AK[cls] in set(onto.transitive_objects(t, RDFS.subClassOf)) for t in onto.objects(s, RDF.type))

    def closure(seeds: set, props: list) -> set:
        out, todo = set(), list(seeds)
        while todo:
            s = todo.pop()
            if s in out or s not in inst:
                continue
            out.add(s)
            todo += [o for p in props for o in onto.objects(s, p)]
        return out

    keep = set()
    if "context_values" in keep_opts:
        keep |= {s for s in inst if typed(s, "ApplicationContext")}
    if "mitigation_links" in keep_opts:
        for m, r in onto.subject_objects(AK.mitigates):
            keep |= {x for x in (m, r) if x in inst}
    if "risk_motifs" in keep_opts:
        keep |= closure({s for s in inst if typed(s, "RiskMotif")},
                        [AK.inContext, AK.indicatesRisk, AK.hasManifestCondition, AK.hasElement])
    test = set()
    if "workflows" in test_opts:
        test = closure({s for s in inst if typed(s, "AIWorkflow")},
                       [AK.isWorkflowOf, AK.hasWorkflow, AK.hasArchitecturalContext, AK.hasElement]) - keep
    drop = inst - keep
    kg, test_g = Graph(), Graph()
    for t in onto:
        if t[0] in drop or t[2] in drop:
            if t[0] in test:
                test_g.add(t)
            continue
        kg.add(t)
    return kg, test_g, {"authored_instances": len(inst), "kept": len(keep), "test_only": len(test),
                        "dropped": len(drop) - len(test)}


def build_merged(cfg: dict, include_accepted: bool = True) -> Graph:
    onto = Graph()
    for f in ontology_files(cfg):          # airkg.ttl + contexts.ttl
        onto.parse(f, format="turtle")
    g, _, _ = split_authored(onto, cfg)
    for name, required in PARTS:
        if name == "accepted_mitigation_links.nt" and not include_accepted:
            continue
        p = BUILD / name
        if not p.exists():
            if required:
                raise SystemExit(f"merge: {p.relative_to(ROOT)} missing - run the earlier steps first")
            continue
        g.parse(p, format="turtle" if name.endswith(".ttl") else "nt")
    return g


def main() -> None:
    cfg = load_config()
    write_text(BUILD / "declarations.ttl", declarations().serialize(format="turtle"))
    onto = Graph()
    for f in ontology_files(cfg):
        onto.parse(f, format="turtle")
    _, test_g, counts = split_authored(onto, cfg)
    bind_prefixes(test_g, cfg)
    write_text(BUILD / "authored_test_data.ttl", test_g.serialize(format="turtle"))
    log(f"  authored instances in the ontology files: {counts} (test-only -> build/authored_test_data.ttl)")
    g = build_merged(cfg)
    canon = Graph()
    for t in to_canonical_graph(g):
        canon.add(t)
    bind_prefixes(canon, cfg)
    write_text(BUILD / "airkg-core-kg.ttl", canon.serialize(format="turtle"))
    write_text(BUILD / "airkg-core-kg.nt", to_nt(canon))
    log(f"  merged graph: {len(canon)} triples -> build/airkg-core-kg.ttl (+ .nt)")


if __name__ == "__main__":
    main()

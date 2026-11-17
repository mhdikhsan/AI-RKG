"""Merge: schema + authored (core module, unchanged) + imported + reused + accepted candidates.

Outputs
  build/declarations.ttl  pipeline-owned OWL declarations for properties the core does not declare
  build/airkg-core-kg.ttl merged graph, canonical blank nodes -> byte-identical on rerun
  build/airkg-core-kg.nt  same graph as sorted N-Triples (for OWL tools)
"""
from __future__ import annotations

from rdflib import OWL, RDF, Graph, Namespace, URIRef
from rdflib.compare import to_canonical_graph
from rdflib.namespace import DCTERMS, SKOS

from scripts.common import BUILD, ROOT, load_config, log, write_text
from scripts.map import to_nt

PARTS = [  # (file in build/, required)
    ("declarations.ttl", True),
    ("imported_risks_ibm.nt", True), ("imported_risks_mit.nt", True), ("imported_risks_owasp.nt", True),
    ("imported_crosswalks.nt", True), ("imported_mitigations.nt", True),
    ("reused_roles_beam.nt", True), ("reused_roles_iso22989.nt", False), ("role_grounding.nt", False),
    ("accepted_mitigation_links.nt", False),
]


def declarations() -> Graph:
    """Annotation properties used by the pipeline but not declared in the core."""
    g = Graph()
    for p in (SKOS.relatedMatch, SKOS.broadMatch, SKOS.narrowMatch, DCTERMS.license, DCTERMS.source):
        g.add((p, RDF.type, OWL.AnnotationProperty))
    return g


def bind_prefixes(g: Graph, cfg: dict) -> None:
    base = cfg["base_iri"]
    for prefix, ns in [("ak", cfg["ak_namespace"]), ("risk", base + "risk/"), ("mitigation", base + "mitigation/"),
                       ("beamrole", base + "role/beam/"), ("isorole", base + "role/iso22989/"),
                       ("nexus", "https://w3id.org/ai-atlas-nexus/"), ("skos", str(SKOS)), ("dct", str(DCTERMS)),
                       ("owl", str(OWL)), ("beam", "http://w3id.org/beam/core#"), ("dpv", "https://w3id.org/dpv#"),
                       ("airo", "https://w3id.org/airo#")]:
        g.bind(prefix, Namespace(ns), override=True, replace=True)


def build_merged(cfg: dict, include_accepted: bool = True) -> Graph:
    g = Graph()
    g.parse(ROOT / cfg["ontology"]["core"], format="turtle")
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

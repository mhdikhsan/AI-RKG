"""Read the AI-RKG ontology (the file named in config/pipeline.yaml) and render it for prompts.

AgentO pastes the full ontology into its prompt. We render the TBox as compact, deterministic text
instead: the response cache is keyed on the exact prompt, so the rendering must not change between
runs unless the ontology itself changes.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from rdflib import OWL, RDF, RDFS, BNode, Graph, URIRef
from rdflib.collection import Collection

REPO_ROOT = Path(__file__).resolve().parents[3]       # <repo>/extractor/llm_mitigation/llm_mitigation/ontology.py
PIPELINE_CONFIG = REPO_ROOT / "config" / "pipeline.yaml"


def pipeline_config(path: Path | None = None) -> dict:
    with open(path or PIPELINE_CONFIG, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class Ontology:
    def __init__(self, path: Path | None = None, pcfg: dict | None = None):
        pcfg = pcfg or pipeline_config()
        self.ns = pcfg["ak_namespace"]
        self.path = Path(path) if path else REPO_ROOT / pcfg["ontology"]["core"]
        self.g = Graph().parse(self.path)
        if path is None and pcfg["ontology"].get("contexts"):    # extra Domain/Task/... values
            self.g.parse(REPO_ROOT / pcfg["ontology"]["contexts"])

    # ---------------------------------------------------------------- names
    def local(self, node) -> str:
        if isinstance(node, URIRef):
            s = str(node)
            if s.startswith(self.ns):
                return s[len(self.ns):]
            for prefix, ns in (("owl", str(OWL)), ("rdfs", str(RDFS)), ("xsd", "http://www.w3.org/2001/XMLSchema#")):
                if s.startswith(ns):
                    return f"{prefix}:{s[len(ns):]}"
            return s
        if isinstance(node, BNode):
            union = self.g.value(node, OWL.unionOf)
            if union is not None:
                return " or ".join(sorted(self.local(m) for m in Collection(self.g, union)))
        return str(node)

    def iri(self, local: str) -> URIRef:
        return URIRef(self.ns + local)

    def classes(self) -> list[URIRef]:
        return sorted((c for c in self.g.subjects(RDF.type, OWL.Class) if isinstance(c, URIRef)
                       and str(c).startswith(self.ns)), key=str)

    def subclasses(self, root: str, include_root: bool = True) -> list[str]:
        """Local names of `root` and all its (transitive) subclasses, sorted."""
        top = self.iri(root)
        out, todo = set(), [top]
        while todo:
            c = todo.pop()
            if c in out:
                continue
            out.add(c)
            todo.extend(s for s in self.g.subjects(RDFS.subClassOf, c) if isinstance(s, URIRef))
        if not include_root:
            out.discard(top)
        return sorted(self.local(c) for c in out)

    def individuals(self, cls: str) -> list[tuple[str, str]]:
        """(local name, ak:name or '') of the individuals typed with `cls` or one of its subclasses."""
        name = self.iri("name")
        out = set()
        for c in self.subclasses(cls):
            for s in self.g.subjects(RDF.type, self.iri(c)):
                if isinstance(s, URIRef) and str(s).startswith(self.ns):
                    out.add((self.local(s), str(self.g.value(s, name) or "")))
        return sorted(out)

    # ---------------------------------------------------------------- rendering
    def _restrictions(self, cls: URIRef) -> list[str]:
        out = []
        for sup in self.g.objects(cls, RDFS.subClassOf):
            if not isinstance(sup, BNode) or (sup, RDF.type, OWL.Restriction) not in self.g:
                continue
            prop = self.local(self.g.value(sup, OWL.onProperty))
            on = self.g.value(sup, OWL.onClass)
            for kind, word in ((OWL.cardinality, "exactly"), (OWL.qualifiedCardinality, "exactly"),
                               (OWL.minCardinality, "min"), (OWL.minQualifiedCardinality, "min"),
                               (OWL.maxCardinality, "max"), (OWL.maxQualifiedCardinality, "max")):
                n = self.g.value(sup, kind)
                if n is not None:
                    out.append(f"{prop} {word} {n}" + (f" {self.local(on)}" if on is not None else ""))
        return sorted(out)

    def render(self, only: set[str] | None = None) -> str:
        """Classes (with parents and restrictions) and properties (with domain and range) as text lines.
        `only`: restrict to these local names (classes and properties)."""
        keep = (lambda n: n in only) if only else (lambda n: True)
        lines = ["Classes (`X < Y` means X is a subclass of Y):"]
        for c in self.classes():
            n = self.local(c)
            if not keep(n):
                continue
            parents = sorted(self.local(p) for p in self.g.objects(c, RDFS.subClassOf) if isinstance(p, URIRef))
            text = f"- {n}" + (f" < {', '.join(parents)}" if parents else "")
            r = self._restrictions(c)
            if r:
                text += f"  [{'; '.join(r)}]"
            comment = self.g.value(c, RDFS.comment)
            if comment:
                text += f"  -- {comment}"
            lines.append(text)
        lines.append("")
        lines.append("Properties (`p: Domain -> Range`):")
        for kind, label in ((OWL.ObjectProperty, "object"), (OWL.DatatypeProperty, "data")):
            for p in sorted((p for p in self.g.subjects(RDF.type, kind) if isinstance(p, URIRef)
                             and str(p).startswith(self.ns)), key=str):
                n = self.local(p)
                if not keep(n):
                    continue
                dom = self.g.value(p, RDFS.domain)
                rng = self.g.value(p, RDFS.range)
                inv = self.g.value(p, OWL.inverseOf)
                text = f"- {n} ({label}): {self.local(dom) if dom is not None else '?'} -> {self.local(rng) if rng is not None else '?'}"
                if inv is not None:
                    text += f"  (inverse of {self.local(inv)})"
                lines.append(text)
        return "\n".join(lines)

"""Static site: one HTML page + one Turtle file per entry (risk, mitigation, role, motif,
risk pattern, mitigation pattern) and an index. No server.

Paths: an IRI under base_iri  -> site/<rest of IRI>.html / .ttl   (e.g. site/risk/atlas-x.html)
       an authored ak: IRI     -> site/ak/<local name>.html / .ttl
"""
from __future__ import annotations

import os
import posixpath
import shutil

from jinja2 import Environment, FileSystemLoader, select_autoescape
from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, SKOS

from scripts.common import BUILD, ROOT, SITE, STAGING, load_config, log, provenance_line, read_csv, write_text
from scripts.merge import bind_prefixes

SECTIONS = [("risks", "Risks", ["Risk"]),
            ("mitigations", "Mitigations", ["Mitigation", "TechnicalMitigation", "OrganisationalMitigation"]),
            ("roles", "Roles", ["ComponentRole", "StakeholderRole", "Role"]),
            ("motifs", "Motifs", ["Motif"]),
            ("risk-patterns", "Risk patterns", ["RiskPattern"]),
            ("mitigation-patterns", "Mitigation patterns", ["MitigationPattern"])]


class Site:
    def __init__(self, cfg: dict, g: Graph):
        self.cfg, self.g = cfg, g
        self.base, self.ak = cfg["base_iri"], cfg["ak_namespace"]
        self.AK = Namespace(self.ak)
        bind_prefixes(g, cfg)
        self.entries: dict[URIRef, str] = {}          # IRI -> section id
        for sid, _, classes in SECTIONS:
            for c in classes:
                for s in g.subjects(RDF.type, self.AK[c]):
                    if isinstance(s, URIRef):
                        self.entries.setdefault(s, sid)
        cats = read_csv(STAGING / "catalogues.csv")
        self.attribution = {c["license"]: c["attribution"] for c in cats}
        self.attribution.setdefault(cfg["mit_mitigations"]["license"],
                                    "MIT AI Risk Repository mitigation database, via IBM AI Atlas Nexus (CC BY 4.0).")
        self.candidates = {(r["mitigation_iri"], r["risk_iri"]) for r in read_csv(STAGING / "accepted_mitigation_links.csv")} \
            if (STAGING / "accepted_mitigation_links.csv").exists() else set()

    # ------------------------------------------------------------ paths
    def rel(self, iri: URIRef) -> str:
        s = str(iri)
        if s.startswith(self.base):
            return s[len(self.base):]
        return "ak/" + s[len(self.ak):]

    def href(self, from_rel: str, target: URIRef) -> str:
        return posixpath.relpath(self.rel(target) + ".html", posixpath.dirname(from_rel) or ".")

    def qname(self, u: URIRef) -> str:
        try:
            return self.g.namespace_manager.normalizeUri(u)
        except Exception:  # noqa: BLE001
            return str(u)

    def title(self, s: URIRef) -> str:
        v = self.g.value(s, self.AK.name) or self.g.value(s, RDFS.label)
        return str(v) if v else self.qname(s)

    def value(self, from_rel: str, o) -> dict:
        if isinstance(o, Literal):
            return {"text": str(o), "href": None}
        if isinstance(o, URIRef):
            if o in self.entries:
                return {"text": self.title(o), "href": self.href(from_rel, o)}
            if str(o).startswith(("http://", "https://")) and not str(o).startswith(self.ak):
                return {"text": self.qname(o) if self.qname(o) != str(o) else str(o), "href": str(o)}
            return {"text": self.qname(o), "href": None}
        return {"text": "[blank node]", "href": None}

    def grouped(self, from_rel: str, pairs) -> list[dict]:
        by_p: dict = {}
        for p, o in pairs:
            by_p.setdefault(p, []).append(o)
        out = []
        for p in sorted(by_p, key=lambda x: self.qname(x)):
            vals = sorted((self.value(from_rel, o) for o in by_p[p]), key=lambda v: (v["text"], v["href"] or ""))
            out.append({"label": self.qname(p), "values": vals})
        return out

    # ------------------------------------------------------------ build
    def entry(self, s: URIRef) -> dict:
        g, rel = self.g, self.rel(s)
        props = [(p, o) for p, o in g.predicate_objects(s)
                 if p != self.AK.description and not (p == RDF.type and o == OWL.NamedIndividual)]
        incoming = [(p, x) for x, p in g.subject_predicates(s) if x in self.entries]
        lic = g.value(s, DCTERMS.license)
        types = sorted(self.qname(t) for t in g.objects(s, RDF.type) if t != OWL.NamedIndividual)
        cand = any((str(s), str(o)) in self.candidates for o in g.objects(s, self.AK.mitigates))
        return {"iri": str(s), "title": self.title(s), "types": types,
                "origin": "authored" if str(s).startswith(self.ak) else "imported / reused",
                "description": str(g.value(s, self.AK.description) or ""),
                "props": self.grouped(rel, props), "incoming": self.grouped(rel, incoming),
                "license": str(lic) if lic else "", "attribution": self.attribution.get(str(lic), "") if lic else "",
                "ttl_name": posixpath.basename(rel) + ".ttl",
                "candidate_note": "Some ak:mitigates links of this entry were proposed by an LLM and accepted by a human reviewer "
                                  "(staging/accepted_mitigation_links.csv)." if cand else ""}

    def turtle(self, s: URIRef) -> str:
        t = Graph()
        bind_prefixes(t, self.cfg)
        for p, o in self.g.predicate_objects(s):
            t.add((s, p, o))
        return t.serialize(format="turtle")


def main() -> None:
    cfg = load_config()
    kg = BUILD / "airkg-core-kg.ttl"
    if not kg.exists():
        log("site: build/airkg-core-kg.ttl missing - run merge first; skipped")
        return
    g = Graph().parse(kg)
    site = Site(cfg, g)
    env = Environment(loader=FileSystemLoader(ROOT / "scripts" / "templates"),
                      autoescape=select_autoescape(["html", "j2"]), keep_trailing_newline=True)
    entry_t, index_t = env.get_template("entry.html.j2"), env.get_template("index.html.j2")
    # clean generated output (keep .gitkeep)
    for child in SITE.iterdir() if SITE.exists() else []:
        if child.name == ".gitkeep":
            continue
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    prov = provenance_line()
    rows_by_section: dict[str, list] = {sid: [] for sid, _, _ in SECTIONS}
    for s in sorted(site.entries, key=str):
        rel = site.rel(s)
        root = "../" * rel.count("/")
        e = site.entry(s)
        write_text(SITE / f"{rel}.html", entry_t.render(e=e, root=root, provenance=prov))
        write_text(SITE / f"{rel}.ttl", site.turtle(s))
        ident = g.value(s, site.AK.identifier)
        rows_by_section[site.entries[s]].append(
            {"href": rel + ".html", "title": e["title"], "type": ", ".join(t.replace("ak:", "") for t in e["types"]),
             "identifier": str(ident) if ident else "", "origin": e["origin"]})
    sections = [{"id": sid, "title": title, "rows": sorted(rows_by_section[sid], key=lambda r: (r["title"].lower(), r["href"]))}
                for sid, title, _ in SECTIONS]
    write_text(SITE / "index.html", index_t.render(sections=sections, total=len(site.entries), triples=len(g),
                                                    base=cfg["base_iri"], root="", provenance=prov))
    log(f"  site: {len(site.entries)} entries -> {len(site.entries) * 2 + 1} files in site/")


if __name__ == "__main__":
    main()

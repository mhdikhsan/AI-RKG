from __future__ import annotations
from pathlib import Path
from pyshacl import validate
from rdflib import OWL, RDF, RDFS, Graph, Literal, Namespace, URIRef
from rdflib.namespace import SH
from llm_mitigation.config import Config, read_csv, write_csv
from llm_mitigation.ontology import REPO_ROOT
from . import accepted as accepted_mod
from .core import Vocab
from .stages import read_jsonl

CHECK_COLS = ["motif_id", "risk_id", "number_of_incidents", "matches_own_incidents", "own_incidents_not_matched",
              "matches_other_incidents", "all_matched_incidents", "broader_motif_same_risk"]
EXTENSION_COLS = ["motif_id", "incident_id", "incident_title", "incident_url"]
TEMPLATE = "motif-template-"           
SCHEMA_TYPES = {OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty, OWL.Ontology,
                OWL.Restriction, RDFS.Datatype}


def tbox(vocab: Vocab) -> Graph:
    g = vocab.onto.g
    inst = {s for s, o in g.subject_objects(RDF.type) if o not in SCHEMA_TYPES}
    out = Graph()
    for t in g:
        if t[0] not in inst:
            out.add(t)
    return out


def add_structure(g: Graph, answer: dict, prefix: str, ns: str, arch: URIRef) -> None:
    for e in answer["elements"]:
        g.add((arch, URIRef(ns + "hasElement"), URIRef(prefix + e["id"])))
        g.add((URIRef(prefix + e["id"]), RDF.type, URIRef(ns + e["class"])))
    for f in answer["flows"]:
        g.add((URIRef(prefix + f["from"]), URIRef(ns + f["relation"]), URIRef(prefix + f["to"])))


def build_graph(vocab: Vocab, profiles: list[dict], motifs: list[dict], risks: dict) -> Graph:
    ns, base = vocab.ns, vocab.base + "check/"
    AK = Namespace(ns)
    g = tbox(vocab)
    for p in profiles:
        iid = p["incident_id"]
        wf, arch, system = URIRef(f"{base}workflow/{iid}"), URIRef(f"{base}workflow/{iid}/architecture"), URIRef(f"{base}system/{iid}")
        g.add((wf, RDF.type, AK.AIWorkflow))
        g.add((wf, AK.isWorkflowOf, system))
        g.add((system, RDF.type, AK.AISystem))
        g.add((wf, AK.hasArchitecturalContext, arch))
        g.add((arch, RDF.type, AK.ArchitecturalContext))
        add_structure(g, p["answer"], f"{base}workflow/{iid}/", ns, arch)
        for c in p["answer"]["contexts"]:
            g.add((wf, AK.hasApplicationContext, URIRef(vocab.context_iri(c))))
            g.add((URIRef(vocab.context_iri(c)), RDF.type, URIRef(ns + c["class"])))
    for m in motifs:
        a, key = m["answer"], m["motif_key"]
        motif, arch = URIRef(f"{base}motif/{key}"), URIRef(f"{base}motif/{key}/architecture")
        g.add((motif, RDF.type, AK.RiskMotif))
        g.add((motif, AK.identifier, Literal(key)))
        g.add((motif, AK.indicatesRisk, URIRef(a.get("risk_iri") or (risks[a["risk_id"]]["iri"] if a["risk_id"] in risks
                                                                     else vocab.base + "risk/" + a["risk_id"]))))
        g.add((motif, AK.inContext, arch))
        g.add((arch, RDF.type, AK.ArchitecturalContext))
        g.add((motif, AK.hasManifestCondition, URIRef(f"{base}motif/{key}/{a['manifest_condition']}")))
        add_structure(g, a, f"{base}motif/{key}/", ns, arch)
        for c in a["contexts"]:
            ci = URIRef(c.get("iri") or vocab.context_iri(c))
            g.add((motif, AK.inContext, ci))
            g.add((ci, RDF.type, URIRef(ns + c["class"])))
    return g


def run_check(cfg: Config, vocab: Vocab | None = None) -> dict:
    vocab = vocab or Vocab()
    out_dir = Path(cfg.path("output_dir"))
    profiles, motifs = read_jsonl(out_dir / "profiles.jsonl"), read_jsonl(out_dir / "motifs.jsonl")
    by_url = {p["url"]: p["incident_id"] for p in profiles if p.get("url")}
    acc = accepted_mod.load(cfg, vocab, by_url)
    acc_keys = {m["motif_key"] for m in acc}
    proposals = [m for m in motifs if m["motif_key"] not in acc_keys]   
    if not profiles or not (motifs or acc):
        raise SystemExit("check: needs output/profiles.jsonl and output/motifs.jsonl (run the profile and abstract stages)")
    risks = {r["nexus_id"]: r for r in read_csv(cfg.path("risks"))}
    templates = [{"incident_id": TEMPLATE + m["motif_key"], "answer": m["answer"]} for m in proposals]
    g = build_graph(vocab, profiles + templates, proposals + acc, risks)
    shapes = Graph().parse(REPO_ROOT / vocab.pcfg["ontology"]["shapes"])
    _, results, _ = validate(g, shacl_graph=shapes, inference="none", advanced=True, allow_warnings=True)
    if not isinstance(results, Graph):
        raise SystemExit(f"check: SHACL engine failed: {results}")
    detect = URIRef(vocab.ns + "MotifDetectionShape")
    wf_prefix, motif_prefix = vocab.base + "check/workflow/", vocab.base + "check/motif/"
    fired = {}
    for r in results.subjects(RDF.type, SH.ValidationResult):
        if results.value(r, SH.sourceShape) != detect:
            continue
        wf, mo = str(results.value(r, SH.focusNode)), str(results.value(r, SH.value))
        if wf.startswith(wf_prefix) and mo.startswith(motif_prefix):
            fired.setdefault(mo[len(motif_prefix):], set()).add(wf[len(wf_prefix):])
    on_templates = {k: {w[len(TEMPLATE):] for w in v if w.startswith(TEMPLATE)} for k, v in fired.items()}
    fired = {k: {w for w in v if not w.startswith(TEMPLATE)} for k, v in fired.items()}
    covered = covered_by(proposals + acc, on_templates)
    mark = lambda k: f"{k}(accepted)" if k in acc_keys else k
    profile_ids = {p["incident_id"] for p in profiles}
    rows = []
    for m in proposals:
        sup = set(m["answer"]["support"]) & profile_ids
        f = fired.get(m["motif_key"], set())
        rows.append({"motif_id": m["motif_key"], "risk_id": m["answer"]["risk_id"], "number_of_incidents": len(sup),
                     "matches_own_incidents": f"{len(f & sup)} of {len(sup)}",
                     "own_incidents_not_matched": " ".join(sorted(sup - f)),
                     "matches_other_incidents": len(f - sup), "all_matched_incidents": " ".join(sorted(f)),
                     "broader_motif_same_risk": " ".join(mark(k) for k in covered.get(m["motif_key"], []))})
    write_csv(out_dir / "check.csv", CHECK_COLS, rows)
    pmap = {p["incident_id"]: p for p in profiles}
    ext = [{"motif_id": m["motif_key"], "incident_id": i, "incident_title": pmap[i]["title"],
            "incident_url": pmap[i].get("url", "")}
           for m in acc for i in sorted(fired.get(m["motif_key"], set()) - set(m["answer"]["support"]))
           if pmap[i].get("url", "") not in m["excluded"]]
    write_csv(out_dir / "extensions.csv", EXTENSION_COLS, ext)
    full = sum(1 for r in rows if not r["own_incidents_not_matched"])
    return {"motifs": len(rows), "fire_on_all_their_support": full, "profiles": len(profiles),
            "detections": sum(len(v) for v in fired.values()), "covered_by_another": len(covered),
            "accepted_motifs": len(acc), "proposals_already_accepted": len(motifs) - len(proposals),
            "extension_candidates": len(ext)}


def covered_by(motifs: list[dict], on_templates: dict[str, set[str]]) -> dict[str, list[str]]:
    risk = {m["motif_key"]: m["answer"]["risk_id"] for m in motifs}
    fires_on = {a: {b for b, temps in on_templates.items() if a in temps and b != a} for a in risk}
    out = {}
    for a in sorted(risk):
        cov = sorted(b for b in fires_on[a] if risk.get(b) == risk[a]
                     and not (a in fires_on.get(b, set()) and a < b))      
        if cov:
            out[a] = cov
    return out

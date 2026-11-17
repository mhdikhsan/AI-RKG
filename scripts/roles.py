"""Reused roles (ISO/IEC 22989 stakeholder roles, BEAM process roles) + alignment report.

Outputs
  staging/stakeholder_roles.csv, staging/component_roles_beam.csv
  build/reused_roles_iso22989.nt, build/reused_roles_beam.nt
  build/reports/roles_alignment.md
The core module is only read, never changed.
"""
from __future__ import annotations

import csv
import re

from rdflib import OWL, RDF, RDFS, Graph, Namespace, URIRef

from scripts.common import (BUILD, REPORTS, ROOT, STAGING, load_config, log, provenance_line,
                            write_csv, write_text)
from scripts.map import materialize, write_graph

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def stage_iso(cfg: dict, problems: list) -> list[dict]:
    path = ROOT / cfg["sources"]["iso22989"]["manual_file"]
    base, url = cfg["base_iri"], cfg["sources"]["iso22989"]["standard_url"]
    rows = []
    if path.exists():
        with open(path, encoding="utf-8-sig", newline="") as fh:
            rows = [r for r in csv.DictReader(fh) if any((v or "").strip() for v in r.values())]
    ids = {r["id"].strip() for r in rows}
    out = []
    for r in rows:
        rid, parent = r["id"].strip(), (r.get("parent_id") or "").strip()
        if not ID_RE.match(rid):
            problems.append(f"iso22989_roles.csv: id {rid!r} is not lower-case kebab-case")
        if parent and parent not in ids:
            problems.append(f"iso22989_roles.csv: parent_id {parent!r} of {rid!r} is not an id in the file")
        out.append({"id": rid, "name": r["name"].strip(), "clause": (r.get("clause") or "").strip(),
                    "parent_id": parent, "source": url, "iri": f"{base}role/iso22989/{rid}",
                    "parent_iri": f"{base}role/iso22989/{parent}" if parent else ""})
    return sorted(out, key=lambda r: r["id"])


def stage_beam(cfg: dict, beam: Graph, problems: list) -> list[dict]:
    base, ns = cfg["base_iri"], cfg["roles"]["beam_namespace"]
    out = []
    for r in cfg["roles"]["beam"]:
        iri = URIRef(ns + r["beam_class"])
        if len(beam) and (iri, None, None) not in beam:
            problems.append(f"BEAM class {iri} not found in beam_core.ttl")
        out.append({"id": r["id"], "name": r["name"], "beam_iri": str(iri), "parent_id": r["parent"],
                    "iri": f"{base}role/beam/{r['id']}",
                    "parent_iri": f"{base}role/beam/{r['parent']}" if r["parent"] else ""})
    return sorted(out, key=lambda r: r["id"])


def norm(s: str) -> str:
    s = re.sub(r"\(.*?\)", " ", s.lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def alignment_report(cfg: dict, core: Graph, beam: Graph, iso_rows: list, beam_rows: list) -> str:
    AK = Namespace(cfg["ak_namespace"])
    name = lambda s: str(core.value(s, AK.name) or s.split("#")[-1])
    authored = {}
    for cls in (AK.ComponentRole, AK.StakeholderRole):
        for s in core.subjects(RDF.type, cls):
            authored[s] = {"class": cls.split("#")[-1], "name": name(s),
                           "parent": core.value(s, AK.specialises),
                           "seeAlso": {str(o) for o in core.objects(s, RDFS.seeAlso)},
                           "grounded": bool(core.value(s, AK.source)) or any(
                               str(o).startswith("http") and not str(o).startswith(cfg["ak_namespace"])
                               for p in (RDFS.seeAlso, URIRef("http://www.w3.org/2004/02/skos/core#exactMatch"),
                                         URIRef("http://www.w3.org/2004/02/skos/core#closeMatch"))
                               for o in core.objects(s, p))}
    L = ["# Roles alignment: authored (core module) vs. reused (BEAM, ISO/IEC 22989)", "",
         provenance_line(), "",
         "The core module is not changed. Correspondences below are *proposals* for your decision.", ""]

    # ---- BEAM
    L += ["## BEAM process roles (component roles)", "",
          "| Reused role | IRI | BEAM class | Target parent | Authored counterpart (via `rdfs:seeAlso`) | Authored parent | Status |",
          "|---|---|---|---|---|---|---|"]
    by_beam = {}
    for s, a in authored.items():
        for b in a["seeAlso"]:
            by_beam.setdefault(b, []).append(s)
    beam_to_authored = {}
    for r in beam_rows:
        matches = by_beam.get(r["beam_iri"], [])
        beam_to_authored[r["id"]] = matches[0] if matches else None
    for r in beam_rows:
        m = beam_to_authored[r["id"]]
        target_parent = next((x["name"] for x in beam_rows if x["id"] == r["parent_id"]), "—")
        if not m:
            status, apar = "**missing** in authored list", "—"
        else:
            apar_iri = authored[m]["parent"]
            apar = name(apar_iri) if apar_iri else "— (core level)"
            want = beam_to_authored.get(r["parent_id"]) if r["parent_id"] else None
            if r["parent_id"] and (apar_iri is None or apar_iri != want):
                status = f"**conflict**: target specialises {target_parent}, authored {'is at core level' if not apar_iri else 'specialises ' + apar}"
            elif not r["parent_id"] and apar_iri:
                status = f"**conflict**: target is core level, authored specialises {apar}"
            else:
                status = "corresponds"
        L.append(f"| {r['name']} | `role/beam/{r['id']}` | `beam:{r['beam_iri'].split('#')[-1]}` | {target_parent} | "
                 f"{'`ak:' + m.split('#')[-1] + '` (' + authored[m]['name'] + ')' if m else '—'} | {apar} | {status} |")
    # BEAM's own hierarchy, for information
    ns = cfg["roles"]["beam_namespace"]
    L += ["", "BEAM's own class hierarchy (from `beam_core.ttl`):", ""]
    for r in beam_rows:
        sup = sorted(str(o).replace(ns, "beam:") for o in beam.objects(URIRef(r["beam_iri"]), RDFS.subClassOf)
                     if isinstance(o, URIRef))
        L.append(f"- `beam:{r['beam_iri'].split('#')[-1]}` rdfs:subClassOf {', '.join(f'`{x}`' for x in sup) or '—'}")
    # Known authored conflict: Generation step
    gen = URIRef(cfg["ak_namespace"] + "GenerationStepRole")
    if gen in authored:
        g = authored[gen]
        L += ["", "### Authored `ak:GenerationStepRole`", "",
              f"- name: \"{g['name']}\"; specialises: {name(g['parent']) if g['parent'] else '—'}.",
              "- Target (prompt): \"Content generation step\" under Infer step (BEAM *Infer*, not *Generate*). "
              f"Parent {'already matches' if g['parent'] == URIRef(cfg['ak_namespace'] + 'InferStepRole') else 'differs'}; "
              f"name {'matches' if norm(g['name']) == 'content generation step' else 'differs (rename needed in the core module)'}.",
              "- Risk of confusion: the reused `role/beam/generate` (\"Generate step\", BEAM *Generate* = producing a model) is a different role."]

    # ---- ISO
    L += ["", "## ISO/IEC 22989 stakeholder roles", ""]
    authored_sh = {s: a for s, a in authored.items() if a["class"] == "StakeholderRole"}
    if not iso_rows:
        L += ["`sources/manual/iso22989_roles.csv` is empty: no ISO roles imported yet. "
              f"Authored stakeholder roles waiting for grounding: {len(authored_sh)} — "
              + ", ".join(f"`ak:{s.split('#')[-1]}` ({a['name']})" for s, a in sorted(authored_sh.items())) + "."]
    else:
        L += ["| Reused role | Clause | Parent | Authored counterpart (name match) |", "|---|---|---|---|"]
        matched = set()
        for r in iso_rows:
            m = [s for s, a in authored_sh.items() if norm(a["name"]) == norm(r["name"])]
            matched.update(m)
            L.append(f"| {r['name']} (`role/iso22989/{r['id']}`) | {r['clause']} | {r['parent_id'] or '—'} | "
                     f"{', '.join('`ak:' + s.split('#')[-1] + '`' for s in m) or '**missing** in authored list'} |")
        rest = sorted(set(authored_sh) - matched)
        L += ["", "Authored stakeholder roles with no ISO counterpart by name: "
              + (", ".join(f"`ak:{s.split('#')[-1]}` ({authored_sh[s]['name']})" for s in rest) or "none") + "."]

    # ---- grounding summary
    comp = {s: a for s, a in authored.items() if a["class"] == "ComponentRole"}
    L += ["", "## Grounding of authored roles", "",
          "A role is *grounded* if it has `ak:source` or `rdfs:seeAlso`/`skos:*Match` to an external IRI.", "",
          f"- Component roles: {sum(a['grounded'] for a in comp.values())} of {len(comp)} grounded.",
          f"- Stakeholder roles: {sum(a['grounded'] for a in authored_sh.values())} of {len(authored_sh)} grounded.",
          "", "Authored component roles not grounded (proposed, local): "
          + ", ".join(f"`ak:{s.split('#')[-1]}`" for s, a in sorted(comp.items()) if not a["grounded"]) + "."]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- role grounding
SKOS_NS = "http://www.w3.org/2004/02/skos/core#"
STOPWORDS = {"step", "role", "the", "of", "a", "an", "and", "ai", "data"}


def vocabularies(cfg: dict) -> dict[str, Graph]:
    """Local copies of external vocabularies used to verify grounding targets."""
    out = {}
    beam = ROOT / cfg["sources"]["beam"]["manual_file"]
    if beam.exists():
        out[cfg["roles"]["grounding_prefixes"]["beam"]] = Graph().parse(beam)
    dpv_dir = ROOT / "sources" / "_clones" / "dpv" / cfg["sources"]["dpv"]["version"]
    if (dpv_dir / "dpv" / "dpv.ttl").exists():
        out[cfg["roles"]["grounding_prefixes"]["dpv"]] = Graph().parse(dpv_dir / "dpv" / "dpv.ttl")
        out[cfg["roles"]["grounding_prefixes"]["ai"]] = Graph().parse(dpv_dir / "ai" / "ai.ttl")
    return out


def expand(term: str, prefixes: dict) -> str:
    term = term.strip()
    if term.startswith(("http://", "https://")):
        return term
    if ":" in term and term.split(":", 1)[0] in prefixes:
        p, local = term.split(":", 1)
        return prefixes[p] + local
    return ""


def stage_grounding(cfg: dict, core: Graph, roles_graph: Graph, vocabs: dict, problems: list, notes: list) -> list[dict]:
    rcfg = cfg["roles"]
    path = ROOT / rcfg["grounding_file"]
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if any((v or "").strip() for v in r.values())]
    AK = Namespace(cfg["ak_namespace"])
    role_classes = (AK.Role, AK.ComponentRole, AK.StakeholderRole)
    known_roles = {s for c in role_classes for g in (core, roles_graph) for s in g.subjects(RDF.type, c)}
    out, seen = [], set()
    for i, r in enumerate(rows, start=2):
        role = (r.get("role") or "").strip()
        role_iri = URIRef(role if role.startswith(("http://", "https://")) else cfg["ak_namespace"] + role)
        pred = (r.get("predicate") or "").strip()
        target = expand(r.get("target") or "", rcfg["grounding_prefixes"])
        if role_iri not in known_roles:
            problems.append(f"role_grounding.csv row {i}: {role!r} is not a role in the core module or reused roles")
            continue
        if pred not in rcfg["grounding_predicates"]:
            problems.append(f"role_grounding.csv row {i}: predicate {pred!r} not in {rcfg['grounding_predicates']}")
            continue
        if not target:
            problems.append(f"role_grounding.csv row {i}: target {r.get('target')!r} is not an IRI or known CURIE")
            continue
        ns = next((n for n in vocabs if target.startswith(n)), None)
        if ns is not None and (URIRef(target), None, None) not in vocabs[ns]:
            problems.append(f"role_grounding.csv row {i}: target {target} not found in the fetched vocabulary")
            continue
        if ns is None:
            notes.append(f"row {i}: target {target} not verified (no local copy of that vocabulary)")
        pred_iri = str(RDFS.seeAlso) if pred == "seeAlso" else SKOS_NS + pred
        key = (str(role_iri), pred_iri, target)
        if key in seen:
            continue
        seen.add(key)
        out.append({"role_iri": str(role_iri), "predicate_iri": pred_iri, "target_iri": target,
                    "note": (r.get("note") or "").strip()})
    return sorted(out, key=lambda x: (x["role_iri"], x["predicate_iri"], x["target_iri"]))


def tokens(s: str) -> set[str]:
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in STOPWORDS and len(t) > 2}


def candidates_report(cfg: dict, core: Graph, vocabs: dict, grounded: set) -> str:
    """Name-overlap suggestions for authored roles without grounding. Suggestions only."""
    AK = Namespace(cfg["ak_namespace"])
    pfx = {v: k for k, v in cfg["roles"]["grounding_prefixes"].items()}
    terms = []
    for ns, g in vocabs.items():
        for s in set(g.subjects()):
            if isinstance(s, URIRef) and str(s).startswith(ns) and len(str(s)) > len(ns):
                lab = g.value(s, URIRef(SKOS_NS + "prefLabel")) or g.value(s, RDFS.label) or str(s)[len(ns):]
                terms.append((f"{pfx[ns]}:{str(s)[len(ns):]}", str(lab), tokens(str(lab)) | tokens(str(s)[len(ns):])))
    L = ["# Role grounding: suggestions (by name overlap only — NOT applied)", "", provenance_line(), "",
         "For each authored component/stakeholder role without an external link, terms from BEAM, DPV and DPV-AI "
         "whose label shares words with the role name. Copy the ones you agree with into "
         "`sources/manual/role_grounding.csv` (see `sources/manual/README.md`). Many will be wrong: "
         "risk/bias concepts share words with data roles.", "",
         "| Role | Name | Description | Suggestions (term — label — overlap) |", "|---|---|---|---|"]
    for cls in (AK.ComponentRole, AK.StakeholderRole):
        for s in sorted(core.subjects(RDF.type, cls)):
            if s in grounded:
                continue
            name = str(core.value(s, AK.name) or "")
            rt = tokens(name) | tokens(str(s).split("#")[-1].replace("Role", ""))
            scored = []
            for curie, lab, tt in terms:
                if not tt or not rt:
                    continue
                inter = rt & tt
                if inter:
                    scored.append((len(inter) / len(rt | tt), curie, lab))
            top = sorted(scored, key=lambda x: (-x[0], x[1]))[:4]
            sug = "<br>".join(f"`{c}` — {l} — {sc:.2f}" for sc, c, l in top) or "—"
            L.append(f"| `ak:{s.split('#')[-1]}` | {name} | {core.value(s, AK.description) or ''} | {sug} |")
    return "\n".join(L) + "\n"


def main() -> None:
    cfg = load_config()
    problems: list[str] = []
    beam = Graph()
    beam_file = ROOT / cfg["sources"]["beam"]["manual_file"]
    if beam_file.exists():
        beam.parse(beam_file)
    else:
        problems.append(f"{cfg['sources']['beam']['manual_file']} missing: BEAM IRIs not verified")
    iso_rows = stage_iso(cfg, problems)
    beam_rows = stage_beam(cfg, beam, problems)
    write_csv(STAGING / "stakeholder_roles.csv", ["id", "name", "clause", "parent_id", "source", "iri", "parent_iri"], iso_rows)
    write_csv(STAGING / "component_roles_beam.csv", ["id", "name", "beam_iri", "parent_id", "iri", "parent_iri"], beam_rows)

    n_beam = write_graph("reused_roles_beam.nt", materialize("roles_beam.rml.ttl"))
    n_iso = write_graph("reused_roles_iso22989.nt", materialize("roles_iso22989.rml.ttl") if iso_rows else Graph())
    log(f"  reused_roles_beam.nt: {n_beam} triples ({len(beam_rows)} roles)")
    log(f"  reused_roles_iso22989.nt: {n_iso} triples ({len(iso_rows)} roles)")

    core = Graph().parse(ROOT / cfg["ontology"]["core"])
    write_text(REPORTS / "roles_alignment.md", alignment_report(cfg, core, beam, iso_rows, beam_rows))
    log("  wrote build/reports/roles_alignment.md")

    # hand-written grounding of roles
    reused = Graph()
    for f in ("reused_roles_beam.nt", "reused_roles_iso22989.nt"):
        if (BUILD / f).exists():
            reused.parse(BUILD / f, format="nt")
    vocabs = vocabularies(cfg)
    notes: list[str] = []
    gl = stage_grounding(cfg, core, reused, vocabs, problems, notes)
    write_csv(STAGING / "role_grounding.csv", ["role_iri", "predicate_iri", "target_iri", "note"], gl)
    n_gr = write_graph("role_grounding.nt", materialize("role_grounding.rml.ttl") if gl else Graph())
    log(f"  role_grounding.nt: {n_gr} triples ({len(gl)} rows from {cfg['roles']['grounding_file']})")
    for n in notes:
        log(f"  note: {n}")
    already = {s for s, p, o in core if p in (RDFS.seeAlso, URIRef(SKOS_NS + "exactMatch"), URIRef(SKOS_NS + "closeMatch"))
               and isinstance(o, URIRef) and not str(o).startswith(cfg["ak_namespace"])}
    already |= {URIRef(r["role_iri"]) for r in gl}
    write_text(REPORTS / "role_grounding_candidates.md", candidates_report(cfg, core, vocabs, already))
    log("  wrote build/reports/role_grounding_candidates.md")
    for p in problems:
        log(f"  WARNING: {p}")
    if any("not found" in p or "kebab" in p or "parent_id" in p or "role_grounding.csv" in p for p in problems):
        raise SystemExit("roles: input errors")


if __name__ == "__main__":
    main()

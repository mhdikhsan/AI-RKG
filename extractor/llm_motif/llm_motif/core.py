"""Configuration, ontology vocabulary, prompt blocks and the ontology checks applied to every answer.

Shared machinery (Claude provider, response cache, JSON-schema validation, TF-IDF)
"""
from __future__ import annotations

import copy
import json
import re
import unicodedata
from pathlib import Path

from rdflib import OWL, RDFS, URIRef
from rdflib.collection import Collection

from llm_mitigation.config import Config, load_config
from llm_mitigation.ontology import Ontology, pipeline_config

PKG_ROOT = Path(__file__).resolve().parent.parent          # llm_motif/ folder
DEFAULT_CONFIG = PKG_ROOT / "config.yaml"


def load_cfg(path: str | Path | None = None, overrides: dict | None = None) -> Config:
    return load_config(path or DEFAULT_CONFIG, overrides)


def stage_cfg(cfg: Config, stage: str) -> Config:
    """A copy of the config with the stage's effort as `effort` (what the provider and cache key read)."""
    c = Config(copy.deepcopy(dict(cfg)), cfg.base)
    c["effort"] = cfg["effort"][stage]
    return c


def slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-") or "x"


def norm_text(text: str) -> str:
    """Lower-case, quotes and dashes unified, whitespace collapsed: for evidence matching."""
    t = unicodedata.normalize("NFKC", text or "").lower()
    t = t.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                                   "–": "-", "—": "-"}))
    return " ".join(t.split())


class Vocab:
    """Ontology terms the LLM may use, read from the ontology file named in config/pipeline.yaml."""

    def __init__(self, onto: Ontology | None = None):
        self.pcfg = pipeline_config()
        self.onto = onto or Ontology(pcfg=self.pcfg)
        self.base = self.pcfg["base_iri"]
        self.ns = self.onto.ns
        o = self.onto
        self.element_classes = [c for c in o.subclasses("Element") if c != "Element"]
        self.context_classes = o.subclasses("ApplicationContext", include_root=False)
        self.existing = {c: o.individuals(c) for c in self.context_classes}
        # domain / range of the two element relations, closed under subclasses
        self.domain, self.range = {}, {}
        for p in ("uses", "produces"):
            self.domain[p] = self._closure(o.g.value(o.iri(p), RDFS.domain))
            self.range[p] = self._closure(o.g.value(o.iri(p), RDFS.range))

    def _closure(self, node) -> set[str]:
        if node is None:
            return set(self.element_classes)
        union = self.onto.g.value(node, OWL.unionOf)
        roots = [self.onto.local(m) for m in Collection(self.onto.g, union)] if union is not None else [self.onto.local(node)]
        out = set()
        for r in roots:
            out |= set(self.onto.subclasses(r))
        return out

    def existing_ids(self) -> list[str]:
        return sorted({i for vals in self.existing.values() for i, _ in vals})

    # ---------------------------------------------------------------- IRIs (shared by apply and check)
    def class_iri(self, local: str) -> str:
        return self.ns + local

    def context_iri(self, ctx: dict) -> str:
        if ctx.get("existing") and ctx["existing"] != "new":
            return self.ns + ctx["existing"]
        return f"{self.base}context/{slug(ctx['class'])}/{slug(ctx['value'])}"

    # ---------------------------------------------------------------- prompt blocks
    def element_classes_block(self) -> str:
        lines = []
        for c in self.element_classes:
            parents = sorted(self.onto.local(p) for p in self.onto.g.objects(self.onto.iri(c), RDFS.subClassOf)
                             if isinstance(p, URIRef))
            lines.append(f"- {c}" + (f" (a kind of {', '.join(parents)})" if parents else ""))
        return "\n".join(lines)

    def context_values_block(self) -> str:
        lines = []
        for c in self.context_classes:
            vals = self.existing[c]
            lines.append(f"- {c}: " + (", ".join(f"`{i}` ({n})" if n else f"`{i}`" for i, n in vals) if vals
                                        else "no values yet (use `new`)"))
        return "\n".join(lines)


# -------------------------------------------------------------------- schema with per-call enums
def fill_schema(base: dict, *, element_classes: list[str], context_classes: list[str], existing_ids: list[str],
                risk_ids: list[str], support_ids: list[str] | None = None, limits: dict | None = None) -> dict:
    s = copy.deepcopy(base)
    p = s["properties"]
    p["elements"]["items"]["properties"]["class"]["enum"] = list(element_classes)
    p["contexts"]["items"]["properties"]["class"]["enum"] = list(context_classes)
    p["contexts"]["items"]["properties"]["existing"]["enum"] = list(existing_ids) + ["new"]
    if "risks" in p:
        p["risks"]["items"]["properties"]["risk_id"]["enum"] = list(risk_ids) or ["none"]
    if "risk_id" in p:
        p["risk_id"]["enum"] = list(risk_ids)
    if support_ids is not None:
        p["support"]["items"]["enum"] = list(support_ids)
    for key, val in (limits or {}).items():
        if key in p and "maxItems" in p[key]:
            p[key]["maxItems"] = val
    return s


def api_schema(full: dict) -> dict:
    """Schema sent to the API: drop keywords structured outputs do not need for decoding."""
    s = copy.deepcopy(full)
    for key in ("$schema", "$id", "title"):
        s.pop(key, None)

    def strip(node):
        if isinstance(node, dict):
            for k in ("maxItems", "minItems", "maxLength", "minLength", "pattern"):
                node.pop(k, None)
            for v in node.values():
                strip(v)
        elif isinstance(node, list):
            for v in node:
                strip(v)
    strip(s)
    return s


# -------------------------------------------------------------------- ontology checks on an answer
def check_structure(data: dict, vocab: Vocab, manifest_key: str) -> list[str]:
    """Errors that the JSON schema cannot express: references between ids, and the ontology's
    domain/range for uses/produces. A non-empty result makes the answer invalid (retry, then skip)."""
    errors = []
    ids = [e["id"] for e in data["elements"]]
    if len(ids) != len(set(ids)):
        errors.append("duplicate element ids")
    cls = {e["id"]: e["class"] for e in data["elements"]}
    for f in data["flows"]:
        if f["from"] not in cls or f["to"] not in cls:
            errors.append(f"flow {f['from']} {f['relation']} {f['to']}: unknown element id")
            continue
        if cls[f["from"]] not in vocab.domain[f["relation"]]:
            errors.append(f"flow {f['from']} {f['relation']} {f['to']}: {cls[f['from']]} cannot {f['relation']} "
                          f"(only {', '.join(sorted(vocab.domain[f['relation']]))})")
        if cls[f["to"]] not in vocab.range[f["relation"]]:
            errors.append(f"flow {f['from']} {f['relation']} {f['to']}: {cls[f['to']]} cannot be {f['relation']}d "
                          f"(only {', '.join(sorted(vocab.range[f['relation']]))})")
    mc = data.get(manifest_key, "")
    if mc and mc not in cls:
        errors.append(f"{manifest_key} {mc!r} is not an element id")
    for c in data["contexts"]:
        if c["existing"] != "new":
            valid = {i for i, _ in vocab.existing.get(c["class"], [])}
            if c["existing"] not in valid:
                errors.append(f"context {c['existing']!r} is not an existing {c['class']} value")
    return errors


def evidence_report(data: dict, source_text: str) -> tuple[int, int]:
    """(elements with evidence found in the source text, elements with evidence)."""
    src = norm_text(source_text)
    with_ev = [e for e in data["elements"] if e.get("evidence", "").strip()]
    found = sum(1 for e in with_ev if norm_text(e["evidence"]).strip(" .\"'") in src)
    return found, len(with_ev)


def structure_text(data: dict) -> str:
    """Compact, readable structure for review sheets: 'm1 Infer uses m2 Data; ...'."""
    cls = {e["id"]: e["class"] for e in data["elements"]}
    flows = [f"{f['from']} {cls.get(f['from'], '?')} {f['relation']} {f['to']} {cls.get(f['to'], '?')}" for f in data["flows"]]
    loose = [f"{i} {c}" for i, c in cls.items() if not any(i in (f["from"], f["to"]) for f in data["flows"])]
    return "; ".join(flows + loose)


def dumps(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)

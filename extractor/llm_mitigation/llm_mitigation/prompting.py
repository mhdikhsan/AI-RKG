from __future__ import annotations
import copy
import json
import re
from pathlib import Path
from .config import Config, sha256_file

SECTION = re.compile(r"^## (System|User)\s*$", re.M)


def load_template(path: Path) -> tuple[str, str]:
    text = re.sub(r"<!--.*?-->", "", Path(path).read_text(encoding="utf-8"), flags=re.S)
    parts = SECTION.split(text)
    sections = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    if set(sections) != {"System", "User"}:
        raise ValueError(f"{path}: needs exactly one '## System' and one '## User' section")
    return sections["System"], sections["User"]


def prompt_sha256(cfg: Config) -> str:
    return sha256_file(cfg.path("prompt"))


def risk_block(risk: dict) -> str:
    lines = [f"- id: {risk['nexus_id']}", f"- catalogue: {risk['catalogue']}",
             f"- identifier: {risk['catalogue_identifier']}", f"- name: {risk['name']}"]
    if risk.get("description"):
        lines.append(f"- description: {risk['description']}")
    return "\n".join(lines)


def category_path(control: dict, groups: dict) -> str:
    paths = []
    for gid in control.get("group_ids", "").split():
        g = groups.get(gid)
        if g:
            parent = groups.get(g.get("broader_id", ""))
            paths.append(f"{parent['name']} > {g['name']}" if parent else g["name"])
    return "; ".join(paths) or "uncategorised"


def shortlist_block(ids: list[str], controls: dict, groups: dict) -> str:
    out = []
    for cid in ids:
        c = controls[cid]
        out.append(f"- id: {cid}\n  name: {c['name']}\n  category: {category_path(c, groups)}"
                   + (f"\n  description: {c['description']}" if c.get("description") else ""))
    return "\n".join(out)


_ONTOLOGY_CACHE: dict = {}

def ontology_block(cfg: Config) -> str:
    terms = tuple(sorted(cfg.get("ontology_terms") or []))
    if terms not in _ONTOLOGY_CACHE:
        from .ontology import Ontology
        _ONTOLOGY_CACHE[terms] = Ontology().render(set(terms) if terms else None)
    return _ONTOLOGY_CACHE[terms]


def render(cfg: Config, risk: dict, ids: list[str], controls: dict, groups: dict) -> tuple[str, str]:
    system, user = load_template(cfg.path("prompt"))
    system = system.replace("{ontology_block}", ontology_block(cfg)) if "{ontology_block}" in system else system
    user = (user.replace("{risk_block}", risk_block(risk))
                .replace("{shortlist_block}", shortlist_block(ids, controls, groups))
                .replace("{max_links}", str(cfg["answer"]["max_links_per_risk"])))
    return system, user


def validation_schema(cfg: Config, allowed_ids: list[str]) -> dict:
    s = json.loads(cfg.path("schema").read_text(encoding="utf-8"))
    s["properties"]["links"]["maxItems"] = cfg["answer"]["max_links_per_risk"]
    item = s["properties"]["links"]["items"]
    item["properties"]["rationale"]["maxLength"] = cfg["answer"]["rationale_max_chars"]
    item["properties"]["mitigation_id"]["enum"] = list(allowed_ids)
    return s


def prompt_files_sha256(paths: list[Path]) -> str:
    import hashlib
    h = hashlib.sha256()
    for p in paths:
        h.update(Path(p).name.encode() + b"\0" + Path(p).read_bytes() + b"\0")
    return h.hexdigest()


def api_schema(full: dict) -> dict:
    s = copy.deepcopy(full)
    for key in ("$schema", "$id", "title"):
        s.pop(key, None)

    def strip(node):
        if isinstance(node, dict):
            for k in ("maxItems", "minItems", "maxLength", "minLength"):
                node.pop(k, None)
            for v in node.values():
                strip(v)
        elif isinstance(node, list):
            for v in node:
                strip(v)
    strip(s)
    return s

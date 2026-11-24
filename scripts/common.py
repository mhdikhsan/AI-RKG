"""Shared helpers: paths, config, deterministic I/O."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "pipeline.yaml"

SOURCES = ROOT / "sources"
NEXUS_DIR = SOURCES / "nexus"
MANUAL = SOURCES / "manual"
MANIFEST = SOURCES / "manifest.json"
STAGING = ROOT / "staging"
MAPPINGS = ROOT / "mappings"
BUILD = ROOT / "build"
REPORTS = BUILD / "reports"
QUERIES = ROOT / "queries"
SITE = ROOT / "site"
DOCS = ROOT / "docs"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, header: list[str], rows: list[dict] | list[list]) -> int:
    """Write a CSV deterministically (LF line endings, UTF-8, rows as given)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow([r.get(k, "") for k in header] if isinstance(r, dict) else r)
    return len(rows)


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def write_json(path: Path, obj) -> None:
    write_text(path, json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {}


def provenance_line() -> str:
    """'Computed <date> from Nexus commit <sha>' - every reported count carries this."""
    m = manifest()
    nexus = m.get("nexus", {})
    return (f"Computed from sources fetched {nexus.get('fetched', 'n/a')}, "
            f"Nexus commit `{nexus.get('commit', 'n/a')}`.")


def ontology_files(cfg: dict) -> list[Path]:
    """The ontology files merged into the graph: the core file plus the optional contexts file."""
    o = cfg["ontology"]
    return [ROOT / o[k] for k in ("core", "contexts") if o.get(k)]


def check_ontology_unchanged(cfg: dict | None = None) -> None:
    """The ontology and shapes files must match the SHA-256 pinned in config/pipeline.yaml
    (the pipeline only reads them; after an intended edit, update the hash in the config)."""
    cfg = cfg or load_config()
    o = cfg["ontology"]
    for key in ("core", "contexts", "shapes"):
        if key not in o:          # contexts is optional
            continue
        actual = sha256_file(ROOT / o[key])
        if actual != o[f"{key}_sha256"]:
            sys.exit(f"ERROR: {o[key]} changed (sha256 {actual}). If the edit is intended, run:\n"
                     f"  python -m scripts.run accept-ontology")


def log(msg: str) -> None:
    print(msg, flush=True)


def accept_ontology_changes() -> list[str]:
    """After an intended edit: check that each changed ontology file is valid Turtle, then write its new SHA-256
    into config/pipeline.yaml (only the hash lines change; comments and layout are kept)."""
    import re
    from rdflib import Graph
    cfg = load_config()
    o = cfg["ontology"]
    with open(CONFIG_PATH, encoding="utf-8", newline="") as fh:     # keep the file's line endings as they are
        text = fh.read()
    changed = []
    for key in ("core", "contexts", "shapes"):
        if key not in o:
            continue
        path = ROOT / o[key]
        actual = sha256_file(path)
        if actual == o.get(f"{key}_sha256"):
            continue
        try:
            Graph().parse(path, format="turtle")
        except Exception as e:                     # syntax error: do not accept
            sys.exit(f"ERROR: {o[key]} is not valid Turtle, hash not updated:\n  {e}")
        text, n = re.subn(rf'(\n[ \t]*{key}_sha256:[ \t]*)"[0-9a-f]*"', rf'\g<1>"{actual}"', text, count=1)
        if n != 1:
            sys.exit(f"ERROR: no ontology.{key}_sha256 line found in {CONFIG_PATH.relative_to(ROOT)}")
        changed.append(f"{o[key]} -> {actual}")
    if changed:
        with open(CONFIG_PATH, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    return changed

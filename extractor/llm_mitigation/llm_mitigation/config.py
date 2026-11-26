"""Configuration and small shared helpers (paths, CSV, hashing)."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml

PKG_ROOT = Path(__file__).resolve().parent.parent      # llm_mitigation/ folder
DEFAULT_CONFIG = PKG_ROOT / "config.yaml"


class Config(dict):
    """dict with `.path(key)`: resolves entries of `paths` relative to the config file."""

    def __init__(self, data: dict, base: Path):
        super().__init__(data)
        self.base = base

    def path(self, key: str) -> Path:
        return (self.base / self["paths"][key]).resolve()


def load_config(path: str | Path | None = None, overrides: dict | None = None) -> Config:
    p = Path(path) if path else DEFAULT_CONFIG
    with open(p, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    for k, v in (overrides or {}).items():
        if v is not None:
            data[k] = v
    return Config(data, p.resolve().parent)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def stable_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, header: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=header, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def load_inputs(cfg: Config) -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    """Risks in scope (sorted by nexus_id), controls by id, groups by id."""
    cats = set(cfg["scope"]["catalogues"])
    risks = sorted((r for r in read_csv(cfg.path("risks")) if r["catalogue"] in cats), key=lambda r: r["nexus_id"])
    only = cfg["scope"].get("only_risks_from")          # optional CSV with a risk_id column (e.g. an evaluation set)
    if only:
        keep = {r["risk_id"] for r in read_csv(cfg.base / only)}
        risks = [r for r in risks if r["nexus_id"] in keep]
    controls = {c["nexus_id"]: c for c in read_csv(cfg.path("controls"))}
    groups = {g["group_id"]: g for g in read_csv(cfg.path("groups"))} if cfg.path("groups").exists() else {}
    return risks, controls, groups

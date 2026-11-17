"""Small offline fixtures: a temp config with 3 risks and 6 controls. No network."""
import csv
import shutil
from pathlib import Path

import pytest
import yaml

from llm_mitigation.config import PKG_ROOT, load_config


def _w(path: Path, rows: list[dict]):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


@pytest.fixture
def cfg(tmp_path):
    for sub in ("prompts", "schema"):
        shutil.copytree(PKG_ROOT / sub, tmp_path / sub)
    data = tmp_path / "data"
    data.mkdir()
    B = "http://example.org/airkg/"
    _w(data / "risks.csv", [
        {"nexus_id": "r-injection", "catalogue": "ibm", "name": "Prompt injection attack",
         "catalogue_identifier": "r-injection", "description": "Crafted prompt input changes model behaviour.",
         "iri": B + "risk/r-injection"},
        {"nexus_id": "r-privacy", "catalogue": "mit", "name": "Personal data leakage",
         "catalogue_identifier": "2.1", "description": "Model output reveals personal data.",
         "iri": B + "risk/r-privacy"},
        {"nexus_id": "r-owasp", "catalogue": "owasp", "name": "LLM09:2025 Misinformation",
         "catalogue_identifier": "LLM09:2025", "description": "", "iri": B + "risk/r-owasp"},
    ])
    _w(data / "controls.csv", [
        {"nexus_id": f"C{i}", "name": n, "description": d, "group_ids": g, "iri": B + f"mitigation/C{i}"}
        for i, (n, d, g) in enumerate([
            ("Input filtering", "Filter prompt input for injected instructions.", "g2.1"),
            ("Red teaming", "Test model behaviour against prompt injection attacks.", "g3.1"),
            ("Data minimisation", "Remove personal data before training.", "g3.2"),
            ("Output review", "Human review of model output for misinformation.", "g3.1"),
            ("Board oversight", "A board oversees safety decisions.", "g1.1"),
            ("Privacy audit", "Audit personal data handling.", "g3.2"),
        ])])
    _w(data / "groups.csv", [
        {"group_id": "g1", "name": "1. Governance", "broader_id": ""},
        {"group_id": "g1.1", "name": "1.1 Board", "broader_id": "g1"},
        {"group_id": "g2", "name": "2. Technical", "broader_id": ""},
        {"group_id": "g2.1", "name": "2.1 Security", "broader_id": "g2"},
        {"group_id": "g3", "name": "3. Operational", "broader_id": ""},
        {"group_id": "g3.1", "name": "3.1 Testing", "broader_id": "g3"},
        {"group_id": "g3.2", "name": "3.2 Data", "broader_id": "g3"},
    ])
    conf = yaml.safe_load((PKG_ROOT / "config.yaml").read_text(encoding="utf-8"))
    conf["provider"] = "fake"
    conf["shortlist"]["k"] = 3
    conf["paths"] = {"risks": "data/risks.csv", "controls": "data/controls.csv", "groups": "data/groups.csv",
                     "prompt": "prompts/link_mitigations.md", "schema": "schema/response.schema.json",
                     "output_dir": "output", "cache_dir": "cache", "accepted_out": "data/accepted.csv"}
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(conf), encoding="utf-8")
    return load_config(tmp_path / "config.yaml")

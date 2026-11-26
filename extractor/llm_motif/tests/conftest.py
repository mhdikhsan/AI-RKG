"""Offline fixtures: a temp config with 3 incidents and 3 risks; the real ontology is read. No network."""
import csv
import shutil
from pathlib import Path

import pytest
import yaml

from llm_motif.core import PKG_ROOT, load_cfg

INCIDENT_COLS = ["incident_id", "source", "record_class", "title", "description", "url", "date", "deployer", "developer",
                 "harmed_parties", "mit_risk_ids", "mit_entity", "mit_timing", "mit_intent", "gmf_goal", "gmf_technology",
                 "gmf_failure", "gmf_potential_technology", "gmf_potential_failure", "gmf_published", "cset_sector",
                 "cset_autonomy", "cset_ai_task", "cset_data_inputs", "avid_artifacts", "avid_lifecycle", "avid_sep",
                 "avid_risk_domain", "license"]


def _w(path: Path, header: list[str], rows: list[dict]):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=header, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})


@pytest.fixture
def cfg(tmp_path):
    for sub in ("prompts", "schema"):
        shutil.copytree(PKG_ROOT / sub, tmp_path / sub)
    data = tmp_path / "data"
    data.mkdir()
    B = "http://example.org/airkg/"
    _w(data / "risks.csv", ["nexus_id", "catalogue", "name", "catalogue_identifier", "description", "iri"], [
        {"nexus_id": "r-toxic", "catalogue": "mit", "name": "Exposure to toxic content", "catalogue_identifier": "1.2",
         "description": "AI exposing users to harmful, abusive or inappropriate content.", "iri": B + "risk/r-toxic"},
        {"nexus_id": "r-injection", "catalogue": "owasp", "name": "Prompt injection", "catalogue_identifier": "LLM01:2025",
         "description": "Crafted input changes the behaviour of a language model.", "iri": B + "risk/r-injection"},
        {"nexus_id": "r-bias", "catalogue": "ibm", "name": "Output bias", "catalogue_identifier": "r-bias",
         "description": "Generated content might unfairly represent groups.", "iri": B + "risk/r-bias"}])
    _w(data / "incidents.csv", INCIDENT_COLS, [
        {"incident_id": "aiid-1", "source": "aiid", "record_class": "AIID incident", "title": "Chatbot made offensive remarks",
         "description": "A chatbot used derogatory language towards minority groups.", "url": "https://incidentdatabase.ai/cite/1/",
         "mit_risk_ids": "r-toxic", "gmf_goal": "Chatbot", "gmf_technology": "Transformer"},
        {"incident_id": "aiid-2", "source": "aiid", "record_class": "AIID incident", "title": "Assistant leaked its system prompt",
         "description": "Users injected instructions into a language model assistant.", "url": "https://incidentdatabase.ai/cite/2/",
         "gmf_goal": "Chatbot", "gmf_technology": "Language Modeling"},
        {"incident_id": "aiid-3", "source": "aiid", "record_class": "AIID incident", "title": "No GMF classification",
         "description": "Skipped by scope (aiid_require_gmf).", "url": "https://incidentdatabase.ai/cite/3/"}])
    conf = yaml.safe_load((PKG_ROOT / "config.yaml").read_text(encoding="utf-8"))
    conf["provider"] = "fake"
    conf["shortlist"]["k_risks"] = 2
    conf["group"]["min_support"] = 1          # two test incidents: abstract every group
    (tmp_path / "staging").mkdir()
    conf["paths"].update({"incidents": "data/incidents.csv", "risks": "data/risks.csv", "output_dir": "output",
                          "cache_dir": "cache", "accepted_dir": "staging"})
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(conf), encoding="utf-8")
    return load_cfg(tmp_path / "config.yaml")

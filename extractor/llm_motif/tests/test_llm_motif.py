import csv
import json
import os
import shutil
from pathlib import Path

import pytest
from rdflib import RDF, Graph, Namespace, URIRef

from llm_mitigation.ontology import REPO_ROOT
from llm_motif import check, review, stages
from llm_motif.core import Vocab, check_structure, evidence_report
from llm_motif.fake import FakeMotifProvider

AK = Namespace("http://example.org/airkg#")


@pytest.fixture(scope="module")
def vocab():
    return Vocab()


def run_all(cfg, vocab, provider=None):
    provider = provider or FakeMotifProvider()
    s1 = stages.run_profiles(cfg, provider, vocab, log=lambda *_: None)
    stages.group_profiles(cfg)
    s2 = stages.run_motifs(cfg, provider, vocab, log=lambda *_: None)
    return provider, s1, s2


def test_scope_and_shortlist(cfg, vocab):
    incs = stages.load_incidents(cfg)
    assert [i["incident_id"] for i in incs] == ["aiid-1", "aiid-2"]           # aiid-3 has no GMF data
    sl = stages.build_risk_shortlist(cfg, incs, stages.load_risks(cfg))
    assert "r-toxic" in sl["aiid-1"]                                            # AIID's MIT label always offered
    assert len(sl["aiid-2"]) <= 2


def test_dry_run_makes_no_calls_and_shows_ontology(cfg, vocab):
    assert stages.dry_run(cfg, vocab, "profile") == 2
    text = (Path(cfg.path("output_dir")) / "prompts_preview" / "profile" / "aiid-1.md").read_text(encoding="utf-8")
    assert "Classes (`X < Y`" in text and "uses (object): Process -> " in text   # ontology given as fixed schema
    assert '"enum"' in text


def test_ontology_check_rejects_wrong_domain_and_range(vocab):
    bad = {"elements": [{"id": "e1", "class": "Data"}, {"id": "e2", "class": "Infer"}],
           "flows": [{"from": "e1", "relation": "uses", "to": "e2"}], "contexts": [], "failure_point": "e9"}
    errs = check_structure(bad, vocab, "failure_point")
    assert any("cannot uses" in e for e in errs) and any("cannot be usesd" in e for e in errs)
    assert any("failure_point" in e for e in errs)
    good = {"elements": [{"id": "e1", "class": "Data"}, {"id": "e2", "class": "Infer"}, {"id": "e3", "class": "LLM"}],
            "flows": [{"from": "e2", "relation": "uses", "to": "e1"}, {"from": "e2", "relation": "uses", "to": "e3"}],
            "contexts": [], "failure_point": "e2"}
    assert check_structure(good, vocab, "failure_point") == []


def test_invalid_answer_retried_then_skipped(cfg, vocab):
    wrong = json.dumps({"elements": [{"id": "e1", "class": "Data", "label": "x", "evidence": ""},
                                     {"id": "e2", "class": "Data", "label": "y", "evidence": ""}],
                        "flows": [{"from": "e1", "relation": "uses", "to": "e2"}], "contexts": [], "failure_point": "",
                        "risks": [], "confidence": "low", "issues": []})
    p = FakeMotifProvider(responses=[wrong, "{not json", wrong, wrong])
    s = stages.run_profiles(cfg, p, vocab, log=lambda *_: None)
    assert s.get("skipped") == 2 and p.calls == 4                              # 1 retry each, then skip


def test_full_run_cached_and_reproducible(cfg, vocab):
    p, s1, s2 = run_all(cfg, vocab)
    assert s1["profiles"] == 2 and s2["motifs"] >= 1
    calls = p.calls
    out = Path(cfg.path("output_dir"))
    first = (out / "motifs.jsonl").read_text(encoding="utf-8")
    run_all(cfg, vocab, p)                                                     # same inputs -> all from cache
    assert p.calls == calls
    assert (out / "motifs.jsonl").read_text(encoding="utf-8") == first


def test_groups_below_min_support_are_not_abstracted(cfg, vocab):
    p = FakeMotifProvider()
    stages.run_profiles(cfg, p, vocab, log=lambda *_: None)
    cfg["group"]["min_support"] = 99
    rows = stages.group_profiles(cfg)
    assert rows and all(r["sent_to_llm"].startswith("no") for r in rows)
    calls = p.calls
    assert stages.run_motifs(cfg, p, vocab, log=lambda *_: None)["motifs"] == 0 and p.calls == calls
    cfg["group"]["min_support"] = 1
    assert all(r["sent_to_llm"] == "yes" for r in stages.group_profiles(cfg))
    assert stages.run_motifs(cfg, p, vocab, log=lambda *_: None)["motifs"] ==         sum(1 for r in stages.group_profiles(cfg) if r["sent_to_llm"] == "yes")


def test_evidence_check():
    data = {"elements": [{"evidence": "used derogatory language"}, {"evidence": "not in the text"}, {"evidence": ""}]}
    assert evidence_report(data, "A chatbot USED derogatory  language towards groups.") == (1, 2)


def test_behaviour_check_motifs_fire_on_their_support(cfg, vocab):
    run_all(cfg, vocab)
    res = check.run_check(cfg, vocab)
    assert res["motifs"] >= 1 and res["fire_on_all_their_support"] == res["motifs"]


def test_review_apply_and_rml(cfg, vocab, tmp_path):
    run_all(cfg, vocab)
    check.run_check(cfg, vocab)
    sheet = review.export(cfg)
    rows = list(csv.DictReader(open(sheet, encoding="utf-8")))
    assert rows and all(r["decision"] == "" for r in rows) and rows[0]["matches_own_incidents"]
    _accept(sheet, rows, reviewer="")                                          # accepted without a reviewer
    with pytest.raises(SystemExit):
        review.apply(cfg, sheet, vocab)
    with pytest.raises(SystemExit):                                            # sheet with decisions is protected
        review.export(cfg)
    _accept(sheet, rows, reviewer="tester")
    res = review.apply(cfg, sheet, vocab)
    assert res["accepted"] == len(rows)
    # map the accepted CSVs with the pipeline's RML mapping and validate against the SHACL shapes
    import morph_kgc
    (tmp_path / "mappings").mkdir(exist_ok=True)
    shutil.copy(REPO_ROOT / "mappings" / "accepted_motifs.rml.ttl", tmp_path / "mappings")
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        g = morph_kgc.materialize("[CONFIGURATION]\nlogging_level=ERROR\nna_values=,\nnumber_of_processes=1\n"
                                  "[source]\nmappings=mappings/accepted_motifs.rml.ttl\n")
    finally:
        os.chdir(cwd)
    motifs = set(g.subjects(RDF.type, AK.RiskMotif))
    assert len(motifs) == len(rows)
    for m in motifs:
        assert (m, AK.indicatesRisk, None) in g and (m, AK.hasManifestCondition, None) in g
    from pyshacl import validate
    data = check.tbox(vocab) + g
    for r in csv.DictReader(open(cfg.path("risks"), encoding="utf-8")):   # in the pipeline these come from the imports
        data.add((URIRef(r["iri"]), RDF.type, AK.Risk))
    shapes = Graph().parse(REPO_ROOT / vocab.pcfg["ontology"]["shapes"])
    _, results, _ = validate(data, shacl_graph=shapes, inference="none", advanced=True)
    SH = Namespace("http://www.w3.org/ns/shacl#")
    violations = [r for r in results.subjects(RDF.type, SH.ValidationResult)
                  if results.value(r, SH.resultSeverity) == SH.Violation]
    assert violations == [], [str(results.value(v, SH.resultMessage)) for v in violations]


def _accept(sheet, rows, reviewer):
    with open(sheet, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({**r, "decision": "accept", "reviewer": reviewer})


def test_real_provider_sends_one_effort_level_per_stage():
    """Regression: the provider was built from the whole config and sent effort={profile:..,abstract:..}."""
    from llm_mitigation.providers import AnthropicProvider
    from llm_motif.core import load_cfg, stage_cfg
    cfg = load_cfg()
    for stage in ("profile", "abstract"):
        prov = AnthropicProvider.__new__(AnthropicProvider)   # no SDK client, no API key needed
        prov.cfg = stage_cfg(cfg, stage)                       # what the CLI passes to get_provider
        params = prov._params("s", "u", {"type": "object"})
        assert params["output_config"]["effort"] == cfg["effort"][stage]
        assert isinstance(params["output_config"]["effort"], str)


def test_per_source_takes_first_n_of_each_source(cfg):
    cfg["scope"]["sources"] = ["aiid", "avid"]
    cfg["scope"]["per_source"] = {"aiid": 2, "avid": 1}
    got = stages.load_incidents(cfg)
    by = {}
    for r in got:
        by[r["source"]] = by.get(r["source"], 0) + 1
    assert by.get("aiid", 0) <= 2 and by.get("avid", 0) <= 1 and len(got) == sum(by.values())


def _write_profiles(cfg, profiles):
    out = Path(cfg.path("output_dir"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "profiles.jsonl").write_text("".join(json.dumps(p) + "\n" for p in profiles), encoding="utf-8")


def _profile(iid, risk, contexts, model="Model"):
    return {"incident_id": iid, "title": iid, "answer": {
        "elements": [{"id": "e1", "class": "Data"}, {"id": "e2", "class": model}, {"id": "e3", "class": "Infer"},
                     {"id": "e4", "class": "Data"}],
        "flows": [{"from": "e3", "relation": "uses", "to": "e1"}, {"from": "e3", "relation": "uses", "to": "e2"},
                  {"from": "e3", "relation": "produces", "to": "e4"}],
        "contexts": [{"class": c.split("=")[0], "existing": c.split("=")[1], "value": c} for c in contexts],
        "failure_point": "e4", "risks": [{"risk_id": risk, "confidence": "high", "rationale": "x"}],
        "confidence": "high", "issues": []}}


def test_specific_level_groups(cfg):
    """Same shape; a context value shared by a subset forms a specific group under the general one."""
    cfg["group"].update({"min_support": 2, "specific_min_support": 2})
    _write_profiles(cfg, [
        _profile("a1", "r-a", ["DataCategory=personal_data", "Domain=media"]),
        _profile("a2", "r-a", ["DataCategory=personal_data"]),
        _profile("a3", "r-a", ["Domain=media"]),
        _profile("a4", "r-b", ["DataCategory=personal_data", "LifecycleStage=operation"]),
    ])
    rows = {(r["motif_level"], r["shared_context"] or r["top_risk"]): r for r in stages.group_profiles(cfg)}
    gen = rows[("general", "r-a")]
    assert gen["sent_to_llm"] == "yes" and gen["incidents"] == "a1 a2 a3"
    pd = rows[("specific", "DataCategory=personal_data")]
    assert pd["sent_to_llm"] == "yes" and pd["incidents"] == "a1 a2 a4" and pd["general_motif_id"] == gen["motif_id"]
    assert rows[("specific", "Domain=media")]["sent_to_llm"] == "yes"
    assert ("specific", "LifecycleStage=operation") not in rows               # class not used for specific groups
    assert rows[("general", "r-b")]["sent_to_llm"].startswith("no")           # one incident only


def test_specific_group_with_same_incidents_as_general_is_skipped(cfg):
    cfg["group"].update({"min_support": 2, "specific_min_support": 2})
    _write_profiles(cfg, [_profile("a1", "r-a", ["Domain=media"]), _profile("a2", "r-a", ["Domain=media"])])
    spec = [r for r in stages.group_profiles(cfg) if r["motif_level"] == "specific"]
    assert len(spec) == 1 and spec[0]["sent_to_llm"].startswith("no (same incidents")


def test_level_check_requires_context_and_parent_shape():
    g = {"motif_level": "specific", "shared_context": "DataCategory=personal_data", "architecture_classes": "Data,Infer,Model"}
    parent = {"answer": _profile("p", "r-a", [])["answer"]}
    ok = dict(parent["answer"], contexts=[{"class": "DataCategory", "existing": "personal_data", "value": "x"}])
    assert stages.level_check(g, parent)(ok) == []
    assert any("context" in e for e in stages.level_check(g, parent)(dict(ok, contexts=[])))
    other = _profile("q", "r-a", ["DataCategory=personal_data"], model="LLM")["answer"]
    assert any("architecture" in e for e in stages.level_check(g, parent)(other))
    assert stages.level_check({"motif_level": "general"}, None)(other) == []


def test_covered_by_marks_narrower_same_risk_motifs_only():
    from llm_motif.check import covered_by
    motifs = [{"motif_key": k, "answer": {"risk_id": r}} for k, r in
              [("gen", "r-a"), ("spec", "r-a"), ("other", "r-b"), ("dupa", "r-c"), ("dupb", "r-c")]]
    # motif -> templates it fires on: gen fires on spec's template (spec is narrower); other fires on spec too,
    # but has another risk; dupa and dupb have identical requirements
    on_templates = {"gen": {"gen", "spec"}, "spec": {"spec"}, "other": {"other", "spec"},
                    "dupa": {"dupa", "dupb"}, "dupb": {"dupa", "dupb"}}
    assert covered_by(motifs, on_templates) == {"spec": ["gen"], "dupb": ["dupa"]}


# ==================================================================== evolving KG: apply adds, never replaces
def _read(path):
    return list(csv.DictReader(open(path, encoding="utf-8")))


def _write(path, rows, **changes):
    """Write sheet rows back; `changes` maps motif_id (or '*') to the fields to set."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({**r, **changes.get(r["motif_id"], changes.get("*", {}))})


def _staging(cfg, name="accepted_motifs.csv"):
    return _read(Path(cfg.path("accepted_dir")) / name)


def test_apply_keeps_accepted_motifs_and_adds_new_ones(cfg, vocab):
    run_all(cfg, vocab)
    check.run_check(cfg, vocab)
    rows = _read(review.export(cfg, reviewer="ann"))
    assert len(rows) >= 2 and all(r["review_item"] == review.NEW and r["reviewer"] == "ann" for r in rows)
    first = rows[0]["motif_id"]
    sheet_ann = Path(cfg.path("output_dir")) / "review_sheet_ann.csv"
    _write(sheet_ann, rows, **{first: {"decision": "accept"}})
    assert review.apply(cfg, [sheet_ann], vocab)["new_motifs"] == 1
    # an expert edits the accepted motif by hand in staging
    path = Path(cfg.path("accepted_dir")) / "accepted_motifs.csv"
    acc = _staging(cfg)
    acc[0]["name"] = "Edited by expert"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(acc[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(acc)
    # the next sheet does not offer the accepted motif again
    bob = _read(review.export(cfg, reviewer="bob"))
    assert first not in {r["motif_id"] for r in bob}
    sheet_bob = Path(cfg.path("output_dir")) / "review_sheet_bob.csv"
    _write(sheet_bob, bob, **{"*": {"decision": "accept"}})
    res = review.apply(cfg, [sheet_ann, sheet_bob], vocab)        # ann's old sheet accepts `first` again
    assert res["kept_already_accepted"] == 1 and res["new_motifs"] == len(bob)
    after = {r["identifier"]: r for r in _staging(cfg)}
    assert after[first]["name"] == "Edited by expert"                # reviewed version untouched
    assert len(after) == len(rows)


def test_new_incident_matching_an_accepted_motif_extends_it(cfg, vocab):
    run_all(cfg, vocab)
    check.run_check(cfg, vocab)
    sheet = review.export(cfg)
    rows = _read(sheet)
    _write(sheet, rows, **{"*": {"decision": "accept", "reviewer": "ann"}})
    review.apply(cfg, sheet, vocab)
    n_elements = len(_staging(cfg, "accepted_motif_elements.csv"))
    # a new incident with the same architecture arrives
    out = Path(cfg.path("output_dir"))
    profiles = stages.read_jsonl(out / "profiles.jsonl")
    new = dict(profiles[0], incident_id="aiid-9", title="New incident", url="https://incidentdatabase.ai/cite/9/")
    (out / "profiles.jsonl").write_text("".join(json.dumps(p) + "\n" for p in profiles + [new]), encoding="utf-8")
    res = check.run_check(cfg, vocab)
    assert res["accepted_motifs"] == len(rows) and res["motifs"] == 0     # nothing proposed again
    ext = _read(review.export(cfg, reviewer="bob"))
    assert ext and all(r["review_item"] == review.EXTEND for r in ext)
    assert {r["motif_id"] for r in ext if r["based_on_incidents"] == "aiid-9"} == {r["motif_id"] for r in rows}
    # bob accepts the new incident and rejects the other matches (old incidents of other motifs)
    sheet_bob = out / "review_sheet_bob.csv"
    with open(sheet_bob, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ext[0]), lineterminator="\n")
        w.writeheader()
        w.writerows({**r, "decision": "accept" if r["based_on_incidents"] == "aiid-9" else "reject"} for r in ext)
    n_other = sum(1 for r in ext if r["based_on_incidents"] != "aiid-9")
    res = review.apply(cfg, [sheet_bob], vocab)
    assert res["new_sources"] == len(rows) and res["new_motifs"] == 0
    assert res["rejected_sources_recorded"] == n_other
    added = [s for s in _staging(cfg, "accepted_motif_sources.csv") if s["source_url"].endswith("/cite/9/")]
    assert len(added) == len(rows) and all(s["reviewer"] == "bob" for s in added)
    assert len(_staging(cfg, "accepted_motif_elements.csv")) == n_elements  # structure unchanged
    assert check.run_check(cfg, vocab)["extension_candidates"] == 0        # accepted -> source; rejected -> not offered again


def test_resolve_rules():
    v = {"ann": "accept", "bob": "reject"}
    assert review.resolve(v, "all", 1)[0] == "reject"
    assert review.resolve(v, "any", 1)[0] == "accept"
    assert review.resolve(v, "majority", 1)[0] == ""                  # tie stays undecided
    assert review.resolve({**v, "cy": "accept"}, "majority", 1)[0] == "accept"
    assert review.resolve({"ann": "accept"}, "all", 2)[0] == ""       # too few reviewers
    assert review.resolve({}, "any", 1)[0] == ""


def test_several_reviewers_combined_by_rule(cfg, vocab):
    run_all(cfg, vocab)
    check.run_check(cfg, vocab)
    out = Path(cfg.path("output_dir"))
    for who, d in (("ann", "accept"), ("bob", "reject")):
        _write(out / f"review_sheet_{who}.csv", _read(review.export(cfg, reviewer=who)), **{"*": {"decision": d}})
    sheets = [out / "review_sheet_ann.csv", out / "review_sheet_bob.csv"]
    st = review.status(cfg, sheets)
    assert st["disagreements"] == st["rows"] and st["reject"] == st["rows"]      # default rule: all must accept
    assert review.apply(cfg, sheets, vocab)["new_motifs"] == 0
    cfg["review"] = {"rule": "any", "min_reviewers": 2}
    assert review.apply(cfg, sheets, vocab)["new_motifs"] == st["rows"]
    with pytest.raises(SystemExit, match="already decided"):                     # same reviewer twice
        review.apply(cfg, [sheets[0], sheets[0]], vocab)


# ==================================================================== readable IDs, architecture text
def test_readable_ids_are_stable_and_specific_ids_sit_under_their_general_motif(cfg):
    cfg["group"].update({"min_support": 2, "specific_min_support": 2})
    _write_profiles(cfg, [_profile("a1", "r-a", ["DataCategory=personal_data"]),
                          _profile("a2", "r-a", []), _profile("a3", "r-a", ["DataCategory=personal_data"]),
                          _profile("a4", "r-b", ["DataCategory=personal_data"])])
    rows = {(r["motif_level"], r["shared_context"] or r["top_risk"]): r for r in stages.group_profiles(cfg)}
    gen, spec = rows[("general", "r-a")], rows[("specific", "DataCategory=personal_data")]
    assert gen["motif_id"] == "M-0001" and spec["motif_id"] == "M-0001.1" and spec["general_motif_id"] == "M-0001"
    assert rows[("general", "r-b")]["motif_id"] == ""                  # not sent to the LLM: no ID used up
    # a new profile adds a new group; existing IDs do not change
    _write_profiles(cfg, [_profile("a1", "r-a", ["DataCategory=personal_data"]), _profile("a2", "r-a", []),
                          _profile("a3", "r-a", ["DataCategory=personal_data"]),
                          _profile("a4", "r-b", ["DataCategory=personal_data"]), _profile("a5", "r-b", [])])
    again = {(r["motif_level"], r["shared_context"] or r["top_risk"]): r["motif_id"] for r in stages.group_profiles(cfg)}
    assert again[("general", "r-a")] == "M-0001" and again[("specific", "DataCategory=personal_data")] == "M-0001.1"
    assert again[("general", "r-b")] == "M-0002"


def test_architecture_text_shows_roles_flow_and_risk_location():
    from llm_motif.core import structure_text
    a = {"elements": [{"id": "m1", "class": "Data", "label": "user prompt"}, {"id": "m2", "class": "LLM", "label": "chat model"},
                      {"id": "m3", "class": "Infer", "label": "answer generation"},
                      {"id": "m4", "class": "Data", "label": "answer"}, {"id": "m5", "class": "Data"}],
         "flows": [{"from": "m3", "relation": "uses", "to": "m1"}, {"from": "m3", "relation": "uses", "to": "m2"},
                   {"from": "m3", "relation": "produces", "to": "m4"}], "manifest_condition": "m4"}
    assert structure_text(a) == ("user prompt (Data) + chat model (LLM) -> [answer generation (Infer)] -> "
                                 "answer (Data) [!]; Data")
    assert "[!]" not in structure_text(a, mark=False)

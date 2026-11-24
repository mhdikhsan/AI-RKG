import csv
import json

import pytest

from llm_mitigation import apply as apply_mod
from llm_mitigation import review, run
from llm_mitigation.config import load_inputs, read_csv, write_csv
from llm_mitigation.prompting import api_schema, validation_schema
from llm_mitigation.providers import FakeProvider
from llm_mitigation.shortlist import SHORTLIST_COLS, build_shortlist


def make_shortlist(cfg):
    risks, controls, groups = load_inputs(cfg)
    rows = build_shortlist(risks, controls, groups, cfg["shortlist"]["k"], cfg["shortlist"]["control_fields"])
    write_csv(cfg.path("output_dir") / "shortlist.csv", SHORTLIST_COLS, rows)
    return rows


# ---------------- shortlist
def test_shortlist_deterministic_and_bounded(cfg):
    a, b = make_shortlist(cfg), make_shortlist(cfg)
    assert a == b
    by = {}
    for r in a:
        by.setdefault(r["risk_id"], []).append(r)
    assert all(len(v) <= 3 for v in by.values())
    assert [r["rank"] for r in by["r-injection"]] == list(range(1, len(by["r-injection"]) + 1))
    # the most specific control ranks first
    assert by["r-injection"][0]["mitigation_id"] in {"C0", "C1"}
    assert by["r-privacy"][0]["mitigation_id"] in {"C2", "C5"}


def test_shortlist_scores_sorted_and_positive(cfg):
    for rid in {"r-injection", "r-privacy", "r-owasp"}:
        scores = [float(r["score"]) for r in make_shortlist(cfg) if r["risk_id"] == rid]
        assert scores == sorted(scores, reverse=True)
        assert all(s > 0 for s in scores)


# ---------------- .env loading
def test_load_env_sets_missing_and_keeps_existing(tmp_path, monkeypatch):
    from llm_mitigation.env import load_env
    f = tmp_path / ".env"
    f.write_text('# comment\nAIRKG_TEST_A="from-file"\nexport AIRKG_TEST_B=file-b\nAIRKG_TEST_EMPTY=\nnot a line\n',
                 encoding="utf-8")
    monkeypatch.delenv("AIRKG_TEST_A", raising=False)
    monkeypatch.setenv("AIRKG_TEST_B", "from-shell")
    assert load_env(f) == ["AIRKG_TEST_A"]
    import os
    assert os.environ["AIRKG_TEST_A"] == "from-file" and os.environ["AIRKG_TEST_B"] == "from-shell"
    assert "AIRKG_TEST_EMPTY" not in os.environ
    monkeypatch.delenv("AIRKG_TEST_A")
    assert load_env(tmp_path / "missing.env") == []


# ---------------- schema validation
def test_schema_accepts_valid_and_rejects_invalid(cfg):
    s = validation_schema(cfg, ["C0", "C1"])
    ok = json.dumps({"links": [{"mitigation_id": "C0", "confidence": "high", "rationale": "Blocks it."}]})
    assert run.parse_answer(ok, s)["links"][0]["mitigation_id"] == "C0"
    for bad in ["not json",
                json.dumps({"links": [{"mitigation_id": "C9", "confidence": "high", "rationale": "x"}]}),
                json.dumps({"links": [{"mitigation_id": "C0", "confidence": "sure", "rationale": "x"}]}),
                json.dumps({"links": [{"mitigation_id": "C0", "confidence": "low", "rationale": "x", "extra": 1}]}),
                json.dumps({"links": [{"mitigation_id": "C0", "confidence": "low", "rationale": "x" * 500}]})]:
        with pytest.raises(ValueError):
            run.parse_answer(bad, s)


def test_api_schema_keeps_enum_drops_length_limits(cfg):
    a = api_schema(validation_schema(cfg, ["C0"]))
    item = a["properties"]["links"]["items"]
    assert item["properties"]["mitigation_id"]["enum"] == ["C0"]
    assert "maxItems" not in a["properties"]["links"] and "maxLength" not in item["properties"]["rationale"]
    assert item["additionalProperties"] is False


# ---------------- run, cache, retry
def test_run_uses_cache_and_is_reproducible(cfg):
    make_shortlist(cfg)
    p1 = FakeProvider()
    s1 = run.run(cfg, provider=p1, log=lambda *_: None)
    first = (cfg.path("output_dir") / "candidates.csv").read_bytes()
    assert p1.calls == 3 and s1["called"] == 3
    p2 = FakeProvider()
    s2 = run.run(cfg, provider=p2, log=lambda *_: None)
    assert p2.calls == 0 and s2["cached"] == 3
    assert (cfg.path("output_dir") / "candidates.csv").read_bytes() == first
    rows = read_csv(cfg.path("output_dir") / "candidates.csv")
    assert {r["model_version"] for r in rows} == {"fake-model-1"}
    assert all(len(r["prompt_sha256"]) == 64 and r["decision"] == "" for r in rows)


def test_run_retries_once_then_skips(cfg):
    make_shortlist(cfg)
    run_cfg = cfg
    run_cfg["scope"]["catalogues"] = ["ibm"]                        # one risk
    p = FakeProvider(responses=["{broken", "still not json"])
    stats = run.run(run_cfg, provider=p, log=lambda *_: None)
    assert p.calls == 2 and stats["skipped"] == 1
    assert not list(cfg.path("cache_dir").glob("*.json"))          # invalid answers are never cached
    p2 = FakeProvider(responses=["{broken"])                         # 1st invalid, 2nd valid (generated)
    stats = run.run(run_cfg, provider=p2, log=lambda *_: None)
    assert p2.calls == 2 and stats["called"] == 1


def test_ids_outside_shortlist_rejected(cfg):
    make_shortlist(cfg)
    cfg["scope"]["catalogues"] = ["ibm"]
    ids = {r["mitigation_id"] for r in read_csv(cfg.path("output_dir") / "shortlist.csv") if r["risk_id"] == "r-injection"}
    outside = next(c for c in ["C4", "C5", "C3", "C2"] if c not in ids)
    bad = json.dumps({"links": [{"mitigation_id": outside, "confidence": "high", "rationale": "x"}]})
    p = FakeProvider(responses=[bad, bad])
    stats = run.run(cfg, provider=p, log=lambda *_: None)
    assert stats["skipped"] == 1 and stats["candidates"] == 0
    assert read_csv(cfg.path("output_dir") / "candidates.csv") == []


def test_cache_key_depends_on_provider_and_model(cfg):
    k = run.cache_key(cfg, "s", "u", {})
    cfg["provider"] = "anthropic"
    k2 = run.cache_key(cfg, "s", "u", {})
    cfg["model"] = "claude-haiku-5-5"
    assert len({k, k2, run.cache_key(cfg, "s", "u", {})}) == 3


def test_dry_run_makes_no_calls(cfg):
    make_shortlist(cfg)
    assert run.dry_run(cfg) == 3
    assert len(list((cfg.path("output_dir") / "prompts_preview").glob("*.md"))) == 3
    assert not cfg.path("cache_dir").exists()


def test_estimate_counts_calls_and_skips_cached(cfg):
    make_shortlist(cfg)
    e = run.estimate(cfg)
    assert e["calls"] == 3 and e["cached_free"] == 0 and e["input_tokens"] > 0
    run.run(cfg, provider=FakeProvider(), log=lambda *_: None)
    assert run.estimate(cfg)["calls"] == 0


# ---------------- review + apply
def _reviewed(cfg, decisions):
    make_shortlist(cfg)
    run.run(cfg, provider=FakeProvider(), log=lambda *_: None)
    sheet = review.export(cfg, force=True)
    rows = read_csv(sheet)
    for r, (rev, dec) in zip(rows, decisions):
        r["reviewer"], r["decision"] = rev, dec
    with open(sheet, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return sheet, rows


def test_apply_keeps_only_accepted(cfg):
    sheet, rows = _reviewed(cfg, [("mi", "accept"), ("mi", "reject"), ("", ""), ("mi", "ACCEPT")])
    stats = apply_mod.apply(cfg, sheet)
    out = read_csv(cfg.path("accepted_out"))
    assert stats["accepted"] == 2 == len(out)
    assert {(o["risk_id"], o["mitigation_id"]) for o in out} == {(rows[0]["risk_id"], rows[0]["mitigation_id"]),
                                                                (rows[3]["risk_id"], rows[3]["mitigation_id"])}
    assert all(o["risk_iri"].startswith("http://example.org/airkg/risk/") and o["mitigation_iri"] for o in out)


def test_apply_rejects_bad_sheet(cfg):
    sheet, _ = _reviewed(cfg, [("", "accept")])                    # accept without reviewer
    with pytest.raises(SystemExit):
        apply_mod.apply(cfg, sheet)
    sheet, _ = _reviewed(cfg, [("mi", "maybe")])
    with pytest.raises(SystemExit):
        apply_mod.apply(cfg, sheet)


def test_review_export_protects_decisions(cfg):
    sheet, _ = _reviewed(cfg, [("mi", "accept")])
    with pytest.raises(SystemExit):
        review.export(cfg)
    assert review.export(cfg, force=True) == sheet

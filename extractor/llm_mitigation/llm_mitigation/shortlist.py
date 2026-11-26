from __future__ import annotations

import math
import re
from collections import Counter

STOP = set("""a an and are as at be by can could does for from has have how if in into is it its may might
more most no not of on or other such that the their them then there these this those to was were when which
while with within without would should will also any all ai system systems model models use used using
based e g i e etc via""".split())
TOKEN = re.compile(r"[a-z0-9]+")
OWASP_CODE = re.compile(r"^llm\d{2}:\d{4}\s*", re.I)


def tokens(text: str) -> list[str]:
    out = []
    for t in TOKEN.findall(text.lower()):
        if len(t) < 2 or t in STOP or t.isdigit():
            continue
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out


def group_names(control: dict, groups: dict) -> str:
    names = []
    for gid in control.get("group_ids", "").split():
        g = groups.get(gid)
        if not g:
            continue
        names.append(g["name"])
        parent = groups.get(g.get("broader_id", ""))
        if parent:
            names.append(parent["name"])
    return " ".join(names)


def control_text(control: dict, groups: dict, fields: list[str]) -> str:
    parts = []
    if "name" in fields:
        parts.append(control.get("name", ""))
    if "group" in fields:
        parts.append(group_names(control, groups))
    if "description" in fields:
        parts.append(control.get("description", ""))
    return " ".join(parts)


def risk_text(risk: dict) -> str:
    return OWASP_CODE.sub("", risk.get("name", "")) + " " + risk.get("description", "")


class TfIdf:
    def __init__(self, docs: dict[str, list[str]]):
        n = len(docs)
        df = Counter(t for toks in docs.values() for t in set(toks))
        self.idf = {t: math.log((1 + n) / (1 + d)) + 1.0 for t, d in df.items()}
        self.vecs = {k: self.vector(v) for k, v in docs.items()}

    def vector(self, toks: list[str]) -> dict[str, float]:
        tf = Counter(t for t in toks if t in self.idf)
        v = {t: (1 + math.log(c)) * self.idf[t] for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    @staticmethod
    def cosine(a: dict, b: dict) -> float:
        if len(a) > len(b):
            a, b = b, a
        return sum(x * b.get(t, 0.0) for t, x in a.items())


def build_shortlist(risks: list[dict], controls: dict[str, dict], groups: dict, k: int,
                    fields: list[str], exclude: set[tuple[str, str]] | None = None) -> list[dict]:
    index = TfIdf({cid: tokens(control_text(c, groups, fields)) for cid, c in controls.items()})
    exclude = exclude or set()
    rows = []
    for r in risks:
        q = index.vector(tokens(risk_text(r)))
        scored = [(round(index.cosine(q, v), 6), cid) for cid, v in index.vecs.items()
                  if (r["nexus_id"], cid) not in exclude]
        scored = sorted((s for s in scored if s[0] > 0), key=lambda x: (-x[0], x[1]))[:k]
        for rank, (score, cid) in enumerate(scored, 1):
            rows.append({"risk_id": r["nexus_id"], "rank": rank, "mitigation_id": cid, "score": f"{score:.6f}"})
    return rows


SHORTLIST_COLS = ["risk_id", "rank", "mitigation_id", "score"]

"""Fetch sources at pinned versions and write sources/manifest.json.

- IBM AI Atlas Nexus: fetch exactly the pinned commit (shallow), copy the needed files to
  sources/nexus/<same relative path>, record SHA-256.
- DPV: treeless sparse clone at the pinned commit; only dpv.ttl / ai.ttl (IRI existence check).
- BEAM: try to download; if blocked, expect sources/manual/beam_core.ttl.
- Manual files: report which are present / missing.

The 'fetched' date of a source is kept from the previous manifest when commit and checksums are
unchanged, so reruns produce a byte-identical manifest.
"""
from __future__ import annotations

import datetime as dt
import shutil
import subprocess
import urllib.request

from scripts.common import (MANIFEST, MANUAL, NEXUS_DIR, ROOT, SOURCES, load_config, log,
                            manifest, sha256_file, write_json)

CLONES = SOURCES / "_clones"
TODAY = dt.date.today().isoformat()


def git(*args: str, cwd=None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout.strip()


def fetch_commit(repo: str, commit: str, dest, sparse: list[str] | None = None) -> str:
    """Make `dest` a checkout of exactly `commit` (shallow). Returns the checked-out commit."""
    dest.mkdir(parents=True, exist_ok=True)
    if not (dest / ".git").exists():
        git("init", "-q", cwd=dest)
        git("remote", "add", "origin", repo, cwd=dest)
    try:
        head = git("rev-parse", "HEAD", cwd=dest)
    except subprocess.CalledProcessError:
        head = ""
    if head != commit:
        extra = ["--filter=blob:none"] if sparse else []
        git("fetch", "-q", "--depth", "1", *extra, "origin", commit, cwd=dest)
        if sparse:
            git("sparse-checkout", "set", "--no-cone", *sparse, cwd=dest)
        git("checkout", "-q", "--force", "FETCH_HEAD", cwd=dest)
    elif sparse:
        git("sparse-checkout", "set", "--no-cone", *sparse, cwd=dest)
    got = git("rev-parse", "HEAD", cwd=dest)
    if got != commit:
        raise SystemExit(f"ERROR: {repo} is at {got}, expected pinned {commit}")
    return got


def keep_date(prev: dict, commit: str, files: dict) -> str:
    if prev.get("commit") == commit and prev.get("files") == files and prev.get("fetched"):
        return prev["fetched"]
    return TODAY


def fetch_nexus(cfg: dict, prev: dict) -> dict:
    n = cfg["sources"]["nexus"]
    clone = CLONES / "ai-atlas-nexus"
    log(f"nexus: fetching {n['repo']} @ {n['commit']}")
    fetch_commit(n["repo"], n["commit"], clone)
    files = {}
    for rel in n["files"]:
        src = clone / n["data_dir"] / rel
        if not src.exists():
            raise SystemExit(f"ERROR: {rel} not found in Nexus at {n['commit']} (provide the files manually)")
        dst = NEXUS_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        files[rel] = sha256_file(dst)
    log(f"nexus: {len(files)} files copied to sources/nexus/")
    return {"url": n["repo"], "commit": n["commit"], "commit_date": n["commit_date"],
            "path": f"{n['data_dir']}/", "files": files,
            "fetched": keep_date(prev.get("nexus", {}), n["commit"], files)}


def fetch_dpv(cfg: dict, prev: dict) -> dict:
    d = cfg["sources"]["dpv"]
    clone = CLONES / "dpv"
    paths = [f"{d['version']}/dpv/dpv.ttl", f"{d['version']}/ai/ai.ttl"]
    try:
        fetch_commit(d["repo"], d["commit"], clone, sparse=paths)
    except (subprocess.CalledProcessError, SystemExit) as e:
        log(f"dpv: could not fetch ({e}); IRI check will be skipped")
        return {"url": d["repo"], "status": "unavailable"}
    files = {p: sha256_file(clone / p) for p in paths}
    log(f"dpv: {len(files)} files at {d['commit'][:7]}")
    return {"url": d["repo"], "commit": d["commit"], "version": d["version"],
            "local": "sources/_clones/dpv/", "files": files,
            "fetched": keep_date(prev.get("dpv", {}), d["commit"], files)}


def fetch_beam(cfg: dict, prev: dict) -> dict:
    b = cfg["sources"]["beam"]
    target = ROOT / b["manual_file"]
    status = "manual"
    if not target.exists():
        try:
            req = urllib.request.Request(b["url"], headers={"User-Agent": "airkg-pipeline"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            status = "downloaded"
        except Exception as e: 
            log(f"beam: download blocked ({type(e).__name__}: {e}); place it at {b['manual_file']}")
            return {"url": b["url"], "status": "missing", "expected": b["manual_file"]}
    checksum = sha256_file(target)
    p = prev.get("beam", {})
    same = p.get("sha256") == checksum and p.get("fetched")
    fetched = p["fetched"] if same else TODAY
    status = p.get("status", status) if same else status
    log(f"beam: {status} ({b['manual_file']})")
    return {"url": b["url"], "status": status, "file": b["manual_file"], "sha256": checksum,
            "fetched": fetched}


def check_manual(cfg: dict) -> dict:
    out = {}
    for p in sorted(MANUAL.glob("*")):
        if p.name == "README.md":
            continue
        out[f"sources/manual/{p.name}"] = sha256_file(p)
    iso = ROOT / cfg["sources"]["iso22989"]["manual_file"]
    rows = max(0, len(iso.read_text(encoding="utf-8").strip().splitlines()) - 1) if iso.exists() else 0
    missing = [f for f, ok in [(cfg["sources"]["beam"]["manual_file"], (ROOT / cfg["sources"]["beam"]["manual_file"]).exists()),
                               (cfg["sources"]["iso22989"]["manual_file"], iso.exists() and rows > 0)] if not ok]
    for m in missing:
        log(f"manual: MISSING or empty: {m}")
    return {"files": out, "iso22989_rows": rows, "missing_or_empty": missing}


def main() -> None:
    cfg = load_config()
    prev = manifest()
    m = {"nexus": fetch_nexus(cfg, prev), "dpv": fetch_dpv(cfg, prev),
         "beam": fetch_beam(cfg, prev), "manual": check_manual(cfg)}
    write_json(MANIFEST, m)
    log(f"wrote {MANIFEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

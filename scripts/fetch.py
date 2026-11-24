"""Fetch sources at pinned versions and write sources/manifest.json.

- IBM AI Atlas Nexus: fetch exactly the pinned commit (shallow), copy the needed files to
  sources/nexus/<same relative path>, record SHA-256.
- DPV: treeless sparse clone at the pinned commit; only the files in sources.dpv.files (IRI existence check).
- BEAM: try to download; if blocked, expect sources/manual/beam_core.ttl.
- Manual files: report which are present / missing.

The 'fetched' date of a source is kept from the previous manifest when commit and checksums are
unchanged, so reruns produce a byte-identical manifest.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import shutil
import subprocess
import tarfile
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
    paths = d["files"]
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


AIID_DIR = SOURCES / "aiid"
AVID_DIR = SOURCES / "avid"


def fetch_aiid(cfg: dict, prev: dict) -> dict:
    """Pinned AIID snapshot: download once, verify SHA-256, extract only the configured CSV exports."""
    a = cfg["sources"].get("aiid")
    if not a:
        return {}
    AIID_DIR.mkdir(parents=True, exist_ok=True)
    archive = AIID_DIR / a["snapshot"]
    if not archive.exists() or sha256_file(archive) != a["sha256"]:
        url = a["url"].format(snapshot=a["snapshot"])
        log(f"aiid: downloading {a['snapshot']}")
        req = urllib.request.Request(url, headers={"User-Agent": "airkg-pipeline"})
        tmp = archive.with_suffix(archive.suffix + ".part")
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as fh:
            shutil.copyfileobj(r, fh, length=1 << 20)
        tmp.replace(archive)
    got = sha256_file(archive)
    if got != a["sha256"]:
        raise SystemExit(f"ERROR: AIID snapshot {a['snapshot']} has sha256 {got}, expected {a['sha256']}")
    out = AIID_DIR / "extracted"
    out.mkdir(exist_ok=True)
    want = set(a["extract"])
    files = {}
    with tarfile.open(archive, "r:bz2") as tf:
        for m in tf.getmembers():
            name = m.name.rsplit("/", 1)[-1]
            # top-level CSV exports only (the archive also holds BSON dumps and translations)
            if m.isfile() and name in want and m.name.count("/") == 1:
                with tf.extractfile(m) as src, open(out / name, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                files[name] = sha256_file(out / name)
    missing = sorted(want - set(files))
    if missing:
        raise SystemExit(f"ERROR: AIID snapshot lacks {missing}")
    log(f"aiid: {len(files)} files extracted to {out.relative_to(ROOT)}/")
    p = prev.get("aiid", {})
    return {"url": a["url"].format(snapshot=a["snapshot"]), "snapshot": a["snapshot"],
            "snapshot_date": a["snapshot_date"], "sha256": got, "files": files,
            "fetched": p["fetched"] if p.get("sha256") == got and p.get("fetched") else TODAY}


def fetch_avid(cfg: dict, prev: dict) -> dict:
    """AVID records at the pinned commit (sparse checkout of the configured folders only)."""
    v = cfg["sources"].get("avid")
    if not v:
        return {}
    fetch_commit(v["repo"], v["commit"], AVID_DIR, sparse=[p.rstrip("/") + "/" for p in v["paths"]])
    files = {}
    for p in v["paths"]:
        for f in sorted((AVID_DIR / p).rglob("*.json")):
            files[f.relative_to(AVID_DIR).as_posix()] = sha256_file(f)
    log(f"avid: {len(files)} JSON records at {v['commit'][:7]}")
    # one checksum over all record checksums (the manifest stays small)
    digest = hashlib.sha256("\n".join(f"{k} {h}" for k, h in sorted(files.items())).encode()).hexdigest()
    p = prev.get("avid", {})
    same = p.get("commit") == v["commit"] and p.get("files_sha256") == digest and p.get("fetched")
    return {"url": v["repo"], "commit": v["commit"], "paths": v["paths"], "n_files": len(files),
            "files_sha256": digest, "fetched": p["fetched"] if same else TODAY}


def check_manual(cfg: dict) -> dict:
    out = {}
    for p in sorted(MANUAL.rglob("*")):
        if not p.is_file() or p.name == "README.md":
            continue
        out[f"sources/manual/{p.relative_to(MANUAL).as_posix()}"] = sha256_file(p)
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
    for key, fn in (("aiid", fetch_aiid), ("avid", fetch_avid)):
        entry = fn(cfg, prev)
        if entry:
            m[key] = entry
    write_json(MANIFEST, m)
    log(f"wrote {MANIFEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

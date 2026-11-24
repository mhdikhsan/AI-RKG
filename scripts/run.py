"""Make-free pipeline runner (same targets as the Makefile).

Usage:  python -m scripts.run <target> [<target> ...]
Targets: fetch stage map merge validate coverage report site all check-ontology accept-ontology
(accept-ontology: after an intended edit of the ontology/shapes files, check they parse and record their new hashes)
(The LLM extractors in extractor/ run separately; see extractor/README.md.)
"""
from __future__ import annotations

import importlib
import sys

from scripts.common import accept_ontology_changes, check_ontology_unchanged, log

STEPS = ["fetch", "stage", "map", "merge", "validate", "coverage", "report", "site"]
ALIASES = {"all": STEPS}


def run_step(name: str) -> None:
    if name == "accept-ontology":
        changed = accept_ontology_changes()
        log("\n".join(f"accepted {c}" for c in changed) if changed else "nothing to accept; ontology files unchanged")
        return
    if name == "check-ontology":
        check_ontology_unchanged()
        log("ontology files unchanged")
        return
    log(f"=== {name} ===")
    mod = importlib.import_module(f"scripts.{name}")
    mod.main()


def main(argv: list[str]) -> None:
    targets = argv or ["all"]
    for t in targets:
        steps = ALIASES.get(t, [t])
        for s in steps:
            if s not in STEPS and s not in ("check-ontology", "accept-ontology"):
                sys.exit(f"unknown target: {s}")
            if s != "accept-ontology":
                check_ontology_unchanged()
            run_step(s)
    check_ontology_unchanged()
    log("done; ontology files unchanged")


if __name__ == "__main__":
    main(sys.argv[1:])

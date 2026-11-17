"""Make-free pipeline runner (same targets as the Makefile).

Usage:  python -m scripts.run <target> [<target> ...]
Targets: fetch stage map merge validate report site all check-ontology
"""
from __future__ import annotations

import importlib
import sys

from scripts.common import check_ontology_unchanged, log

STEPS = ["fetch", "stage", "map", "roles", "authored", "merge", "validate", "coverage", "report", "site"]
ALIASES = {"all": STEPS}


def run_step(name: str) -> None:
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
            if s not in STEPS and s != "check-ontology":
                sys.exit(f"unknown target: {s}")
            check_ontology_unchanged()
            run_step(s)
    check_ontology_unchanged()
    log("done; ontology files unchanged")


if __name__ == "__main__":
    main(sys.argv[1:])

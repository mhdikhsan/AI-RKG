from __future__ import annotations

import os
from pathlib import Path

from .ontology import REPO_ROOT

ENV_FILE = REPO_ROOT / ".env"


def load_env(path: Path | None = None) -> list[str]:
    path = Path(path) if path else ENV_FILE
    if not path.exists():
        return []
    loaded = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if name and value and name not in os.environ:
            os.environ[name] = value
            loaded.append(name)
    return loaded

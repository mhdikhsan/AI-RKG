"""Load settings such as ANTHROPIC_API_KEY from the repository's `.env` file (git-ignored).

Format: one `NAME=value` per line; `#` starts a comment; surrounding quotes are removed.
A variable that is already set in the environment wins over the file, so a key exported in the
shell (or an `ant auth login` profile, which the SDK reads itself) is never overridden.
"""
from __future__ import annotations

import os
from pathlib import Path

from .ontology import REPO_ROOT

ENV_FILE = REPO_ROOT / ".env"


def load_env(path: Path | None = None) -> list[str]:
    """Set variables from the file that are not set yet. Returns their names (never the values)."""
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

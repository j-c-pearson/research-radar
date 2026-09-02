from __future__ import annotations

import os
from pathlib import Path


def load_local_env(project_dir: Path = Path(".")) -> None:
    for filename in [".env", ".env.local"]:
        path = project_dir / filename
        if path.exists():
            _load_env_file(path)


def _load_env_file(path: Path) -> None:
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key:
            continue
        os.environ.setdefault(key, _clean_value(value.strip()))


def _clean_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value

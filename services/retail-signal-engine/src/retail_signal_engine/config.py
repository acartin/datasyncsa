"""Environment configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path


SERVICE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = SERVICE_DIR.parents[1]
ENV_PATH = REPO_ROOT / ".env"


def parse_env(path: Path = ENV_PATH) -> dict[str, str]:
    env: dict[str, str] = {}
    if path.exists():
        for raw_line in path.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")

    for key, value in os.environ.items():
        if value:
            env[key] = value
    return env


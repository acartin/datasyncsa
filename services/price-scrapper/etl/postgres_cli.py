#!/usr/bin/env python3
"""Helpers minimos para ejecutar Postgres via docker compose + psql."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


SERVICE_DIR = Path(__file__).resolve().parents[1]
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
            env[key.strip()] = value.strip()

    for key in ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASS", "DB_NAME"):
        value = os.getenv(key)
        if value:
            env[key] = value
    return env


def run_psql(
    env: dict[str, str],
    *,
    sql: str,
    tuples_only: bool = False,
) -> str:
    process_env = os.environ.copy()
    if os.getenv("PRICE_SCRAPPER_DB_MODE") == "direct":
        command = [
            "psql",
            "-h",
            env.get("DB_HOST", "postgres"),
            "-p",
            env.get("DB_PORT", "5432"),
            "-U",
            env["DB_USER"],
            "-d",
            env["DB_NAME"],
            "-v",
            "ON_ERROR_STOP=1",
            "-q",
        ]
        if env.get("DB_PASS"):
            process_env["PGPASSWORD"] = env["DB_PASS"]
        cwd = SERVICE_DIR
    else:
        command = [
            "docker",
            "compose",
            "--env-file",
            str(ENV_PATH),
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            env["DB_USER"],
            "-d",
            env["DB_NAME"],
            "-v",
            "ON_ERROR_STOP=1",
            "-q",
        ]
        cwd = REPO_ROOT

    if tuples_only:
        command.extend(["-At", "-F", "\t"])

    result = subprocess.run(
        command,
        cwd=cwd,
        input=sql,
        text=True,
        capture_output=True,
        env=process_env,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()

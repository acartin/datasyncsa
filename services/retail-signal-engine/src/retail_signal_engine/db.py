"""Postgres access through the existing Docker Compose psql pattern."""

from __future__ import annotations

import csv
import io
import os
import subprocess
from pathlib import Path

from .config import ENV_PATH, REPO_ROOT, parse_env


class Database:
    def __init__(self, env: dict[str, str]) -> None:
        self.env = env
        missing = [key for key in ("DB_USER", "DB_NAME") if not env.get(key)]
        if missing:
            raise RuntimeError(f"Missing required DB env vars: {', '.join(missing)}")

    @classmethod
    def from_env(cls) -> "Database":
        return cls(parse_env())

    def run_psql(self, sql: str, *, tuples_only: bool = False) -> str:
        process_env = os.environ.copy()
        process_env.update({key: value for key, value in self.env.items() if value})

        if os.getenv("RETAIL_SIGNAL_DB_MODE") == "direct":
            command = [
                "psql",
                "-h",
                self.env.get("DB_HOST", "postgres"),
                "-p",
                self.env.get("DB_PORT", "5432"),
                "-U",
                self.env["DB_USER"],
                "-d",
                self.env["DB_NAME"],
                "-v",
                "ON_ERROR_STOP=1",
                "-q",
            ]
            if self.env.get("DB_PASS"):
                process_env["PGPASSWORD"] = self.env["DB_PASS"]
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
                self.env["DB_USER"],
                "-d",
                self.env["DB_NAME"],
                "-v",
                "ON_ERROR_STOP=1",
                "-q",
            ]

        if tuples_only:
            command.extend(["-At", "-F", "\t"])

        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            input=sql,
            text=True,
            capture_output=True,
            env=process_env,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return result.stdout.strip()

    def fetch_csv(self, sql: str) -> list[dict[str, str]]:
        output = self.run_psql(
            f"copy (\n{sql}\n) to stdout with (format csv, header true);"
        )
        reader = csv.DictReader(io.StringIO(output))
        return [dict(row) for row in reader]

    def apply_sql_file(self, path: Path) -> None:
        self.run_psql(path.read_text())


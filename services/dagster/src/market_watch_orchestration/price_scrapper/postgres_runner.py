import os
import subprocess


class PostgresRunner:
    """Runs SQL against the operational Postgres database."""

    def run(self, sql: str) -> str:
        env = os.environ.copy()
        if env.get("DB_PASS"):
            env["PGPASSWORD"] = env["DB_PASS"]

        result = subprocess.run(
            [
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
                "-At",
                "-F",
                "\t",
            ],
            input=sql,
            text=True,
            capture_output=True,
            env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return result.stdout.strip()


import os
import subprocess
from pathlib import Path


class CommandRunner:
    """Runs commands inside the price-scrapper bounded context."""

    def __init__(self, *, root_path: Path) -> None:
        self.root_path = root_path

    def run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=self.root_path,
            text=True,
            capture_output=True,
            env=os.environ.copy(),
        )

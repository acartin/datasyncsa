import os
import subprocess
from pathlib import Path


class CommandRunner:
    """Runs commands inside the price-scrapper bounded context."""

    def __init__(self, *, root_path: Path) -> None:
        self.root_path = root_path

    def list_command_scripts(self) -> list[str]:
        commands_dir = self.root_path / "commands"
        if not commands_dir.exists():
            return []

        return sorted(
            path.name
            for path in commands_dir.glob("*.py")
            if path.name != "__init__.py"
        )

    def run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=self.root_path,
            text=True,
            capture_output=True,
            env=os.environ.copy(),
        )


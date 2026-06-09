import shutil
from pathlib import Path
from typing import Optional

from mazyr.infrastructure.paths import MAZYR_HOME


class FilesystemAdapter:
    """File operations for .mazyr/ directory and memory storage."""

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else MAZYR_HOME
        self.mazyr_dir = self.base_dir
        self.memory_dir = self.base_dir / "memory"

    def init_mazyr_dir(self):
        self.mazyr_dir.mkdir(parents=True, exist_ok=True)
        self.memory_dir.mkdir(exist_ok=True)
        (self.memory_dir / "episodic").mkdir(exist_ok=True)
        (self.memory_dir / "semantic").mkdir(exist_ok=True)
        (self.memory_dir / "procedural").mkdir(exist_ok=True)

    def write_identity(self, content: str):
        (self.mazyr_dir / "identity.md").write_text(content)

    def write_mission(self, content: str):
        (self.mazyr_dir / "mission.md").write_text(content)

    def write_config(self, content: str):
        (self.mazyr_dir / "config.yaml").write_text(content)

    def read_file(self, path: str) -> Optional[str]:
        full_path = self.base_dir / path
        if full_path.exists():
            return full_path.read_text()
        return None

    def backup_memory(self, dest: str):
        shutil.copytree(self.memory_dir, dest, dirs_exist_ok=True)

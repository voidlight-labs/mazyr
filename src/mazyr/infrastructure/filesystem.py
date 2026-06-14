import shutil
import stat
from pathlib import Path
from typing import Optional

from mazyr.infrastructure.paths import MAZYR_HOME

# Restrictive permissions: only the owner can read/write/execute directories
# and read/write files.
_DIR_MODE = stat.S_IRWXU  # 0o700
_FILE_MODE = stat.S_IRUSR | stat.S_IWUSR  # 0o600


class FilesystemAdapter:
    """File operations for .mazyr/ directory and memory storage."""

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else MAZYR_HOME
        self.mazyr_dir = self.base_dir
        self.memory_dir = self.base_dir / "memory"

    def init_mazyr_dir(self):
        self.mazyr_dir.mkdir(parents=True, exist_ok=True)
        self.mazyr_dir.chmod(_DIR_MODE)
        self.memory_dir.mkdir(exist_ok=True)
        self.memory_dir.chmod(_DIR_MODE)
        (self.memory_dir / "episodic").mkdir(exist_ok=True)
        (self.memory_dir / "semantic").mkdir(exist_ok=True)
        (self.memory_dir / "procedural").mkdir(exist_ok=True)
        skills_dir = self.mazyr_dir / "skills"
        skills_dir.mkdir(exist_ok=True)
        skills_dir.chmod(_DIR_MODE)

    def copy_bundled_skills(self, bundled_skills_dir: Path | str) -> list[Path]:
        """Copy bundled skill files into the instance skills directory.

        Existing user skills are preserved (not overwritten). Returns the list
        of copied files.
        """
        source = Path(bundled_skills_dir)
        dest = self.mazyr_dir / "skills"
        dest.mkdir(parents=True, exist_ok=True)
        copied: list[Path] = []
        if not source.exists():
            return copied
        for src_file in source.glob("*.md"):
            dst_file = dest / src_file.name
            if not dst_file.exists():
                shutil.copy2(src_file, dst_file)
                dst_file.chmod(_FILE_MODE)
                copied.append(dst_file)
        return copied

    def _write_private_file(self, path: Path, content: str):
        """Write a file with owner-only read/write permissions."""
        path.write_text(content)
        path.chmod(_FILE_MODE)

    def write_identity(self, content: str):
        self._write_private_file(self.mazyr_dir / "identity.md", content)

    def write_mission(self, content: str):
        self._write_private_file(self.mazyr_dir / "mission.md", content)

    def write_config(self, content: str):
        self._write_private_file(self.mazyr_dir / "config.yaml", content)

    def read_file(self, path: str) -> Optional[str]:
        full_path = self.base_dir / path
        full_path = full_path.resolve()
        if not full_path.is_relative_to(self.base_dir.resolve()):
            return None
        if full_path.exists():
            return full_path.read_text()
        return None

    def backup_memory(self, dest: str):
        shutil.copytree(self.memory_dir, dest, dirs_exist_ok=True)

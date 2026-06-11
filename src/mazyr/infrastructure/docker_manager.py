import subprocess
import time
from pathlib import Path
from typing import Optional

from mazyr.infrastructure.paths import MAZYR_HOME


class DockerComposeManager:
    """Manages Qdrant container via Docker Compose."""

    def __init__(self, compose_file: Optional[str] = None):
        self.compose_file = Path(compose_file) if compose_file else Path("docker-compose.yml")
        self.qdrant_storage_dir = MAZYR_HOME / "memory" / "qdrant_storage"
        self._available = None

    @property
    def is_available(self) -> bool:
        """Check if docker compose is available on this system."""
        if self._available is None:
            self._available = self._check_docker()
        return self._available

    def _check_docker(self) -> bool:
        """Check if docker compose command works."""
        try:
            result = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Try legacy docker-compose
            try:
                result = subprocess.run(
                    ["docker-compose", "version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return result.returncode == 0
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return False

    def _compose_cmd(self, *args: str) -> list[str]:
        """Build docker compose command, preferring 'docker compose' over 'docker-compose'."""
        try:
            subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True,
                timeout=2,
                check=True,
            )
            return ["docker", "compose", "-f", str(self.compose_file), *args]
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ["docker-compose", "-f", str(self.compose_file), *args]

    def start(self) -> bool:
        """Start Qdrant container. Returns True if successful."""
        if not self.is_available:
            return False

        self.qdrant_storage_dir.mkdir(parents=True, exist_ok=True)
        cmd = self._compose_cmd("up", "-d", "qdrant")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env={
                **__import__("os").environ,
                "MAZYR_QDRANT_STORAGE": str(self.qdrant_storage_dir),
            },
        )
        return result.returncode == 0

    def stop(self) -> bool:
        """Stop Qdrant container."""
        if not self.is_available:
            return False

        cmd = self._compose_cmd("down")
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0

    def is_running(self) -> bool:
        """Check if Qdrant container is running."""
        if not self.is_available:
            return False

        cmd = self._compose_cmd("ps", "--format", "json", "qdrant")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return False
        return "running" in result.stdout.lower() or "Up" in result.stdout

    def wait_for_healthy(self, timeout: float = 60.0) -> bool:
        """Wait for Qdrant to be healthy."""
        if not self.is_available:
            return False

        start = time.time()
        while time.time() - start < timeout:
            if self.is_running():
                # Try health endpoint
                try:
                    import urllib.request

                    req = urllib.request.Request(
                        "http://localhost:6333/healthz",
                        method="GET",
                    )
                    with urllib.request.urlopen(req, timeout=2) as resp:
                        if resp.status == 200:
                            return True
                except Exception:
                    pass
            time.sleep(1)
        return False

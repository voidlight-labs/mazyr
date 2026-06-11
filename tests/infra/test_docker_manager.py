from unittest.mock import MagicMock, patch

from mazyr.infrastructure.docker_manager import DockerComposeManager
from mazyr.infrastructure.paths import MAZYR_HOME


class TestDockerComposeManager:
    def test_is_available_when_docker_compose_works(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            dm = DockerComposeManager()
            assert dm.is_available is True

    def test_is_not_available_when_docker_missing(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            dm = DockerComposeManager()
            assert dm.is_available is False

    def test_start_returns_false_when_docker_unavailable(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            dm = DockerComposeManager()
            assert dm.start() is False

    def test_stop_returns_false_when_docker_unavailable(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            dm = DockerComposeManager()
            assert dm.stop() is False

    def test_qdrant_storage_defaults_under_mazyr_home(self):
        dm = DockerComposeManager()
        assert dm.qdrant_storage_dir == MAZYR_HOME / "memory" / "qdrant_storage"

    def test_start_sets_qdrant_storage_env(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            dm = DockerComposeManager()
            dm.qdrant_storage_dir = tmp_path / "qdrant_storage"

            assert dm.start() is True

            start_call = mock_run.call_args_list[-1]
            assert start_call.kwargs["env"]["MAZYR_QDRANT_STORAGE"] == str(dm.qdrant_storage_dir)

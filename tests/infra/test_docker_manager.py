from unittest.mock import MagicMock, patch

from mazyr.infrastructure.docker_manager import DockerComposeManager


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

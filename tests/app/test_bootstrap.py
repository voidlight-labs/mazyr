import pytest
from unittest.mock import Mock

from mazyr.app.bootstrap import Bootstrap, BootContext


class TestBootstrap:
    def test_successful_boot(self):
        mock_loader = Mock()
        mock_loader.load_identity.return_value = Mock(
            instance_name="Aria", creator_name="Khayren", is_configured=True
        )
        mock_loader.load_mission.return_value = Mock(primary="Learn")
        mock_loader.load_custom_rules.return_value = []

        mock_memory = Mock()
        mock_llm = Mock()

        bootstrap = Bootstrap(mock_loader, mock_memory, mock_llm)
        ctx = bootstrap.boot()

        assert ctx.status == "READY"
        assert ctx.identity is not None

    def test_boot_fails_without_identity(self):
        mock_loader = Mock()
        mock_loader.load_identity.return_value = None

        bootstrap = Bootstrap(mock_loader, Mock(), Mock())
        ctx = bootstrap.boot()

        assert ctx.status == "ERROR"
        assert "mazyr-init" in ctx.errors[0]

    def test_boot_fails_unconfigured_identity(self):
        mock_loader = Mock()
        mock_loader.load_identity.return_value = Mock(
            instance_name="Mazyr", creator_name="Anonymous", is_configured=False
        )

        bootstrap = Bootstrap(mock_loader, Mock(), Mock())
        ctx = bootstrap.boot()

        assert ctx.status == "ERROR"

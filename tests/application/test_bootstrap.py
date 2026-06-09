import tempfile
from pathlib import Path
from unittest.mock import Mock

from mazyr.application.bootstrap import BootContext, Bootstrap
from mazyr.domain.instance_config import InstanceConfig


class TestBootstrap:
    def _make_config(self):
        return InstanceConfig(api_key="secret", inference_preference="cloud")

    def test_successful_boot(self):
        mock_loader = Mock()
        mock_loader.load_config.return_value = self._make_config()
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
        assert ctx.config is not None

    def test_successful_boot_with_custom_base_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write identity and mission files
            (Path(tmpdir) / "identity.md").write_text("""---
instance_name: Aria
creator: Khayren
vessel_type: laptop
---
""")
            (Path(tmpdir) / "mission.md").write_text("""---
primary: Learn
cope: general
---
""")
            (Path(tmpdir) / "config.yaml").write_text(
                "api_key: secret\ninference_preference: cloud\n"
            )

            from mazyr.infrastructure.config_loader import ConfigLoader

            loader = ConfigLoader(tmpdir)
            bootstrap = Bootstrap(loader, Mock(), Mock())
            ctx = bootstrap.boot(tmpdir)

            assert ctx.status == "READY"

    def test_boot_fails_without_config(self):
        mock_loader = Mock()
        mock_loader.load_config.return_value = None

        bootstrap = Bootstrap(mock_loader, Mock(), Mock())
        ctx = bootstrap.boot()

        assert ctx.status == "ERROR"
        assert "config" in ctx.errors[0].lower()

    def test_boot_fails_without_identity(self):
        mock_loader = Mock()
        mock_loader.load_config.return_value = self._make_config()
        mock_loader.load_identity.return_value = None

        bootstrap = Bootstrap(mock_loader, Mock(), Mock())
        ctx = bootstrap.boot()

        assert ctx.status == "ERROR"
        assert "mazyr-init" in ctx.errors[0]

    def test_boot_fails_unconfigured_identity(self):
        mock_loader = Mock()
        mock_loader.load_config.return_value = self._make_config()
        mock_loader.load_identity.return_value = Mock(
            instance_name="Mazyr", creator_name="Anonymous", is_configured=False
        )

        bootstrap = Bootstrap(mock_loader, Mock(), Mock())
        ctx = bootstrap.boot()

        assert ctx.status == "ERROR"

    def test_boot_fails_without_llm(self):
        mock_loader = Mock()
        mock_loader.load_config.return_value = InstanceConfig()
        mock_loader.load_identity.return_value = Mock(
            instance_name="Aria", creator_name="Khayren", is_configured=True
        )

        bootstrap = Bootstrap(mock_loader, Mock(), Mock())
        ctx = bootstrap.boot()

        assert ctx.status == "ERROR"
        assert "LLM" in ctx.errors[0]

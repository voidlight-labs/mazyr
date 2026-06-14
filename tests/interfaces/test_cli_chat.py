from pathlib import Path
from unittest.mock import Mock

from click.testing import CliRunner

from mazyr.interfaces import cli as cli_module
from mazyr.interfaces.cli import cli


def _write_instance(base_dir: Path):
    (base_dir / "identity.md").write_text("""---
instance_name: Aria
creator: Khayren
vessel_type: laptop
---
""")
    (base_dir / "mission.md").write_text("""---
primary: Learn
scope: general
---
""")
    (base_dir / "config.yaml").write_text("""api_key: secret
base_url: https://api.example.test/v1
model: test-model
inference_preference: cloud
sqlite_path: memory/mazyr.db
""")


def test_chat_command_calls_llm(monkeypatch, tmp_path):
    _write_instance(tmp_path)
    mock_cloud = Mock()
    mock_cloud.is_available.return_value = True
    mock_cloud.generate.return_value = "API reply"
    mock_cloud.generate_stream.return_value = iter(["API ", "reply"])

    monkeypatch.setattr(cli_module, "CloudLLM", Mock(return_value=mock_cloud))

    result = CliRunner().invoke(
        cli,
        ["chat", "--base-dir", str(tmp_path)],
        input="hello\nexit\n",
    )

    assert result.exit_code == 0
    assert "Aria:" in result.output
    assert "API reply" in result.output
    mock_cloud.generate_stream.assert_called_once()

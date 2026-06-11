from pathlib import Path
from unittest.mock import Mock

from click.testing import CliRunner

from mazyr.interfaces import cli as cli_module
from mazyr.interfaces.cli import cli


def _write_instance(base_dir: Path, telegram_token: str = "telegram-secret"):
    (base_dir / "identity.md").write_text(
        """---
instance_name: Aria
creator: Khayren
vessel_type: laptop
---
"""
    )
    (base_dir / "mission.md").write_text(
        """---
primary: Learn
scope: general
---
"""
    )
    (base_dir / "config.yaml").write_text(
        f"""api_key: secret
base_url: https://api.example.test/v1
model: test-model
inference_preference: cloud
sqlite_path: memory/mazyr.db
telegram_bot_token: {telegram_token}
"""
    )


def test_boot_daemon_receives_telegram_message(monkeypatch, tmp_path):
    _write_instance(tmp_path)
    mock_cloud = Mock()
    mock_cloud.is_available.return_value = True
    mock_cloud.generate.return_value = "telegram reply"
    mock_telegram = Mock()

    def listen(handler):
        handler(
            {
                "text": "hello",
                "chat_id": 123,
                "from": "khayren",
                "message_id": 456,
            }
        )

    mock_telegram.listen.side_effect = listen
    monkeypatch.setattr(cli_module, "CloudLLM", Mock(return_value=mock_cloud))
    monkeypatch.setattr(cli_module, "TelegramAdapter", Mock(return_value=mock_telegram))

    result = CliRunner().invoke(
        cli,
        ["boot", "--base-dir", str(tmp_path), "--daemon"],
    )

    assert result.exit_code == 0
    assert "Telegram daemon listening" in result.output
    mock_cloud.generate.assert_called_once()
    mock_telegram.send_message.assert_called_once_with(123, "telegram reply")

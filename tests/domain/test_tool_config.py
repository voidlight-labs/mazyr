from mazyr.domain.tool_config import ToolRegistryConfig, AbuseThresholds, Tier2Config, Tier3Config


class TestToolRegistryConfig:
    def test_default_config(self):
        cfg = ToolRegistryConfig()
        assert cfg.sandbox.run_code_timeout_seconds == 30
        assert cfg.tier2.abuse_thresholds.add_memory_per_session == 20
        assert cfg.tier3.approval_timeout_minutes == 10
        assert cfg.tier3.notify_channel == "cli"
        assert "/mazyr/context/" in cfg.read_file_whitelist
        assert cfg.external_api_whitelist["api.github.com"] == 2

    def test_custom_config(self):
        cfg = ToolRegistryConfig(
            tier2=Tier2Config(abuse_thresholds=AbuseThresholds(add_memory_per_session=5)),
            tier3=Tier3Config(approval_timeout_minutes=30),
            read_file_whitelist=["/custom/path/"],
            external_api_whitelist={"api.custom.com": 1},
        )
        assert cfg.tier2.abuse_thresholds.add_memory_per_session == 5
        assert cfg.tier3.approval_timeout_minutes == 30
        assert cfg.read_file_whitelist == ["/custom/path/"]
        assert cfg.external_api_whitelist["api.custom.com"] == 1

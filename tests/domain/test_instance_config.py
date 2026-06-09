import pytest

from mazyr.domain.instance_config import InstanceConfig


class TestInstanceConfig:
    def test_defaults(self):
        cfg = InstanceConfig()
        assert cfg.base_url == "https://api.moonshot.cn/v1"
        assert cfg.model == "kimi-k2-6"
        assert cfg.inference_preference == "hybrid"
        assert cfg.qdrant_host == "localhost"
        assert cfg.qdrant_port == 6333
        assert cfg.sqlite_path == "./memory/mazyr.db"

    def test_invalid_inference_preference(self):
        with pytest.raises(ValueError):
            InstanceConfig(inference_preference="invalid")

    def test_invalid_qdrant_port(self):
        with pytest.raises(ValueError):
            InstanceConfig(qdrant_port=0)
        with pytest.raises(ValueError):
            InstanceConfig(qdrant_port=70000)

    def test_use_cloud_llm(self):
        assert InstanceConfig(api_key="secret").use_cloud_llm is True
        assert InstanceConfig().use_cloud_llm is False

    def test_use_local_llm(self):
        assert InstanceConfig(local_model_path="/path/to/model.gguf").use_local_llm is True
        assert InstanceConfig().use_local_llm is False

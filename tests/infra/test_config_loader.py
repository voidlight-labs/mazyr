import tempfile
from pathlib import Path

import pytest

from mazyr.infrastructure.config_loader import ConfigLoader
from mazyr.infrastructure.paths import MAZYR_HOME


class TestConfigLoader:
    def test_load_identity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "identity.md").write_text("""---
instance_name: Aria
creator: Khayren
vessel_type: laptop
---
""")
            loader = ConfigLoader(tmpdir)
            identity = loader.load_identity(tmpdir)

            assert identity.instance_name == "Aria"
            assert identity.creator_name == "Khayren"

    def test_load_identity_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = ConfigLoader(tmpdir)
            identity = loader.load_identity(tmpdir)
            assert identity is None

    def test_load_mission(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "mission.md").write_text("""---
primary: Learn coding
scope: coding, analysis
---
""")
            loader = ConfigLoader(tmpdir)
            mission = loader.load_mission(tmpdir)

            assert mission.primary == "Learn coding"
            assert mission.scope == ["coding", "analysis"]

    def test_load_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "config.yaml").write_text("""api_key: secret
base_url: https://api.moonshot.cn/v1
model: kimi-k2-6
inference_preference: cloud
qdrant_enabled: true
embedding_api_key: embed-secret
embedding_model: text-embedding-3-small
embedding_dimensions: 1536
""")
            loader = ConfigLoader(tmpdir)
            config = loader.load_config()

            assert config is not None
            assert config.api_key == "secret"
            assert config.inference_preference == "cloud"
            assert config.qdrant_port == 6333
            assert config.sqlite_path == str(Path(tmpdir) / "memory" / "mazyr.db")
            assert config.embedding_api_key == "embed-secret"
            assert config.embedding_model == "text-embedding-3-small"

    def test_load_config_resolves_relative_sqlite_path_under_instance_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "config.yaml").write_text("""api_key: secret
inference_preference: cloud
sqlite_path: memory/custom.db
""")
            loader = ConfigLoader(tmpdir)
            config = loader.load_config()

            assert config.sqlite_path == str(Path(tmpdir) / "memory" / "custom.db")

    def test_load_config_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = ConfigLoader(tmpdir)
            config = loader.load_config()
            assert config is None

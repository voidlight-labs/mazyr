import pytest
import tempfile
from pathlib import Path

from mazyr.infrastructure.config_loader import ConfigLoader


class TestConfigLoader:
    def test_load_identity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mazyr_dir = Path(tmpdir) / ".mazyr"
            mazyr_dir.mkdir()
            (mazyr_dir / "identity.md").write_text("""---
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
            mazyr_dir = Path(tmpdir) / ".mazyr"
            mazyr_dir.mkdir()
            (mazyr_dir / "mission.md").write_text("""---
primary: Learn coding
scope: coding, analysis
---
""")
            loader = ConfigLoader(tmpdir)
            mission = loader.load_mission(tmpdir)

            assert mission.primary == "Learn coding"
            assert mission.scope == ["coding", "analysis"]

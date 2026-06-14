import tempfile
from pathlib import Path

from mazyr.infrastructure.filesystem import FilesystemAdapter


class TestFilesystemAdapter:
    def test_init_mazyr_dir_creates_skills_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fs = FilesystemAdapter(base_dir=tmp)
            fs.init_mazyr_dir()
            assert (tmp / "skills").exists()
            assert (tmp / "skills").is_dir()

    def test_copy_bundled_skills_copies_to_user_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bundled = tmp / "bundled_skills"
            bundled.mkdir()
            (bundled / "python-craft.md").write_text(
                "---\nname: python-craft\ndescription: d\ncategory: coding\n---\n\ncontent"
            )

            fs = FilesystemAdapter(base_dir=tmp)
            fs.init_mazyr_dir()
            copied = fs.copy_bundled_skills(bundled)

            assert len(copied) == 1
            assert (tmp / "skills" / "python-craft.md").exists()
            assert "content" in (tmp / "skills" / "python-craft.md").read_text()

    def test_copy_bundled_skills_preserves_existing_user_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bundled = tmp / "bundled_skills"
            bundled.mkdir()
            (bundled / "python-craft.md").write_text(
                "---\nname: python-craft\ndescription: bundled\ncategory: coding\n---\n\nbundled"
            )

            fs = FilesystemAdapter(base_dir=tmp)
            fs.init_mazyr_dir()
            (tmp / "skills" / "python-craft.md").write_text(
                "---\nname: python-craft\ndescription: user\ncategory: coding\n---\n\nuser"
            )
            copied = fs.copy_bundled_skills(bundled)

            assert len(copied) == 0
            content = (tmp / "skills" / "python-craft.md").read_text()
            assert "user" in content
            assert "bundled" not in content

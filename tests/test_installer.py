from pathlib import Path
import json
import tempfile
import unittest

from starsector_fontgen.errors import FontGenError
from starsector_fontgen.installer import (
    InstallConfig,
    install_replacement_fonts,
    restore_from_manifest,
    validate_starsector_root,
)


class InstallerTests(unittest.TestCase):
    def make_game_root(self, root: Path) -> Path:
        game = root / "Starsector"
        fonts = game / "starsector-core" / "graphics" / "fonts"
        fonts.mkdir(parents=True)
        (fonts / "old.fnt").write_text("old fnt", encoding="utf-8")
        (fonts / "old.png").write_bytes(b"old png")
        return game

    def test_validate_starsector_root_requires_fonts_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaises(FontGenError):
                validate_starsector_root(root)

    def test_install_copies_only_font_files_and_restore_uses_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game = self.make_game_root(root)
            replacement = root / "replacement_fonts"
            replacement.mkdir()
            (replacement / "old.fnt").write_text("new fnt", encoding="utf-8")
            (replacement / "new_0.png").write_bytes(b"new png")
            (replacement / "README.md").write_text("do not copy", encoding="utf-8")
            manifest = root / "work" / "install_manifest.json"

            result = install_replacement_fonts(
                InstallConfig(
                    starsector_root=game,
                    replacement_font_dir=replacement,
                    manifest_path=manifest,
                )
            )

            fonts = game / "starsector-core" / "graphics" / "fonts"
            self.assertEqual((fonts / "old.fnt").read_text(encoding="utf-8"), "new fnt")
            self.assertTrue((fonts / "new_0.png").exists())
            self.assertFalse((fonts / "README.md").exists())
            self.assertTrue(result.backup_dir.exists())
            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(len(manifest_data["installed_files"]), 2)

            restore = restore_from_manifest(manifest)

            self.assertEqual((fonts / "old.fnt").read_text(encoding="utf-8"), "old fnt")
            self.assertFalse((fonts / "new_0.png").exists())
            self.assertEqual(restore.backup_dir, result.backup_dir)


if __name__ == "__main__":
    unittest.main()

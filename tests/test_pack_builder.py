from pathlib import Path
import json
import tempfile
import unittest

from starsector_fontgen.errors import FontGenError
from starsector_fontgen.pack_builder import BuildPackConfig, build_pack


class PackBuilderTests(unittest.TestCase):
    def test_build_pack_copies_fonts_and_generates_release_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            replacement = root / "replacement_fonts_src"
            replacement.mkdir()
            (replacement / "font.fnt").write_text("fnt", encoding="utf-8")
            (replacement / "font_0.png").write_bytes(b"png")
            (replacement / "ignore.md").write_text("ignore", encoding="utf-8")
            report = replacement / "rebuild_fontlib_report.md"
            report.write_text("# report", encoding="utf-8")
            output_pack = root / "release" / "Starsector-Uranus-Font-Pack"

            result = build_pack(
                BuildPackConfig(
                    replacement_font_dir=replacement,
                    report=report,
                    output_pack=output_pack,
                    pack_name="Starsector Uranus Pixel Font Pack",
                )
            )

            self.assertTrue((output_pack / "replacement_fonts" / "font.fnt").exists())
            self.assertTrue((output_pack / "replacement_fonts" / "font_0.png").exists())
            self.assertFalse((output_pack / "replacement_fonts" / "ignore.md").exists())
            self.assertTrue((output_pack / "rebuild_fontlib_report.md").exists())
            self.assertTrue(result.install_script.exists())
            self.assertTrue(result.uninstall_script.exists())
            self.assertTrue(result.readme_path.exists())
            manifest = json.loads((output_pack / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["pack_name"], "Starsector Uranus Pixel Font Pack")
            self.assertEqual(manifest["file_count"], 2)
            self.assertEqual(manifest["warning"], "this is a core-overwrite font pack")
            self.assertIn("replacement_fonts/font.fnt", manifest["replacement_font_files"])
            install_script = result.install_script.read_text(encoding="utf-8")
            self.assertIn("starsector-core\\graphics\\fonts", install_script)
            self.assertIn("install_manifest.json", install_script)
            self.assertIn(".fnt", install_script)
            self.assertIn(".png", install_script)

    def test_build_pack_refuses_existing_pack_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            replacement = root / "replacement"
            replacement.mkdir()
            (replacement / "font.fnt").write_text("fnt", encoding="utf-8")
            report = root / "rebuild_fontlib_report.md"
            report.write_text("report", encoding="utf-8")
            output_pack = root / "pack"
            output_pack.mkdir()

            with self.assertRaises(FontGenError):
                build_pack(
                    BuildPackConfig(
                        replacement_font_dir=replacement,
                        report=report,
                        output_pack=output_pack,
                        pack_name="Pack",
                    )
                )

    def test_build_pack_force_recreates_existing_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            replacement = root / "replacement"
            replacement.mkdir()
            (replacement / "font.fnt").write_text("fnt", encoding="utf-8")
            report = root / "rebuild_fontlib_report.md"
            report.write_text("report", encoding="utf-8")
            output_pack = root / "pack"
            output_pack.mkdir()
            (output_pack / "old.txt").write_text("old", encoding="utf-8")

            build_pack(
                BuildPackConfig(
                    replacement_font_dir=replacement,
                    report=report,
                    output_pack=output_pack,
                    pack_name="Pack",
                    force=True,
                )
            )

            self.assertFalse((output_pack / "old.txt").exists())
            self.assertTrue((output_pack / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()

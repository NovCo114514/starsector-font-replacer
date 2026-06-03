from pathlib import Path
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from starsector_fontgen.build_pack_cli import main
from starsector_fontgen.pack_builder import BuildPackResult


class BuildPackCliTests(unittest.TestCase):
    def test_build_pack_cli_calls_builder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_pack = root / "pack"
            fake_result = BuildPackResult(
                output_pack=output_pack,
                replacement_files=[Path("replacement_fonts/font.fnt")],
                manifest_path=output_pack / "manifest.json",
                install_script=output_pack / "install_font_pack.ps1",
                uninstall_script=output_pack / "uninstall_font_pack.ps1",
                readme_path=output_pack / "README.md",
                copied_report=output_pack / "rebuild_fontlib_report.md",
            )

            with patch("starsector_fontgen.build_pack_cli.build_pack", return_value=fake_result) as build:
                with redirect_stdout(io.StringIO()):
                    code = main(
                        [
                            "--replacement-font-dir",
                            str(root / "replacement_fonts"),
                            "--report",
                            str(root / "rebuild_fontlib_report.md"),
                            "--output-pack",
                            str(output_pack),
                            "--pack-name",
                            "Pack",
                            "--force",
                        ]
                    )

            self.assertEqual(code, 0)
            self.assertEqual(build.call_count, 1)
            config = build.call_args.args[0]
            self.assertEqual(config.pack_name, "Pack")
            self.assertTrue(config.force)


if __name__ == "__main__":
    unittest.main()

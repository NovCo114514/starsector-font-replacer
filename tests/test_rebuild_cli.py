from pathlib import Path
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from starsector_fontgen.rebuild_cli import main
from starsector_fontgen.rebuild_fontlib import RebuildEntry, RebuildResult


class RebuildCliTests(unittest.TestCase):
    def test_rebuild_cli_calls_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = root / "out" / "rebuild_fontlib_report.md"
            fake_result = RebuildResult(
                entries=[
                    RebuildEntry(
                        source_fnt=root / "fonts" / "font.fnt",
                        original_size=16,
                        output_fnt=root / "out" / "font.fnt",
                        output_png=root / "out" / "font_0.png",
                        success=True,
                        glyph_count=10,
                        atlas_occupancy=0.01,
                        unsupported_chars=False,
                    )
                ],
                report_path=report,
            )

            with patch("starsector_fontgen.rebuild_cli.rebuild_fontlib", return_value=fake_result) as rebuild:
                with redirect_stdout(io.StringIO()):
                    code = main(
                        [
                            "--font",
                            str(root / "font.ttf"),
                            "--source-font-dir",
                            str(root / "fonts"),
                            "--charset",
                            str(root / "charset.txt"),
                            "--output-font-dir",
                            str(root / "out"),
                            "--atlas-size",
                            "4096",
                            "--force",
                        ]
                    )

            self.assertEqual(code, 0)
            self.assertEqual(rebuild.call_count, 1)
            config = rebuild.call_args.args[0]
            self.assertEqual(config.atlas_size, 4096)
            self.assertTrue(config.force)


if __name__ == "__main__":
    unittest.main()

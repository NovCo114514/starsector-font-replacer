from pathlib import Path
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from starsector_fontgen.analyze_cli import main
from starsector_fontgen.analyzer import FontLibAnalysisResult


class AnalyzeCliTests(unittest.TestCase):
    def test_analyze_cli_calls_analyzer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            font_dir = root / "graphics" / "fonts"
            config_dir = root / "config"
            output_dir = root / "out"
            fake_result = FontLibAnalysisResult(
                font_dir=font_dir,
                config_dir=config_dir,
                output_dir=output_dir,
                fonts=[],
                charset_path=output_dir / "charset_union_from_fontlib.txt",
                report_path=output_dir / "fontlib_analysis_report.md",
            )

            with patch("starsector_fontgen.analyze_cli.analyze_fontlib", return_value=fake_result) as analyze:
                with redirect_stdout(io.StringIO()):
                    code = main(
                        [
                            "--font-dir",
                            str(font_dir),
                            "--config-dir",
                            str(config_dir),
                            "--output",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(code, 0)
            self.assertEqual(analyze.call_count, 1)
            self.assertEqual(analyze.call_args.args, (font_dir, config_dir, output_dir))


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from starsector_fontgen.charset_filter import CharsetFilterResult
from starsector_fontgen.filter_cli import main


class FilterCliTests(unittest.TestCase):
    def test_filter_cli_calls_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            font = root / "font.ttf"
            charset = root / "charset.txt"
            output = root / "supported.txt"
            fake_result = CharsetFilterResult(
                input_count=3,
                supported_count=2,
                unsupported_count=1,
                unsupported_chars=[],
                output_path=output,
                report_path=root / "charset_filter_report.txt",
            )

            with patch("starsector_fontgen.filter_cli.filter_charset_by_font", return_value=fake_result) as filter_call:
                with redirect_stdout(io.StringIO()):
                    code = main(
                        [
                            "--font",
                            str(font),
                            "--charset",
                            str(charset),
                            "--output",
                            str(output),
                            "--force",
                        ]
                    )

            self.assertEqual(code, 0)
            self.assertEqual(filter_call.call_count, 1)
            self.assertEqual(filter_call.call_args.args, (font, charset, output))
            self.assertTrue(filter_call.call_args.kwargs["force"])


if __name__ == "__main__":
    unittest.main()

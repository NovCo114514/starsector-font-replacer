from pathlib import Path
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from starsector_fontgen.cli import main
from starsector_fontgen.generator import (
    BatchEntry,
    BatchResult,
    FontGenerationResult,
    FontGenConfig,
    OutputPaths,
)


def make_outputs(prefix: Path) -> OutputPaths:
    return OutputPaths(
        fnt=prefix.with_suffix(".fnt"),
        atlas=prefix.with_name(f"{prefix.name}_0.png"),
        preview=prefix.with_name(f"{prefix.name}_preview.png"),
        report=prefix.with_name(f"{prefix.name}_report.txt"),
        unsupported_report=prefix.with_name(f"{prefix.name}_unsupported_chars_report.txt"),
    )


class CliTests(unittest.TestCase):
    def test_size_mode_uses_single_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "out" / "myfont16"
            outputs = make_outputs(output)
            fake_result = FontGenerationResult(
                config=FontGenConfig(
                    font=Path("font.ttf"),
                    text_dir=Path("data"),
                    extra_charset=None,
                    size=18,
                    output=output,
                ),
                outputs=outputs,
                glyph_count=10,
                atlas_occupancy=0.01,
            )

            with patch("starsector_fontgen.cli.generate_font_result", return_value=fake_result) as single:
                with patch("starsector_fontgen.cli.generate_batch") as batch:
                    with redirect_stdout(io.StringIO()):
                        code = main(
                            [
                                "--font",
                                "font.ttf",
                                "--text-dir",
                                "data",
                                "--size",
                                "18",
                                "--output",
                                str(output),
                            ]
                        )

            self.assertEqual(code, 0)
            self.assertEqual(single.call_count, 1)
            self.assertFalse(batch.called)
            self.assertEqual(single.call_args.args[0].size, 18)

    def test_sizes_mode_uses_batch_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "out" / "myfont16"
            fake_batch = BatchResult(
                entries=[],
                summary_report=output.parent / "batch_summary_report.txt",
                patch_instructions=output.parent / "patch_instructions.txt",
            )

            with patch("starsector_fontgen.cli.generate_batch", return_value=fake_batch) as batch:
                with patch("starsector_fontgen.cli.generate_font_result") as single:
                    with redirect_stdout(io.StringIO()):
                        code = main(
                            [
                                "--font",
                                "font.ttf",
                                "--text-dir",
                                "data",
                                "--sizes",
                                "12,16,20",
                                "--output",
                                str(output),
                            ]
                        )

            self.assertEqual(code, 0)
            self.assertEqual(batch.call_count, 1)
            self.assertFalse(single.called)
            self.assertEqual(batch.call_args.args[1], [12, 16, 20])

    def test_sizes_mode_returns_error_when_any_size_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "out" / "myfont16"
            failed_outputs = make_outputs(output)
            fake_batch = BatchResult(
                entries=[
                    BatchEntry(
                        size=16,
                        outputs=failed_outputs,
                        glyph_count=None,
                        atlas_size=2048,
                        atlas_occupancy=None,
                        success=False,
                        unsupported_chars=True,
                        error="unsupported chars",
                    )
                ],
                summary_report=output.parent / "batch_summary_report.txt",
                patch_instructions=output.parent / "patch_instructions.txt",
            )

            with patch("starsector_fontgen.cli.generate_batch", return_value=fake_batch):
                with redirect_stdout(io.StringIO()):
                    code = main(
                        [
                            "--font",
                            "font.ttf",
                            "--text-dir",
                            "data",
                            "--sizes",
                            "16",
                            "--output",
                            str(output),
                        ]
                    )

            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()

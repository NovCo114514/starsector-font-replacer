from pathlib import Path
import tempfile
import unittest

from starsector_fontgen.errors import FontGenError
from starsector_fontgen.generator import (
    FontGenConfig,
    OutputPaths,
    batch_output_prefix,
    batch_summary_path,
    build_report,
    calculate_atlas_occupancy,
    measure_line_metrics,
    measure_space_advance,
    output_paths,
    parse_sizes_argument,
    patch_instructions_path,
    validate_config,
)
from starsector_fontgen.scanner import CharsetBuildResult


class FakeFont:
    def getlength(self, char: str) -> float:
        if char == " ":
            return 0
        if char == "n":
            return 7
        return 0

    def getmetrics(self) -> tuple[int, int]:
        return 12, 4


class GeneratorUnitTests(unittest.TestCase):
    def test_output_paths_use_prefix_semantics(self) -> None:
        paths = output_paths(Path("output/fonts/myfont16"))

        self.assertEqual(paths.fnt, Path("output/fonts/myfont16.fnt"))
        self.assertEqual(paths.atlas, Path("output/fonts/myfont16_0.png"))
        self.assertEqual(paths.preview, Path("output/fonts/myfont16_preview.png"))
        self.assertEqual(paths.report, Path("output/fonts/myfont16_report.txt"))

    def test_batch_output_prefix_replaces_trailing_size(self) -> None:
        self.assertEqual(batch_output_prefix(Path("output/fonts/myfont16"), 12), Path("output/fonts/myfont12"))
        self.assertEqual(batch_output_prefix(Path("output/fonts/myfont"), 20), Path("output/fonts/myfont20"))

    def test_batch_support_paths_use_output_directory(self) -> None:
        self.assertEqual(batch_summary_path(Path("output/fonts/myfont16")), Path("output/fonts/batch_summary_report.txt"))
        self.assertEqual(patch_instructions_path(Path("output/fonts/myfont16")), Path("output/fonts/patch_instructions.txt"))

    def test_parse_sizes_argument(self) -> None:
        self.assertEqual(parse_sizes_argument("12, 16,20"), [12, 16, 20])
        with self.assertRaises(FontGenError):
            parse_sizes_argument("12,,16")
        with self.assertRaises(FontGenError):
            parse_sizes_argument("12,12")

    def test_space_advance_falls_back_to_n(self) -> None:
        self.assertEqual(measure_space_advance(FakeFont(), 16), 7)

    def test_line_metrics_prefer_font_metrics(self) -> None:
        self.assertEqual(measure_line_metrics(FakeFont(), []), (16, 12))

    def test_invalid_atlas_size_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            font = root / "font.ttf"
            font.write_bytes(b"not a real font")
            text_dir = root / "data"
            text_dir.mkdir()
            config = FontGenConfig(
                font=font,
                text_dir=text_dir,
                extra_charset=None,
                size=16,
                output=root / "out" / "myfont16",
                atlas_size=1536,
            )

            with self.assertRaises(FontGenError):
                validate_config(config)

    def test_report_includes_reference_encoding(self) -> None:
        config = FontGenConfig(
            font=Path("ttf/font.ttf"),
            text_dir=Path("data"),
            extra_charset=None,
            size=16,
            output=Path("output/fonts/myfont16"),
        )
        outputs = OutputPaths(
            fnt=Path("output/fonts/myfont16.fnt"),
            atlas=Path("output/fonts/myfont16_0.png"),
            preview=Path("output/fonts/myfont16_preview.png"),
            report=Path("output/fonts/myfont16_report.txt"),
            unsupported_report=Path("output/fonts/myfont16_unsupported_chars_report.txt"),
        )
        charset = CharsetBuildResult(
            chars=["A"],
            char_sources={"A": {"preview text"}},
            ignored_chars={},
            read_records=[],
            source_unique_counts={"preview text": 1},
        )

        report = build_report(config, outputs, charset, 1, Path("reference/orbitron12.fnt"), "gb18030", 0.125)

        self.assertIn("Reference encoding: gb18030", report)
        self.assertIn("Atlas occupancy: 12.50%", report)

    def test_calculate_atlas_occupancy(self) -> None:
        class Metric:
            width = 4
            height = 8

        self.assertEqual(calculate_atlas_occupancy([Metric()], 16), 0.125)


if __name__ == "__main__":
    unittest.main()

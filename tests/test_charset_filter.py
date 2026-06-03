from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from starsector_fontgen.charset_filter import filter_charset_by_font, read_charset_chars
from starsector_fontgen.errors import FontGenError


class CharsetFilterTests(unittest.TestCase):
    def test_read_charset_chars_deduplicates_and_keeps_space(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "charset.txt"
            path.write_text("A A\n\u4e2d\u4e2d", encoding="utf-8")

            self.assertEqual(read_charset_chars(path), ["A", " ", "\u4e2d"])

    def test_filter_charset_by_font_keeps_supported_chars_and_reports_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            font = root / "font.ttf"
            charset = root / "charset_union_from_fontlib.txt"
            output = root / "charset_supported_by_font.txt"
            font.write_bytes(b"fake font")
            charset.write_text(" A\u4e2d\u2605", encoding="utf-8")

            with patch("starsector_fontgen.charset_filter.load_font_cmap", return_value={ord("A"), ord("\u4e2d")}):
                with patch("starsector_fontgen.charset_filter.load_pillow_font", return_value=object()):
                    with patch("starsector_fontgen.charset_filter.glyph_renders_empty", return_value=False):
                        result = filter_charset_by_font(font, charset, output)

            self.assertEqual(output.read_text(encoding="utf-8"), " A\u4e2d")
            report = (root / "charset_filter_report.txt").read_text(encoding="utf-8")
            self.assertEqual(result.input_count, 4)
            self.assertEqual(result.supported_count, 3)
            self.assertEqual(result.unsupported_count, 1)
            self.assertEqual(result.missing_cmap_count, 1)
            self.assertEqual(result.empty_glyph_count, 0)
            self.assertIn("\u2605", report)
            self.assertIn("U+2605", report)
            self.assertIn("BLACK STAR", report)
            self.assertIn("missing_cmap", report)

    def test_filter_charset_by_font_filters_empty_glyphs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            font = root / "font.ttf"
            charset = root / "charset_union_from_fontlib.txt"
            output = root / "charset_supported_by_font.txt"
            font.write_bytes(b"fake font")
            charset.write_text("A\u2605", encoding="utf-8")

            def is_empty(_font, char: str) -> bool:
                return char == "\u2605"

            with patch("starsector_fontgen.charset_filter.load_font_cmap", return_value={ord("A"), ord("\u2605")}):
                with patch("starsector_fontgen.charset_filter.load_pillow_font", return_value=object()):
                    with patch("starsector_fontgen.charset_filter.glyph_renders_empty", side_effect=is_empty):
                        result = filter_charset_by_font(font, charset, output)

            self.assertEqual(output.read_text(encoding="utf-8"), "A")
            report = (root / "charset_filter_report.txt").read_text(encoding="utf-8")
            self.assertEqual(result.missing_cmap_count, 0)
            self.assertEqual(result.empty_glyph_count, 1)
            self.assertIn("empty_glyph", report)

    def test_filter_charset_refuses_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            font = root / "font.ttf"
            charset = root / "charset.txt"
            output = root / "supported.txt"
            font.write_bytes(b"fake font")
            charset.write_text("A", encoding="utf-8")
            output.write_text("old", encoding="utf-8")

            with patch("starsector_fontgen.charset_filter.load_font_cmap", return_value={ord("A")}):
                with patch("starsector_fontgen.charset_filter.load_pillow_font", return_value=object()):
                    with self.assertRaises(FontGenError):
                        filter_charset_by_font(font, charset, output)


if __name__ == "__main__":
    unittest.main()
